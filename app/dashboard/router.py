from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["dashboard"])

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@router.get("/dashboard")
def dashboard_index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


@router.get("/dashboard/{asset_path:path}")
def dashboard_assets(asset_path: str) -> FileResponse:
    asset = _STATIC_DIR / asset_path
    if not asset.is_file():
        asset = _STATIC_DIR / "index.html"
    return FileResponse(asset)
