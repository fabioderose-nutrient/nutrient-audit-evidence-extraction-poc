import json
import threading
import time
from pathlib import Path

from nutrient_sdk import (
    ClassificationRequest,
    Document,
    License,
    StructuredExtractionRequest,
    Vision,
    VisionEngine,
    VlmProvider,
)

from . import config

_lock = threading.Lock()
_licensed = False

ENGINE_LABELS = {
    VisionEngine.ADAPTIVE_OCR: "OCR",
    VisionEngine.ICR: "ICR",
    VisionEngine.VLM_ENHANCED_ICR: "ICR + VLM",
}


def ensure_license() -> None:
    """Register the license key once. Without a key the SDK runs in evaluation mode."""
    global _licensed
    with _lock:
        if not _licensed:
            if config.NUTRIENT_PYTHON_LICENSE_KEY:
                License.register_key(config.NUTRIENT_PYTHON_LICENSE_KEY)
            _licensed = True


def _configure(document, engine: VisionEngine) -> None:
    vision = document.settings.vision_settings
    vision.engine = engine
    vision.provider = VlmProvider.CUSTOM
    vision.enable_vlm = engine is VisionEngine.VLM_ENHANCED_ICR


LOCAL_PREFIX = "ollama:"


def _configure_ai(document, endpoint: str, model: str) -> None:
    ai = document.settings.ai_processing_settings
    ai.ai_provider = VlmProvider.CUSTOM
    ai.endpoint = endpoint
    ai.api_key = config.OPENAI_API_KEY
    ai.model = model.removeprefix(LOCAL_PREFIX)
    ai.temperature = 0.0
    ai.include_confidence = True
    ai.include_source_locations = True
    ai.strict_structured_output = True
    ai.metadata_schema_version = config.METADATA_SCHEMA_VERSION
    ai.include_groundedness = config.METADATA_SCHEMA_VERSION == 2
    vlm = document.settings.custom_vlm_api_settings
    vlm.api_endpoint = endpoint
    vlm.api_key = config.OPENAI_API_KEY
    vlm.model = model.removeprefix(LOCAL_PREFIX)
    vlm.temperature = 0.0
    vlm.batch_size = 8
    vlm.max_concurrency = 4
    vlm.send_full_page_reference = config.VLM_FULL_PAGE


def warmup() -> None:
    """Load the ICR models once at startup (the first run downloads them)."""
    ensure_license()
    seed = sorted((Path(__file__).resolve().parent.parent / "samples" / "invoices").glob("*.pdf"))
    if not seed:
        return
    with Document.open(str(seed[0])) as document:
        _configure(document, VisionEngine.ICR)
        Vision.set(document).warmup()


def extract_content(path: str, engine: VisionEngine, ai_endpoint: str | None = None, ai_model: str | None = None) -> dict:
    ensure_license()
    started = time.perf_counter()
    with Document.open(path) as document:
        _configure(document, engine)
        if ai_endpoint and ai_model:
            _configure_ai(document, ai_endpoint, ai_model)
        payload = json.loads(Vision.set(document).extract_content())
    return {
        "engine": ENGINE_LABELS[engine],
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "content": payload,
    }


def require_openai(model: str = "") -> None:
    if model.startswith(LOCAL_PREFIX):
        return
    if not config.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set, so the steps that call OpenAI cannot run. "
            "Add it to .env and restart."
        )


def extract_structured(
    path: str,
    engine: VisionEngine,
    schema: dict,
    instructions: str,
    ai_endpoint: str,
    ai_model: str,
) -> dict:
    ensure_license()
    require_openai(ai_model)
    started = time.perf_counter()
    with Document.open(path) as document:
        _configure(document, engine)
        _configure_ai(document, ai_endpoint, ai_model)
        request = StructuredExtractionRequest()
        request.set_schema(json.dumps({"schema": schema}))
        request.set_instructions(instructions)
        payload = json.loads(Vision.set(document).extract_structured(request))
    return {
        "engine": ENGINE_LABELS[engine],
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "values": payload.get("extraction", payload),
        "metadata": payload.get("metadata") or {},
        "pages": payload.get("pages") or [],
    }


def classify(path: str, labels: dict[str, str], text: str | None = None) -> dict:
    ensure_license()
    started = time.perf_counter()
    with Document.open(path) as document:
        _configure(document, VisionEngine.ICR)
        if text:
            document.settings.document_classification_settings.text = text
        request = ClassificationRequest()
        for label, description in labels.items():
            request.add_candidate_label(label, description)
        payload = json.loads(Vision.set(document).classify(request))
    return {
        "engine": "ICR",
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "classification": payload.get("classification", payload),
    }
