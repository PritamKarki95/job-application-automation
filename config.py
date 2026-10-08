from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("IA_DATA_DIR", BASE_DIR / "data"))
OUTPUT_DIR = Path(os.getenv("IA_OUTPUT_DIR", BASE_DIR / "outputs"))
RESUME_DIR = Path(os.getenv("IA_RESUME_DIR", BASE_DIR / "resumes"))
COMPANIES_FILE = BASE_DIR / "companies.json"

PROFILE_FILE = DATA_DIR / "profile.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
DB_FILE = DATA_DIR / "applications.db"

RESUMES = {
    "swe": RESUME_DIR / "software_developer.pdf",
    "ai": RESUME_DIR / "ai_ml_engineer.pdf",
}
RESUME_LABELS = {"swe": "Software Developer resume", "ai": "AI/ML Engineer resume"}

DEFAULT_SETTINGS = {
    "authorized_testing": False,
    "authorized_test_hosts": [],
    "daily_limit": 10,
    "min_score": 50,
    "max_display": 15,
    "community_read_limit": 45,
    "weights": {"skills": 40, "track": 25, "geo": 20, "timing": 15},
    "use_ollama": False,
    "ollama_url": os.getenv("OLLAMA_URL", "http://localhost:11434"),
    "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
    "fill_demographics": True,
    "browser_channel": "",
    "request_delay_seconds": 1.0,
    "target_season": "Summer 2027",
}


REQUIRED_PROFILE_FIELDS = ["first_name", "last_name", "email", "phone"]

DEFAULT_PROFILE = {
    "first_name": "",
    "last_name": "",
    "preferred_name": "",
    "email": "",
    "phone": "",
    "university": "",
    "degree": "Bachelor of Science",
    "major": "Computer Science",
    "graduation": "May 2028",
    "graduation_month": "05",
    "graduation_year": "2028",
    "github": "",
    "linkedin": "",
    "portfolio": "",


    "extra_links": [],
    "address": {"street": "", "city": "", "state": "", "zip": "", "country": "United States"},


    "projects": [],

    "experience": [],


    "work_authorization": {
        "status_note": "",
        "current_authorization_preference": "",
        "future_sponsorship_preference": "",
        "sponsorship_confirmed": False,
    },


    "demographics": {
        "race": "",
        "hispanic_latino": "",
        "veteran": "",
        "disability": "",
        "gender": "",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def ensure_dirs() -> None:
    for d in (DATA_DIR, OUTPUT_DIR, RESUME_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ! Could not read {path.name} ({e}); using defaults.")
        return {}


def _save_json(path: Path, data: dict) -> None:
    ensure_dirs()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_settings() -> dict:
    return _deep_merge(DEFAULT_SETTINGS, _load_json(SETTINGS_FILE))


def save_settings(settings: dict) -> None:
    _save_json(SETTINGS_FILE, settings)


def load_profile() -> dict:
    return _deep_merge(DEFAULT_PROFILE, _load_json(PROFILE_FILE))


def save_profile(profile: dict) -> None:
    _save_json(PROFILE_FILE, profile)


def missing_profile_fields(profile: dict) -> list[str]:
    return [f for f in REQUIRED_PROFILE_FIELDS if not str(profile.get(f, "")).strip()]


def full_name(profile: dict) -> str:
    return f"{profile.get('first_name', '').strip()} {profile.get('last_name', '').strip()}".strip()


def load_companies() -> dict:
    data = _load_json(COMPANIES_FILE)
    return {k: [c for c in data.get(k, []) if isinstance(c, str) and c.strip()]
            for k in ("greenhouse", "lever", "ashby")}
