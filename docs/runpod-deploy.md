# Deploying real models on RunPod Serverless

The app ships in **mock mode** (`MOCK_INFERENCE=1`): retrieval, provenance,
trace, and cost are all real, but answer text is simulated so you can build and
demo for $0. This guide flips models to **real** inference on RunPod Serverless.

## The lineup (an ungated size ladder)

The default `models.yaml` defines three models chosen to (a) span a real range
of size/cost and (b) be **ungated** — no HuggingFace access request, no token —
which avoids a whole class of deployment pain (see "Gotchas"):

| Model            | Size      | GPU       | Role                              |
| ---------------- | --------- | --------- | -------------------------------- |
| Qwen3 4B         | 4B        | 48GB A40  | fast / cheap — simple lookups    |
| Mistral 7B       | 7B        | 48GB A40  | balanced — general reasoning     |
| Qwen3 30B-A3B    | 30B (MoE) | 80GB A100 | strong — ~3B active params (MoE) |

You do **not** need all three. One model proves the entire live path; the
others can stay configured-but-undeployed (the selector shows them either way).

## Cost model

RunPod Serverless bills **per GPU-second of active compute**, with
**scale-to-zero**: an idle endpoint costs nothing. `cost = (delayTime +
executionTime) × per_second_usd`, where `delayTime` is the (billed) cold-start
delay. The first query after idle is slower and pricier (cold start); warm
queries are fast and cheap. That contrast is exactly what the cost dashboard
surfaces.

## Deploy one model (repeat per model)

1. RunPod console → **Serverless** → **New Endpoint** → **vLLM** (the official
   worker; it's OpenAI-compatible).
2. **Model**: the HuggingFace id, e.g. `Qwen/Qwen3-4B-Instruct-2507`.
3. **GPU**: 48GB (A40/L40S) for ≤8B; 80GB (A100) for the 30B.
4. **Env var — set this every time**: `MAX_MODEL_LEN=8192`. Without it vLLM
   tries to reserve KV cache for the model's full native context (often 128k+),
   which overflows the GPU and crashes the engine on startup. 8192 is plenty for
   RAG prompts.
5. **Idle Timeout**: `5` seconds (scale-to-zero = $0 idle).
6. **Max workers**: 1 (raise only for real concurrency).
7. Deploy and watch **Logs** until you see `vLLM engines initialized
   successfully` and the worker is **Running** (not dying with exit code 1).

## Wire it into the app

1. **Get the EXACT served model id.** vLLM lowercases the model name, so the id
   you must send rarely matches what you typed. Ask the worker:
   ```bash
   export RUNPOD_API_KEY=$(grep RUNPOD_API_KEY .env | cut -d= -f2)
   curl -s https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1/models \
     -H "Authorization: Bearer $RUNPOD_API_KEY"
   ```
   Copy the `id` field verbatim (e.g. `qwen/qwen3-4b-instruct-2507`).
2. In `backend/app/inference/models.yaml`, set both fields for that model:
   ```yaml
   qwen-4b:
     hf_model_id: "qwen/qwen3-4b-instruct-2507"   # exact served id
     endpoint_id: "your-endpoint-id"
   ```
3. In `.env`: `RUNPOD_API_KEY=...` and `MOCK_INFERENCE=0`.
4. Rebuild so both new code and new env load:
   ```bash
   docker compose up -d --build --force-recreate backend
   ```
5. Test (Low depth = one inference call, cheapest):
   ```bash
   curl -sS -X POST http://localhost:8090/api/query \
     -H 'Content-Type: application/json' \
     -d '{"question":"What is the HbA1c target for type 2 diabetes?","model_key":"qwen-4b","tier":"low"}'
   ```
   First call cold-starts (wait it out); the answer should be real and the
   "simulated" badge gone. Run it again for the warm/cheap path.

## Gotchas (learned the hard way)

- **Config changes need a rebuild.** Editing `.env` or `models.yaml` does
  nothing until `docker compose up -d --build --force-recreate backend`. A value
  hardcoded in `docker-compose.yml` overrides `.env`.
- **`MAX_MODEL_LEN` not set → engine-core crash on startup.** The #1 cause of a
  worker that deploys "Ready" but dies when it tries to serve. Always set 8192.
- **Model-name mismatch → 500 / "model does not exist".** Use the
  `/openai/v1/models` query above to get the exact (lowercased) id.
- **Gated models (Meta Llama) are a trap.** They need an `HF_TOKEN` *and* an
  approved access request. Worse: **regenerating your HF token instantly breaks
  every running endpoint that uses it** (they 401 on the next cold start). The
  ungated lineup above sidesteps all of this — prefer Qwen/Mistral.
- **FP8 needs Hopper.** FP8-quantized weights need an H100; an A100 lacks native
  FP8. On an A100, deploy the non-FP8 build.
- **Timeouts.** Cold starts can exceed default HTTP timeouts. The backend uses a
  600s read timeout and nginx a 620s `proxy_read_timeout` so a cold start isn't
  cut off mid-flight (which would waste billed GPU time).
- **OpenAI vs native path.** The client defaults to the OpenAI-compatible route
  (`/openai/v1/chat/completions`). If a worker only exposes the native handler,
  set `RUNPOD_API_STYLE=native` to use `/runsync` instead.

## When you're done

Scale-to-zero makes idle endpoints ~free, but to be certain of zero charges,
**delete the endpoint** in the RunPod console when finished. Set
`MOCK_INFERENCE=1` to return to $0 local mode.
