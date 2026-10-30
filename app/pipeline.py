import shutil
import time
import uuid
from pathlib import Path

from nutrient_sdk import Document, VisionEngine

from . import config, nutrient_engine, templates, vlm_proxy
from .content import page_sizes, plain_text
from .structured import highlights, rows
from .usage import ledger

WORK = Path(config.WORK_DIR)
OFFICE = {".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".rtf", ".odt", ".txt", ".md", ".html"}
IMAGES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".heic"}


def to_pdf(source: Path, doc_id: str) -> tuple[Path, int]:
    WORK.mkdir(parents=True, exist_ok=True)
    target = WORK / f"{doc_id}.pdf"
    started = time.perf_counter()
    if source.suffix.lower() == ".pdf":
        shutil.copyfile(source, target)
    else:
        nutrient_engine.ensure_license()
        with Document.open(str(source)) as document:
            document.export_as_pdf(str(target))
    return target, round((time.perf_counter() - started) * 1000)


ENGINES = {"adaptive": VisionEngine.ADAPTIVE_OCR, "icr": VisionEngine.ICR, "vlm": VisionEngine.VLM_ENHANCED_ICR}


def pick_engine(engine: str, source: Path) -> VisionEngine:
    """auto: Office files converted by the SDK carry a clean text layer, so the fast text-layer
    engine is complete. PDFs and images of unknown origin go through the ICR vision model."""
    if engine in ENGINES:
        return ENGINES[engine]
    return VisionEngine.ADAPTIVE_OCR if source.suffix.lower() in OFFICE else VisionEngine.ICR


def run(source: Path, original_name: str, template_id: str, catalog: dict, model: str, engine: str = "auto") -> dict:
    doc_id = uuid.uuid4().hex
    pdf, convert_ms = to_pdf(source, doc_id)
    vision_engine = pick_engine(engine, source)

    parse_token = ledger.open() + ("-local" if model.startswith("ollama:") else "")
    content = nutrient_engine.extract_content(
        str(pdf), vision_engine, ai_endpoint=vlm_proxy.endpoint_for(parse_token), ai_model=model
    )
    parse_usage = ledger.close(parse_token)
    text = plain_text(content["content"])

    classification = None
    label = template_id
    if template_id == "auto":
        classification = nutrient_engine.classify(str(pdf), templates.CLASSIFICATION_LABELS, text)
        label = classification["classification"].get("predictedLabel", "other")

    template = catalog.get(label)
    if template is None:
        return {
            "document": _document(doc_id, original_name, source, pdf, content, convert_ms),
            "classification": classification and classification["classification"],
            "template": None,
            "attributes": [],
            "highlights": [],
            "usage": {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            "timings_ms": {"convert": convert_ms, "parse": content["elapsed_ms"],
                           "classify": classification["elapsed_ms"] if classification else 0, "extract": 0},
            "note": f"No extraction template for class '{label}'. Add one in the template editor.",
        }

    usage_token = ledger.open() + ("-local" if model.startswith("ollama:") else "")
    structured = nutrient_engine.extract_structured(
        str(pdf),
        vision_engine,
        templates.schema_from(template["attributes"]),
        template.get("instructions", ""),
        ai_endpoint=vlm_proxy.endpoint_for(usage_token),
        ai_model=model,
    )
    usage = ledger.close(usage_token)
    usage = {
        "calls": usage["calls"] + parse_usage["calls"],
        "input_tokens": usage["input_tokens"] + parse_usage["input_tokens"],
        "output_tokens": usage["output_tokens"] + parse_usage["output_tokens"],
        "cost_usd": round(usage["cost_usd"] + parse_usage["cost_usd"], 6),
    }
    field_rows = rows(structured["values"], structured["metadata"])
    by_name = {r["field"]: r for r in field_rows}
    pages = structured["pages"] or page_sizes(content["content"])

    attributes = []
    for attribute in template["attributes"]:
        row = by_name.get(attribute["name"])
        value = structured["values"].get(attribute["name"])
        attributes.append(
            {
                "name": attribute["name"],
                "value": value,
                "confidence": {
                    "parse": row["confidence"] if row else None,
                    "grounding": row["grounding"] if row else None,
                },
                "citation": (
                    {"page": row["page"], "bbox": row["bounds"]}
                    if row and row["bounds"]
                    else None
                ),
            }
        )

    return {
        "document": _document(doc_id, original_name, source, pdf, content, convert_ms, pages),
        "classification": classification and classification["classification"],
        "template": {"id": label, "label": template.get("label", label)},
        "attributes": attributes,
        "highlights": highlights(field_rows),
        "usage": {**usage, "model": model},
        "engine": structured["engine"],
        "timings_ms": {
            "convert": convert_ms,
            "parse": content["elapsed_ms"],
            "classify": classification["elapsed_ms"] if classification else 0,
            "extract": structured["elapsed_ms"],
        },
        "raw": {"values": structured["values"], "metadata": structured["metadata"]},
    }


def _document(doc_id, name, source: Path, pdf: Path, content, convert_ms, pages=None):
    return {
        "id": doc_id,
        "name": name,
        "source_format": source.suffix.lower().lstrip("."),
        "converted_to_pdf": source.suffix.lower() != ".pdf",
        "page_count": len(content["content"].get("metadata", [])),
        "pages": pages or page_sizes(content["content"]),
        "pdf_url": f"/api/document/{doc_id}.pdf",
        "bbox_units": "pixels in the page size listed under pages (scale to your renderer)",
    }
