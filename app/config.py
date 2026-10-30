import os
import tempfile

# Empty license keys run the Nutrient SDKs in evaluation mode.
NUTRIENT_PYTHON_LICENSE_KEY = os.getenv("NUTRIENT_PYTHON_LICENSE_KEY", "").strip()
NUTRIENT_WEB_SDK_LICENSE_KEY = os.getenv("NUTRIENT_WEB_SDK_LICENSE_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8010,http://127.0.0.1:8010").split(",")
    if o.strip()
]
INTERNAL_VLM_PORT = int(os.getenv("PORT", "8010"))
METADATA_SCHEMA_VERSION = int(os.getenv("NUTRIENT_METADATA_SCHEMA", "2"))
VLM_FULL_PAGE = os.getenv("NUTRIENT_VLM_FULL_PAGE", "0") == "1"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
LOCAL_MAX_TOKENS = int(os.getenv("LOCAL_MAX_TOKENS", "1500"))
LOCAL_PRESENCE_PENALTY = float(os.getenv("LOCAL_PRESENCE_PENALTY", "0.6"))
WORK_DIR = os.getenv("WORK_DIR") or os.path.join(tempfile.gettempdir(), "nutrient-audit-evidence-poc")
