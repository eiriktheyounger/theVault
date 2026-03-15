# routes/settings.py — simple settings get/set

from __future__ import annotations

import json
from typing import Any, Dict

import yaml
from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import APP_DIR

router = APIRouter()
SETTINGS_FILE = APP_DIR / "settings.json"

# Determine repository root to locate Vault/System/Config/models.yml
_root = APP_DIR.parents[2]
if not (_root / "Vault").exists():
    _root = APP_DIR.parents[3]
MODELS_FILE = _root / "Vault" / "System" / "Config" / "models.yml"


class SettingsBody(BaseModel):
    settings: Dict[str, Any] | None = None


@router.get("/settings")
def get_settings():
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text())
            return data
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return {"ok": True, "settings": {}}


@router.post("/settings")
def set_settings(body: SettingsBody):
    data = body.settings or {}
    SETTINGS_FILE.write_text(json.dumps({"ok": True, "settings": data}, indent=2))
    return {"ok": True, "settings": data}


@router.get("/api/config/models")
def get_models_config():
    if MODELS_FILE.exists():
        try:
            data = yaml.safe_load(MODELS_FILE.read_text()) or {}
            return data
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return {}


@router.put("/api/config/models")
def put_models_config(payload: Dict[str, Any] = Body(...)):
    data = payload or {}
    current: Dict[str, Any] = {}
    if MODELS_FILE.exists():
        try:
            current = yaml.safe_load(MODELS_FILE.read_text()) or {}
        except Exception:
            current = {}
    else:
        MODELS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Validate and update routes.fast and routes.ingest
    providers = current.get("providers", {})
    if "routes" in data:
        routes = current.setdefault("routes", {})
        for key in ("fast", "ingest"):
            if key in data["routes"]:
                models = data["routes"][key] or []
                invalid = [m for m in models if m not in providers]
                if invalid:
                    return JSONResponse(
                        {
                            "ok": False,
                            "error": f"unknown models for route '{key}': {', '.join(invalid)}",
                        },
                        status_code=400,
                    )
                routes[key] = models
        # Remove routes key so remaining top-level keys merge cleanly
        data = {k: v for k, v in data.items() if k != "routes"}

    current.update(data)
    MODELS_FILE.write_text(yaml.safe_dump(current, sort_keys=False))
    return current
