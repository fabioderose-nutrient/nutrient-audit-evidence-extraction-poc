import json
import shutil
import httpx
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, nutrient_engine, pipeline, templates, vlm_proxy
from .pricing import USD_PER_MILLION_TOKENS

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
WEB = ROOT / "web"
CATEGORIES = ("soc-reports", "invoices")

app = FastAPI(title="Nutrient audit evidence extraction")
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(vlm_proxy.router)


@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.on_event("startup")
def warm() -> None:
    threading.Thread(target=nutrient_engine.warmup, daemon=True).start()


def sample_path(category: str, name: str) -> Path:
    if category not in CATEGORIES:
        raise HTTPException(status_code=404, detail="unknown category")
    candidate = (SAMPLES / category / name).resolve()
    if not candidate.is_file() or SAMPLES not in candidate.parents:
        raise HTTPException(status_code=404, detail="sample not found")
    return candidate


def local_models() -> list[str]:
    try:
        tags = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=2.0).json()
        return sorted("ollama:" + m["name"] for m in tags.get("models", []))
    except Exception:
        return []


@app.get("/api/config")
def read_config() -> JSONResponse:
    return JSONResponse(
        {
            "web_sdk_license_key": config.NUTRIENT_WEB_SDK_LICENSE_KEY,
            "model": config.OPENAI_TEXT_MODEL,
            "models": sorted(USD_PER_MILLION_TOKENS) + local_models(),
            "pricing": USD_PER_MILLION_TOKENS,
            "openai_configured": bool(config.OPENAI_API_KEY),
            "samples": {
                category: sorted(p.name for p in (SAMPLES / category).glob("*") if p.is_file())
                for category in CATEGORIES
            },
        }
    )


@app.get("/api/templates")
def read_templates() -> JSONResponse:
    return JSONResponse({"classification_labels": templates.CLASSIFICATION_LABELS, "templates": templates.TEMPLATES})


@app.get("/api/sample/{category}/{name}")
def read_sample(category: str, name: str) -> FileResponse:
    return FileResponse(sample_path(category, name))


@app.get("/api/document/{doc_id}.pdf")
def read_document(doc_id: str) -> FileResponse:
    if not doc_id.isalnum():
        raise HTTPException(status_code=404)
    path = Path(config.WORK_DIR) / f"{doc_id}.pdf"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="document expired")
    return FileResponse(path, media_type="application/pdf")


@app.post("/api/process")
def process(
    template: str = Form(default="auto"),
    templates_json: str | None = Form(default=None),
    model: str | None = Form(default=None),
    engine: str = Form(default="auto"),
    category: str | None = Form(default=None),
    sample: str | None = Form(default=None),
    file: UploadFile | None = None,
) -> JSONResponse:
    catalog = templates.TEMPLATES
    if templates_json:
        try:
            catalog = json.loads(templates_json)
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=400, detail=f"templates_json is not valid JSON: {error}")
    if template != "auto" and template not in catalog:
        raise HTTPException(status_code=400, detail=f"unknown template '{template}'")

    temporary = False
    if file is not None and file.filename:
        suffix = Path(file.filename).suffix or ".pdf"
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        shutil.copyfileobj(file.file, handle)
        handle.close()
        source, name, temporary = Path(handle.name), file.filename, True
    elif category and sample:
        source, name = sample_path(category, sample), sample
    else:
        raise HTTPException(status_code=400, detail="no document provided")

    try:
        return JSONResponse(pipeline.run(source, name, template, catalog, model or config.OPENAI_TEXT_MODEL, engine))
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    finally:
        if temporary:
            source.unlink(missing_ok=True)


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
