"""
RunPod Serverless inference client.

Real contract (verified against RunPod docs):
  • POST https://api.runpod.ai/v2/{endpoint_id}/runsync
      headers: Authorization: Bearer {api_key}
      body:    {"input": {...}}
  • runsync waits for completion (good for interactive use); if a job exceeds
    ~90s it returns status IN_PROGRESS and we fall back to polling /status/{id}.
  • Response carries delayTime (cold-start ms) + executionTime (ms) + output.

COST: billable_ms = delayTime + executionTime  → seconds × per_second_usd.
Cold starts (delayTime, 30-60s) ARE billed — the cost tracker surfaces this.

MOCK MODE (MOCK_INFERENCE=1, the default): returns realistic fake completions
with plausible token counts and GPU timings, so the entire inference pipeline
(tiers, trace, cost, chat UI) can be built and verified for $0. Flip to 0 and
set real endpoint_ids in models.yaml to use live RunPod.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import random
from dataclasses import dataclass

import httpx

from app.inference.registry import ModelDescriptor

RUNPOD_BASE = "https://api.runpod.ai/v2"


@dataclass
class InferenceResult:
    """One completion + the metering needed for cost + trace."""

    text: str
    input_tokens: int
    output_tokens: int
    delay_ms: int          # cold-start time (billed)
    execution_ms: int      # compute time (billed)
    mocked: bool

    @property
    def billable_ms(self) -> int:
        return self.delay_ms + self.execution_ms


def _mock_enabled() -> bool:
    return os.getenv("MOCK_INFERENCE", "1") == "1"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class RunPodClient:
    def __init__(self) -> None:
        self._api_key = os.getenv("RUNPOD_API_KEY", "")

    async def generate(
        self,
        *,
        model: ModelDescriptor,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> InferenceResult:
        if _mock_enabled():
            return await self._mock_generate(model=model, prompt=prompt, max_tokens=max_tokens)
        return await self._real_generate(
            model=model, prompt=prompt, max_tokens=max_tokens, temperature=temperature
        )

    # ── mock ────────────────────────────────────────────────────────────────
    async def _mock_generate(
        self, *, model: ModelDescriptor, prompt: str, max_tokens: int
    ) -> InferenceResult:
        # Deterministic-ish per prompt so repeated runs are stable in tests, but
        # with realistic variation in timing. Bigger models "run" longer.
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        # simulate a small amount of real latency so the UI's loading states show
        await asyncio.sleep(0.05)

        # plausible timings: bigger GPU tier -> longer exec; occasional cold start
        base_exec = {"RTX 4090 24GB": 900, "A100 40GB": 1400, "A100 80GB": 2600}.get(
            model.gpu_tier, 1200
        )
        execution_ms = base_exec + rng.randint(-200, 600)
        delay_ms = rng.choice([0, 0, 0, rng.randint(8000, 45000)])  # ~25% cold

        text = (
            f"[MOCK · {model.display_name}] Based on the retrieved context, here is a "
            f"grounded synthesis answering the query. (This is simulated output for "
            f"$0 development; set MOCK_INFERENCE=0 with a real RunPod endpoint for "
            f"live generation.)"
        )
        return InferenceResult(
            text=text,
            input_tokens=_estimate_tokens(prompt),
            output_tokens=_estimate_tokens(text),
            delay_ms=delay_ms,
            execution_ms=execution_ms,
            mocked=True,
        )

    # ── real ────────────────────────────────────────────────────────────────
    async def _real_generate(
        self, *, model: ModelDescriptor, prompt: str, max_tokens: int, temperature: float
    ) -> InferenceResult:
        if not self._api_key:
            raise ValueError("RUNPOD_API_KEY not set but MOCK_INFERENCE=0.")
        if model.endpoint_id.startswith("REPLACE_"):
            raise ValueError(
                f"Model '{model.key}' has no real endpoint_id configured in models.yaml."
            )

        # The RunPod vLLM Quick Deploy worker is OpenAI-COMPATIBLE: it exposes
        #   POST {base}/{endpoint_id}/openai/v1/chat/completions
        # This is the documented, stable interface (vs the native /runsync
        # handler, whose `input` schema varies by worker). We use it by default.
        # Set RUNPOD_API_STYLE=native to use the legacy /runsync path instead.
        style = os.getenv("RUNPOD_API_STYLE", "openai").lower()
        # Cold starts (download weights + load + first-token) can take minutes.
        # Long read timeout so we don't disconnect mid-cold-start (which wastes
        # GPU time we'd still be billed for). Short connect timeout so genuine
        # network failures still surface fast.
        timeout = httpx.Timeout(connect=10.0, read=600.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            if style == "native":
                return await self._call_native(
                    client, model=model, prompt=prompt,
                    max_tokens=max_tokens, temperature=temperature,
                )
            return await self._call_openai(
                client, model=model, prompt=prompt,
                max_tokens=max_tokens, temperature=temperature,
            )

    async def _call_openai(
        self, client, *, model, prompt, max_tokens, temperature
    ) -> InferenceResult:
        """OpenAI-compatible chat/completions against the RunPod vLLM worker."""
        url = f"{RUNPOD_BASE}/{model.endpoint_id}/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        # MODEL_NAME on the worker = the HF model id; RunPod accepts the endpoint's
        # configured model. We send the descriptor's hf id if present, else key.
        payload = {
            "model": getattr(model, "hf_model_id", None) or model.key,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # OpenAI shape: choices[0].message.content + usage{prompt_tokens,...}
        text = ""
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            text = self._extract_text(data.get("output"))
        usage = data.get("usage") or {}
        in_tok = int(usage.get("prompt_tokens") or _estimate_tokens(prompt))
        out_tok = int(usage.get("completion_tokens") or _estimate_tokens(text))

        # Billing time: RunPod surfaces del/exec at the top level on the raw
        # serverless response; the OpenAI passthrough may omit them. Fall back to
        # measured wall-clock if absent (still a fair time-based estimate).
        delay_ms = int(data.get("delayTime", 0) or 0)
        exec_ms = int(data.get("executionTime", 0) or 0)
        if delay_ms == 0 and exec_ms == 0:
            # measured client-side as a fallback (over-counts slightly: includes
            # network) — acceptable and noted; native path gives exact numbers.
            exec_ms = int(resp.elapsed.total_seconds() * 1000)

        return InferenceResult(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            delay_ms=delay_ms,
            execution_ms=exec_ms,
            mocked=False,
        )

    async def _call_native(
        self, client, *, model, prompt, max_tokens, temperature
    ) -> InferenceResult:
        """Legacy native /runsync path (worker-specific `input` schema)."""
        url = f"{RUNPOD_BASE}/{model.endpoint_id}/runsync"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": {
                "prompt": prompt,
                "sampling_params": {
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            }
        }
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status in ("IN_QUEUE", "IN_PROGRESS"):
            data = await self._poll(client, model.endpoint_id, data["id"], headers)
        if data.get("status") != "COMPLETED":
            raise RuntimeError(f"RunPod job did not complete: {data.get('status')}")

        text = self._extract_text(data.get("output"))
        return InferenceResult(
            text=text,
            input_tokens=_estimate_tokens(prompt),
            output_tokens=_estimate_tokens(text),
            delay_ms=int(data.get("delayTime", 0)),
            execution_ms=int(data.get("executionTime", 0)),
            mocked=False,
        )

    async def _poll(self, client, endpoint_id, job_id, headers) -> dict:
        url = f"{RUNPOD_BASE}/{endpoint_id}/status/{job_id}"
        for _ in range(120):  # up to ~2 min
            await asyncio.sleep(1.0)
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            d = r.json()
            if d.get("status") in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"):
                return d
        raise RuntimeError("RunPod job polling timed out.")

    @staticmethod
    def _extract_text(output) -> str:
        # vLLM workers vary: output may be str, {"text": ...}, or a list of those.
        if output is None:
            return ""
        if isinstance(output, str):
            return output
        if isinstance(output, dict):
            return output.get("text") or output.get("output") or str(output)
        if isinstance(output, list) and output:
            first = output[0]
            if isinstance(first, dict):
                return first.get("text") or first.get("choices", [{}])[0].get("text", "") or str(first)
            return str(first)
        return str(output)
