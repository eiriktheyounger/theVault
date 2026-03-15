from __future__ import annotations

import os
from pathlib import Path

# --- App root (this file is .../System/Scripts/RAG/config.py) -----------------
THIS_FILE = Path(__file__).resolve()
ROOT_DIR: Path = THIS_FILE.parents[3]  # project root
SYSTEM_DIR: Path = ROOT_DIR / "System"
SCRIPTS_DIR: Path = SYSTEM_DIR / "Scripts"
CONFIG_DIR: Path = SYSTEM_DIR / "Config"
CONTRACTS_DIR: Path = SYSTEM_DIR / "Contracts"
REFERENCE_DIR: Path = SYSTEM_DIR / "Reference"
VAULT_DIR: Path = ROOT_DIR / "Vault"
VAULT_ROOT: Path = Path(os.getenv("VAULT_ROOT", VAULT_DIR))

# Ensure key dirs exist
for p in [
    SYSTEM_DIR,
    SCRIPTS_DIR,
    CONFIG_DIR,
    CONTRACTS_DIR,
    REFERENCE_DIR,
    VAULT_DIR,
    VAULT_ROOT,
]:
    try:
        # resolve() follows symlinks before mkdir to avoid FileExistsError on symlinks
        p.resolve().mkdir(parents=True, exist_ok=True)
    except (FileExistsError, OSError):
        # Directory exists or symlink path issue - safe to continue
        pass

CHATS_BASE: Path = VAULT_ROOT / "System" / "Ops" / "Chats"
try:
    CHATS_BASE.resolve().mkdir(parents=True, exist_ok=True)
except (FileExistsError, OSError):
    pass
PINS_FILE: Path = CHATS_BASE / "_pins.json"


# --- Small helper -------------------------------------------------------------
def _env_bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, "1" if default else "0")).strip().lower() in (
        "1",
        "true",
        "t",
        "yes",
        "y",
        "on",
    )


# --- Logging -----------------------------------------------------------------
LOGS_DIR: Path = ROOT_DIR / "System" / "Logs"
try:
    LOGS_DIR.resolve().mkdir(parents=True, exist_ok=True)
except (FileExistsError, OSError):
    pass
LOG_DIR: Path = LOGS_DIR  # legacy alias some modules import
LOG_FILE: Path = Path(os.getenv("LOG_FILE", LOGS_DIR / "app.log"))
GLOSSARY_LOG_FILE: Path = Path(os.getenv("GLOSSARY_LOG_FILE", LOGS_DIR / "glossary.log"))

STRUCTLOG_ENABLED: bool = _env_bool("STRUCTLOG_ENABLED", False)
# Some modules import LOG_PATH specifically
LOG_PATH: Path = Path(os.getenv("LOG_PATH", LOG_FILE))

# --- Feature flags / toggles -------------------------------------------------
FORCE_NO_ABSTAIN_FAST: bool = _env_bool("FORCE_NO_ABSTAIN_FAST", False)
FORCE_NO_ABSTAIN_DEEP: bool = _env_bool("FORCE_NO_ABSTAIN_DEEP", False)

# Firebase toggles preserved for compatibility
USE_FIREBASE: bool = _env_bool("USE_FIREBASE", False)
FIREBASE_PROJECT_ID: str | None = os.getenv("FIREBASE_PROJECT_ID")
FIREBASE_API_KEY: str | None = os.getenv("FIREBASE_API_KEY")

# --- RAG data paths ----------------------------------------------------------
APP_DIR: Path = THIS_FILE.parent
RAG_DATA_DIR: Path = Path(os.getenv("RAG_DATA_DIR", APP_DIR / "rag_data"))
try:
    RAG_DATA_DIR.resolve().mkdir(parents=True, exist_ok=True)
except (FileExistsError, OSError):
    pass

DB_PATH: Path = Path(os.getenv("DB_PATH", RAG_DATA_DIR / "chunks.sqlite3"))
HNSW_PATH: Path = Path(os.getenv("HNSW_PATH", RAG_DATA_DIR / "chunks_hnsw.bin"))
META_CSV_PATH: Path = Path(os.getenv("META_CSV_PATH", RAG_DATA_DIR / "meta.csv"))

# --- Models / backends -------------------------------------------------------
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

FAST_MODEL: str = os.getenv("FAST_MODEL", "phi3:mini")
DEEP_MODEL: str = os.getenv("DEEP_MODEL", "llama3.1:8b")
INGEST_MODEL: str = os.getenv(
    "INGEST_MODEL", "mixtral:latest"
)  # Prioritize accuracy over speed for ingest

# Some code expects a single 'LLM_MODEL_NAME'
LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", DEEP_MODEL)

EMBED_MODEL: str = os.getenv("EMBED_MODEL", "nomic-embed-text:latest")
NOMIC_EMBED_MODEL: str = os.getenv("NOMIC_EMBED_MODEL", EMBED_MODEL)
NOMIC_EMBED_DIM: int = int(os.getenv("NOMIC_EMBED_DIM", "768"))

ST_EMBED_MODEL: str = os.getenv("ST_EMBED_MODEL", "all-MiniLM-L6-v2")
ST_EMBED_DIM: int = int(os.getenv("ST_EMBED_DIM", "384"))

VECTOR_BACKEND: str = os.getenv("VECTOR_BACKEND", "brute")

# --- Inboxes expected by tests & scripts -------------------------------------
INBOX_ROOT: Path = ROOT_DIR / "Inbox"
PROCESSED_ROOT: Path = VAULT_DIR / "Processed"

try:
    from ..config import INBOX_PLAUD_MD as _PLAUD_INBOX_PATH
except Exception:  # pragma: no cover - fall back to default path
    _PLAUD_INBOX_PATH = INBOX_ROOT / "Plaud" / "MarkdownOnly"

PLAUD_MD_ONLY_INBOX: Path = Path(_PLAUD_INBOX_PATH)
AUDIO_INBOX: Path = INBOX_ROOT / "audio"
EML_INBOX: Path = INBOX_ROOT / "eml"
WORD_INBOX: Path = INBOX_ROOT / "word"
PDF_INBOX: Path = INBOX_ROOT / "pdf"
IMAGES_INBOX: Path = INBOX_ROOT / "images"
# Processed locations some code refers to


def _mirrored_processed_path(inbox_path: Path) -> Path:
    path = Path(inbox_path)
    try:
        relative = path.relative_to(INBOX_ROOT)
    except ValueError:
        try:
            relative = path.resolve().relative_to(INBOX_ROOT.resolve())
        except Exception:  # pragma: no cover - inbox outside standard tree
            relative = Path("Plaud") / "MarkdownOnly"
    return PROCESSED_ROOT / relative


PLAUD_PROCESSED: Path = _mirrored_processed_path(PLAUD_MD_ONLY_INBOX)
EML_PROCESSED: Path = PROCESSED_ROOT / "eml"

for d in [
    INBOX_ROOT,
    PROCESSED_ROOT,
    PLAUD_MD_ONLY_INBOX,
    AUDIO_INBOX,
    EML_INBOX,
    WORD_INBOX,
    PDF_INBOX,
    IMAGES_INBOX,
    PLAUD_PROCESSED,
]:
    try:
        d.resolve().mkdir(parents=True, exist_ok=True)
    except (FileExistsError, OSError):
        pass

# --- Tags / glossary files ---------------------------------------------------
TAG_REGISTRY: Path = CONFIG_DIR / "tags.yaml"
if not TAG_REGISTRY.exists():
    TAG_REGISTRY.write_text("tags: []\n", encoding="utf-8")
MAX_TAGS: int = int(os.getenv("MAX_TAGS", "10"))

# Some helpers expect a glossary YAML file path
# Glossary paths (Vault-based markdown)
GLOSSARY_DIR: Path = VAULT_ROOT / "System"
try:
    # resolve() follows symlinks before mkdir to avoid FileExistsError on symlinks
    GLOSSARY_DIR.resolve().mkdir(parents=True, exist_ok=True)
except (FileExistsError, OSError):
    # Directory exists or symlink path issue - safe to continue
    pass
GLOSSARY_MD: Path = GLOSSARY_DIR / "glossary.md"
OLD_GLOSSARY_MD: Path = GLOSSARY_DIR / "OLD_glossary.md"
# Backwards-compat alias expected by some modules/tests
GLOSSARY_PATH: Path = GLOSSARY_MD
GLOSSARY_FILE: Path = GLOSSARY_MD
if not GLOSSARY_MD.exists():
    GLOSSARY_MD.write_text("# Glossary\n\n", encoding="utf-8")

# --- Model/token budgets used by transcript chunker --------------------------
MODEL_CTX_TOKENS: int = int(os.getenv("MODEL_CTX_TOKENS", "8192"))
RESPONSE_BUDGET_TOKENS: int = int(os.getenv("RESPONSE_BUDGET_TOKENS", "2048"))


# --- Spec path helper expected by tests --------------------------------------
def get_spec_path(relative_path: str = "") -> str:
    base = REFERENCE_DIR
    return str((base / relative_path).resolve())


# --- Legacy aliases (do not remove; other modules import these names) --------
RAG_DIR = RAG_DATA_DIR
SQLITE_PATH = SQLITE_DB = CHUNKS_DB = RAG_DB_PATH = DB_PATH
HNSW_INDEX = INDEX_PATH = HNSW_PATH

NS_EMBED_MODEL = EMBED_MODEL
EMBED_DIM = NOMIC_EMBED_DIM

# Export surface used by various tests
__all__ = [
    "ROOT_DIR",
    "VAULT_DIR",
    "VAULT_ROOT",
    "SYSTEM_DIR",
    "CONFIG_DIR",
    "CONTRACTS_DIR",
    "REFERENCE_DIR",
    "LOGS_DIR",
    "LOG_DIR",
    "LOG_FILE",
    "LOG_PATH",
    "GLOSSARY_LOG_FILE",
    "TAG_REGISTRY",
    "MAX_TAGS",
    "INBOX_ROOT",
    "PROCESSED_ROOT",
    "PLAUD_MD_ONLY_INBOX",
    "PLAUD_PROCESSED",
    "AUDIO_INBOX",
    "EML_INBOX",
    "WORD_INBOX",
    "PDF_INBOX",
    "IMAGES_INBOX",
    "get_spec_path",
    "GLOSSARY_FILE",
    "CHATS_BASE",
    "PINS_FILE",
    # existing RAG bits:
    "RAG_DATA_DIR",
    "DB_PATH",
    "HNSW_PATH",
    "META_CSV_PATH",
    "FAST_MODEL",
    "DEEP_MODEL",
    "INGEST_MODEL",
    "LLM_MODEL_NAME",
    "EMBED_MODEL",
    "NOMIC_EMBED_MODEL",
    "NOMIC_EMBED_DIM",
    "ST_EMBED_MODEL",
    "ST_EMBED_DIM",
    "VECTOR_BACKEND",
    "OLLAMA_HOST",
    "FORCE_NO_ABSTAIN_FAST",
    "FORCE_NO_ABSTAIN_DEEP",
    "USE_FIREBASE",
    "FIREBASE_PROJECT_ID",
    "FIREBASE_API_KEY",
    "STRUCTLOG_ENABLED",
    "MODEL_CTX_TOKENS",
    "RESPONSE_BUDGET_TOKENS",
    # legacy aliases:
    "RAG_DIR",
    "SQLITE_DB",
    "HNSW_INDEX",
    "NS_EMBED_MODEL",
    "EMBED_DIM",
]
# --- Prompts ---------------------------------------------------------------
PROMPTS_DIR: Path = CONFIG_DIR / "prompts"
try:
    PROMPTS_DIR.resolve().mkdir(parents=True, exist_ok=True)
except (FileExistsError, OSError):
    pass
DEFAULT_PROMPT_PATH: Path = Path(
    os.getenv("DEFAULT_PROMPT_PATH", PROMPTS_DIR / "default_prompt.txt")
)
if not DEFAULT_PROMPT_PATH.exists():
    DEFAULT_PROMPT_PATH.write_text(
        "You are a helpful assistant. Summarize clearly and concisely.\n", encoding="utf-8"
    )

# --- Generic notes dir used by several scripts -----------------------------
GENERIC_NOTES_DIR: Path = VAULT_DIR / "Notes"
try:
    GENERIC_NOTES_DIR.resolve().mkdir(parents=True, exist_ok=True)
except (FileExistsError, OSError):
    pass

# --- Inboxes/Processed (compatibility aliases) -----------------------------
# Some modules expect singular IMAGE_INBOX and a processed path for images.
IMAGE_INBOX: Path = IMAGES_INBOX
IMAGE_PROCESSED: Path = PROCESSED_ROOT / "images"
try:
    IMAGE_PROCESSED.resolve().mkdir(parents=True, exist_ok=True)
except (FileExistsError, OSError):
    pass

# Keep export list up to date
try:
    __all__  # type: ignore[name-defined]
except NameError:
    __all__ = []

for _name in [
    "DEFAULT_PROMPT_PATH",
    "PROMPTS_DIR",
    "GENERIC_NOTES_DIR",
    "IMAGE_INBOX",
    "IMAGE_PROCESSED",
]:
    if _name not in __all__:
        __all__.append(_name)

# --- Markdown inbox/processed (used by process_markdown and API tests) -----
try:
    __all__  # type: ignore[name-defined]
except NameError:
    __all__ = []

# Where incoming .md files are dropped
MARKDOWN_INBOX: Path = INBOX_ROOT / "markdown"
try:
    MARKDOWN_INBOX.resolve().mkdir(parents=True, exist_ok=True)
except (FileExistsError, OSError):
    pass

# Where processed .md files get moved
MARKDOWN_PROCESSED: Path = PROCESSED_ROOT / "markdown"
try:
    MARKDOWN_PROCESSED.resolve().mkdir(parents=True, exist_ok=True)
except (FileExistsError, OSError):
    pass

# export
for _name in ["MARKDOWN_INBOX", "MARKDOWN_PROCESSED"]:
    if _name not in __all__:
        __all__.append(_name)
