from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import config

STATUSES = ["Discovered", "Shortlisted", "Prepared", "Submitted", "Skipped", "Failed"]
TRANSITIONS = {
    "Discovered": {"Shortlisted", "Prepared", "Skipped", "Failed"},
    "Shortlisted": {"Prepared", "Skipped", "Failed", "Discovered"},
    "Prepared": {"Submitted", "Skipped", "Failed", "Shortlisted"},
    "Failed": {"Shortlisted", "Prepared", "Skipped", "Submitted"},
    "Skipped": {"Discovered", "Shortlisted", "Prepared"},
    "Submitted": set(),
}
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gh_src",
                   "lever-source", "lever-origin", "source", "ref", "src", "trk"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT, company TEXT NOT NULL, title TEXT NOT NULL,
    company_key TEXT, title_key TEXT,
    url TEXT, norm_url TEXT, apply_url TEXT, job_id TEXT,
    location TEXT, work_mode TEXT, description TEXT, required TEXT, preferred TEXT,
    dates TEXT, posted TEXT, flags TEXT DEFAULT '[]',
    score INTEGER, score_explain TEXT, resume TEXT, cover_letter TEXT,
    status TEXT NOT NULL DEFAULT 'Discovered',
    discovered_at TEXT, applied_at TEXT, updated_at TEXT, notes TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_norm_url ON jobs(norm_url);
CREATE INDEX IF NOT EXISTS ix_job_id ON jobs(job_id);
CREATE INDEX IF NOT EXISTS ix_company_title ON jobs(company_key, title_key);
"""


class TransitionError(ValueError):
    pass


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(path=None) -> sqlite3.Connection:
    config.ensure_dirs()
    conn = sqlite3.connect(str(path or config.DB_FILE))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def normalize_url(url: str) -> str:
    if not url:
        return ""
    u = urlparse(url.strip())
    host = u.netloc.lower().removeprefix("www.")
    path = re.sub(r"/(apply|application)/?$", "", u.path.rstrip("/"))
    q = sorted((k, v) for k, v in parse_qsl(u.query) if k.lower() not in TRACKING_PARAMS)
    return urlunparse(("https", host, path.lower(), "", urlencode(q), ""))


def norm_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\b(inc|llc|corp|corporation|co|ltd|the)\b\.?", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_title(s: str) -> str:
    s = norm_text(s)
    s = re.sub(r"\b(summer|fall|spring|winter)?\s*20\d\d\b", "", s)
    s = re.sub(r"\b(internship|interns)\b", "intern", s)
    return re.sub(r"\s+", " ", s).strip()


def find_duplicate(conn, job: dict):

    if job.get("job_id"):
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job["job_id"],)).fetchone()
        if row:
            return row
    urls = sorted({normalize_url(u) for u in (job.get("url"), job.get("apply_url")) if u})
    if urls:
        row = conn.execute(f"SELECT * FROM jobs WHERE norm_url IN ({','.join('?' * len(urls))})",
                           urls).fetchone()
        if row:
            return row
    ck, tk = norm_text(job.get("company")), norm_title(job.get("title"))
    if ck and tk:
        return conn.execute("SELECT * FROM jobs WHERE company_key = ? AND title_key = ?", (ck, tk)).fetchone()
    return None


def upsert_job(conn, job: dict, score: dict | None = None) -> tuple[int, bool]:

    existing = find_duplicate(conn, job)
    fields = {
        "source": job.get("source", ""), "company": job.get("company", ""), "title": job.get("title", ""),
        "company_key": norm_text(job.get("company")), "title_key": norm_title(job.get("title")),
        "url": job.get("url", ""), "norm_url": normalize_url(job.get("url") or job.get("apply_url")),
        "apply_url": job.get("apply_url") or job.get("url", ""), "job_id": job.get("job_id", ""),
        "location": job.get("location", ""), "work_mode": job.get("work_mode", ""),
        "description": job.get("description", ""), "required": job.get("required", ""),
        "preferred": job.get("preferred", ""), "dates": job.get("dates", ""), "posted": job.get("posted", ""),
        "flags": json.dumps(job.get("flags") or []), "updated_at": now(),
    }
    if score:
        fields.update(score=score["score"], score_explain=json.dumps(score["explanation"]), resume=score["resume"])
    if existing:
        if existing["status"] == "Submitted":

            return existing["id"], False

        for k in ("url", "norm_url", "apply_url", "job_id", "company_key", "title_key", "company", "title"):
            if existing[k]:
                fields.pop(k, None)
        sets = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", (*fields.values(), existing["id"]))
        conn.commit()
        return existing["id"], False
    fields.update(status="Discovered", discovered_at=now())
    cols = ", ".join(fields)
    cur = conn.execute(f"INSERT INTO jobs ({cols}) VALUES ({', '.join('?' * len(fields))})", tuple(fields.values()))
    conn.commit()
    return cur.lastrowid, True


def get_job(conn, job_pk: int):
    return conn.execute("SELECT * FROM jobs WHERE id = ?", (job_pk,)).fetchone()


def set_status(conn, job_pk: int, status: str, **extra) -> None:
    if status not in STATUSES:
        raise TransitionError(f"Unknown status {status!r}")
    row = get_job(conn, job_pk)
    if row is None:
        raise TransitionError(f"No job with id {job_pk}")
    cur = row["status"]
    if status != cur and status not in TRANSITIONS[cur]:
        raise TransitionError(f"Can't change status from {cur} to {status}")
    fields = {"status": status, "updated_at": now(), **extra}
    if status == "Submitted" and not row["applied_at"]:
        fields["applied_at"] = now()
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", (*fields.values(), job_pk))
    conn.commit()


def update_fields(conn, job_pk: int, **fields) -> None:
    fields["updated_at"] = now()
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE jobs SET {sets} WHERE id = ?", (*fields.values(), job_pk))
    conn.commit()


def submitted_today(conn) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    return conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'Submitted' AND substr(applied_at, 1, 10) = ?",
                        (today,)).fetchone()[0]


def list_jobs(conn, statuses=None, order="score DESC, discovered_at DESC", limit=200):
    if statuses:
        q = f"SELECT * FROM jobs WHERE status IN ({','.join('?' * len(statuses))}) ORDER BY {order} LIMIT ?"
        return conn.execute(q, (*statuses, limit)).fetchall()
    return conn.execute(f"SELECT * FROM jobs ORDER BY {order} LIMIT ?", (limit,)).fetchall()


def row_to_job(row) -> dict:
    d = dict(row)
    try:
        d["flags"] = json.loads(d.get("flags") or "[]")
    except json.JSONDecodeError:
        d["flags"] = []
    return d
