import asyncio
import json
import time

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from . import config
from .usage import ledger

router = APIRouter()

UPSTREAM = "https://api.openai.com/v1/chat/completions"
LOCAL_PREFIX = "ollama:"


@router.post("/internal/vlm/{usage_token}/v1/chat/completions")
async def chat_completions(usage_token: str, request: Request):
    if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="internal endpoint")
    body = await request.json()
    model = body.get("model", "")
    if model.startswith(LOCAL_PREFIX) or usage_token.endswith("-local"):
        # Local model served by Ollama (OpenAI-compatible). Nothing leaves the machine.
        body["model"] = model.removeprefix(LOCAL_PREFIX)
        body.pop("logprobs", None)
        body.pop("top_logprobs", None)
        # The SDK sets no max_tokens. A small model can loop inside the grammar-constrained
        # citation arrays and run to the context limit, blocking Ollama's single slot for minutes.
        body.setdefault("max_tokens", config.LOCAL_MAX_TOKENS)
        # Measured on qwen2.5:7b: without it the model repeats a citation string until the
        # token cap; with it the same request returns valid JSON in ~20 s.
        body.setdefault("presence_penalty", config.LOCAL_PRESENCE_PENALTY)
        url, headers = f"{config.OLLAMA_URL}/v1/chat/completions", {"Content-Type": "application/json"}
    else:
        url, headers = UPSTREAM, {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
    started = time.perf_counter()

    async def forward():
        async with httpx.AsyncClient(timeout=1200.0) as client:
            return await client.post(url, json=body, headers=headers)

    # shield: if the SDK gives up and closes its connection, the upstream call still completes.
    # Ollama's runner wedges permanently when a client disconnects mid-generation.
    upstream = await asyncio.shield(asyncio.ensure_future(forward()))
    payload = upstream.json()
    usage = payload.get("usage") or {}
    if usage:
        ledger.record(
            usage_token,
            (LOCAL_PREFIX + model.removeprefix(LOCAL_PREFIX)) if url != UPSTREAM else payload.get("model", body.get("model", "")),
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )
    return JSONResponse(payload, status_code=upstream.status_code)


def endpoint_for(usage_token: str) -> str:
    return f"http://127.0.0.1:{config.INTERNAL_VLM_PORT}/internal/vlm/{usage_token}/v1"
