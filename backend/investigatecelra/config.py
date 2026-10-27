"""Runtime configuration for InvestigateCelra.

Every setting is an environment variable with a safe default so that the
application boots with zero configuration (`uvicorn` and go).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent.parent
DATA_DIR = BACKEND_DIR / "data"
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip())
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable settings snapshot, read once at import time."""

    app_name: str = "InvestigateCelra"
    tagline: str = "Life Sciences Commercial Intelligence Desk"
    classification: str = os.getenv("CLASSIFICATION_BANNER", "Confidential — Internal Use Only")

    # ---- storage -------------------------------------------------------
    database_url: str = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "var" / "investigatecelra.db"))

    # ---- data mode -----------------------------------------------------
    # live : the only mode. Every document in this system is fetched from a
    #        public source at runtime. There is no bundled corpus and no
    #        generated content anywhere in the repository.
    data_mode: str = "live"
    allow_network: bool = _env_bool("ALLOW_NETWORK", True)
    http_timeout: float = _env_float("HTTP_TIMEOUT", 12.0)
    http_user_agent: str = os.getenv(
        "HTTP_USER_AGENT",
        "InvestigateCelra/1.0 (Excelra commercial intelligence desk; contact: analytics@example.com)",
    )
    max_items_per_source: int = _env_int("MAX_ITEMS_PER_SOURCE", 40)
    refresh_interval_minutes: int = _env_int("REFRESH_INTERVAL_MINUTES", 0)  # 0 = manual only

    # ---- scoring knobs (documented in docs/ARCHITECTURE.md) ------------
    recency_half_life_days: float = _env_float("RECENCY_HALF_LIFE_DAYS", 9.0)
    edition_size: int = _env_int("EDITION_SIZE", 28)

    # ---- access gate ---------------------------------------------------
    access_code: str = os.getenv("ACCESS_CODE", "").strip()

    # ---- optional external graph ---------------------------------------
    neo4j_uri: str = os.getenv("NEO4J_URI", "").strip()

    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
        )
    )

    @property
    def db_path(self) -> Path:
        p = Path(self.database_url)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def gate_enabled(self) -> bool:
        return bool(self.access_code)


settings = Settings()
