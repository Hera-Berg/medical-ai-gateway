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
    text: str
    input_tokens: int
    output_tokens: int
    delay_ms: int
    execution_ms: int
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
            return await self._mock_generate(
                model=model, prompt=prompt, max_tokens=max_tokens
            )
        return await self._real_generate(
            model=model, prompt=prompt, max_tokens=max_tokens, temperature=temperature
        )

    async def _mock_generate(
        self, *, model: ModelDescriptor, prompt: str, max_tokens: int
    ) -> InferenceResult:
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        await asyncio.sleep(0.05)

        base_exec = {"RTX 4090 24GB": 900, "A100 40GB": 1400, "A100 80GB": 2600}.get(
            model.gpu_tier, 1200
        )
        execution_ms = base_exec + rng.randint(-200, 600)
        delay_ms = rng.choice([0, 0, 0, rng.randint(8000, 45000)])

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

    async def _real_generate(
        self,
        *,
        model: ModelDescriptor,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> InferenceResult:
        if not self._api_key:
            raise ValueError("RUNPOD_API_KEY not set but MOCK_INFERENCE=0.")
        if model.endpoint_id.startswith("REPLACE_"):
            raise ValueError(
                f"Model '{model.key}' has no real endpoint_id configured in models.yaml."
            )

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

        async with httpx.AsyncClient(timeout=120.0) as client:
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
        for _ in range(120):
            await asyncio.sleep(1.0)
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            d = r.json()
            if d.get("status") in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"):
                return d
        raise RuntimeError("RunPod job polling timed out.")

    @staticmethod
    def _extract_text(output) -> str:
        if output is None:
            return ""
        if isinstance(output, str):
            return output
        if isinstance(output, dict):
            return output.get("text") or output.get("output") or str(output)
        if isinstance(output, list) and output:
            first = output[0]
            if isinstance(first, dict):
                return (
                    first.get("text")
                    or first.get("choices", [{}])[0].get("text", "")
                    or str(first)
                )
            return str(first)
        return str(output)
