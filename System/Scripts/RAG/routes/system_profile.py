"""System profile management API endpoints."""
from __future__ import annotations

import logging
import socket
from pathlib import Path
from typing import Dict, List, Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system-profile", tags=["system-profile"])


# ============================================================================
# Models
# ============================================================================


class SystemProfile(BaseModel):
    """A system profile configuration."""

    id: str
    name: str
    description: str
    config: Dict[str, Any]


class CurrentProfileResponse(BaseModel):
    """Current system profile response."""

    current_profile: str | None
    hostname: str
    available_profiles: List[str]
    config: Dict[str, Any]


class SetProfileRequest(BaseModel):
    """Request to set system profile."""

    profile_id: str


class SetProfileResponse(BaseModel):
    """Response from setting profile."""

    success: bool
    message: str
    profile_id: str
    config: Dict[str, Any]


# ============================================================================
# System Profiles
# ============================================================================

SYSTEM_PROFILES: Dict[str, SystemProfile] = {
    "macbook-pro": SystemProfile(
        id="macbook-pro",
        name="MacBook Pro",
        description="Eric's MacBook Pro work machine",
        config={
            "calendars": {
                "source": "Harmonic",
                "target": "Work",
            }
        },
    ),
    "mac-mini": SystemProfile(
        id="mac-mini",
        name="Mac Mini M4",
        description="Production Mac Mini server",
        config={
            "calendars": {
                "source": "Calendar",
                "target": "Work",
            }
        },
    ),
}


# ============================================================================
# Helper Functions
# ============================================================================


def get_config_paths() -> tuple[Path, Path]:
    """Get paths to config files."""
    base_path = Path.home() / "theVault"
    config_path = base_path / "config.yaml"
    local_path = base_path / "config.local.yaml"
    return config_path, local_path


def load_current_config() -> Dict:
    """Load current merged configuration."""
    config_path, local_path = get_config_paths()

    config = {}
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

    # Override with local config
    if local_path.exists():
        with open(local_path) as f:
            local_config = yaml.safe_load(f) or {}
            # Deep merge calendars
            if "calendars" in local_config:
                if "calendars" not in config:
                    config["calendars"] = {}
                config["calendars"].update(local_config["calendars"])

    return config


def detect_current_profile() -> str | None:
    """
    Auto-detect current system profile based on config.

    Returns profile ID or None if unknown.
    """
    current_config = load_current_config()
    current_source = current_config.get("calendars", {}).get("source")

    # Match to known profiles
    for profile_id, profile in SYSTEM_PROFILES.items():
        profile_source = profile.config.get("calendars", {}).get("source")
        if profile_source == current_source:
            return profile_id

    return None


def write_local_config(config: Dict) -> None:
    """Write configuration to config.local.yaml."""
    _, local_path = get_config_paths()

    # Ensure directory exists
    local_path.parent.mkdir(parents=True, exist_ok=True)

    # Write with nice formatting
    with open(local_path, "w") as f:
        f.write("# Machine-Specific Configuration Override\n")
        f.write("# This file is NOT tracked in git (.gitignore)\n")
        f.write("# Managed by System Profile selector in Workflows UI\n\n")
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Wrote config.local.yaml: {config}")


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/current", response_model=CurrentProfileResponse)
async def get_current_profile():
    """Get current system profile and configuration."""
    try:
        hostname = socket.gethostname()
        current_profile_id = detect_current_profile()
        current_config = load_current_config()

        return CurrentProfileResponse(
            current_profile=current_profile_id,
            hostname=hostname,
            available_profiles=list(SYSTEM_PROFILES.keys()),
            config=current_config,
        )
    except Exception as e:
        logger.error(f"Error getting current profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_profiles():
    """List all available system profiles."""
    try:
        return {
            "profiles": [
                {
                    "id": profile.id,
                    "name": profile.name,
                    "description": profile.description,
                }
                for profile in SYSTEM_PROFILES.values()
            ]
        }
    except Exception as e:
        logger.error(f"Error listing profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/set", response_model=SetProfileResponse)
async def set_profile(request: SetProfileRequest):
    """
    Set the system profile.

    This writes the profile's configuration to config.local.yaml.
    """
    try:
        profile_id = request.profile_id

        # Validate profile exists
        if profile_id not in SYSTEM_PROFILES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown profile: {profile_id}. Available: {list(SYSTEM_PROFILES.keys())}",
            )

        profile = SYSTEM_PROFILES[profile_id]

        # Write to config.local.yaml
        write_local_config(profile.config)

        # Verify by reloading
        new_config = load_current_config()

        return SetProfileResponse(
            success=True,
            message=f"System profile set to '{profile.name}'",
            profile_id=profile_id,
            config=new_config,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/reset")
async def reset_profile():
    """
    Reset to base configuration (delete config.local.yaml).

    After this, the system will use only config.yaml defaults.
    """
    try:
        _, local_path = get_config_paths()

        if local_path.exists():
            local_path.unlink()
            logger.info("Deleted config.local.yaml - reset to base config")
            message = "Reset to base configuration (config.local.yaml removed)"
        else:
            message = "Already using base configuration (no config.local.yaml)"

        current_config = load_current_config()

        return {
            "success": True,
            "message": message,
            "config": current_config,
        }

    except Exception as e:
        logger.error(f"Error resetting profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nas-status")
async def get_nas_status():
    """
    Get NAS mount status (Mac Mini only).

    Returns NAS mount status, vault symlink accessibility, and paths.
    Useful for Mac Mini to verify NAS is mounted before workflows.
    """
    try:
        nas_path = Path("/Volumes/home/MacMiniStorage")
        vault_symlink = Path.home() / "theVault" / "Vault"

        # Check NAS mount
        nas_mounted = nas_path.exists() and nas_path.is_dir()

        # Check vault symlink
        vault_exists = vault_symlink.exists()
        vault_is_symlink = vault_symlink.is_symlink() if vault_exists else False
        vault_target = None
        vault_accessible = False

        if vault_is_symlink:
            try:
                vault_target = str(vault_symlink.resolve())
                # Verify target is accessible and on NAS
                vault_accessible = (
                    Path(vault_target).exists() and
                    vault_target.startswith(str(nas_path))
                )
            except Exception as e:
                logger.warning(f"Could not resolve vault symlink: {e}")
                vault_accessible = False

        return {
            "nas_mounted": nas_mounted,
            "nas_path": str(nas_path),
            "vault_exists": vault_exists,
            "vault_is_symlink": vault_is_symlink,
            "vault_accessible": vault_accessible,
            "vault_target": vault_target,
            "hostname": socket.gethostname(),
        }

    except Exception as e:
        logger.error(f"Error checking NAS status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
