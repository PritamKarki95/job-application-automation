from __future__ import annotations

import time
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

import config
from job_parser import USER_AGENT, evaluate, from_ashby, from_greenhouse, from_lever

COMMUNITY_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"

PROMINENT_EMPLOYERS = {"google", "alphabet", "amazon", "amazonwebservices", "microsoft", "meta", "apple",
                       "nvidia", "tesla", "netflix", "salesforce", "oracle", "ibm", "palantir",
                       "jpmorganchase", "goldmansachs", "capitalone", "walmart"}


def employer_key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def community_candidates(records, target_season):

    from job_parser import detect_work_mode, new_job
    jobs = []
    seen = set()
    for raw in records:
        if not isinstance(raw, dict) or raw.get("active") is not True or raw.get("is_visible") is False:
            continue
        terms = raw.get("terms") or []
        if terms and target_season not in terms and "N/A" not in terms:
            continue
        url = raw.get("url", "")
        if not isinstance(url, str) or urlparse(url).scheme not in ("https", "http") or not urlparse(url).netloc or url in seen:
            continue
        if not raw.get("company_name") or not raw.get("title"):
            continue
        seen.add(url)
        term = target_season if target_season in terms else ""
        sponsorship = raw.get("sponsorship") or ""
        if sponsorship == "Does Not Offer Sponsorship":
            sponsorship = "No visa sponsorship; check CPT/OPT eligibility with the employer."
        degrees = raw.get("degrees") or []
        metadata = "\n".join(filter(None, [f"Listed term: {term}" if term else "", sponsorship,
                                           "Degrees: " + ", ".join(degrees) if degrees else ""]))
        if degrees and all(re.search(r"master|ph\.?d|doctor", degree, re.I) for degree in degrees):
            metadata += "\nCurrently pursuing a PhD or master's degree."
        locations = raw.get("locations") or []
        location = "; ".join(locations)
        posted = ""
        try:
            posted = datetime.fromtimestamp(raw.get("date_posted", 0), timezone.utc).date().isoformat()
        except (ValueError, TypeError, OSError):
            pass
        job = new_job(source="community", company=raw["company_name"], title=raw["title"],
                      url=url, apply_url=url, location=location, work_mode=detect_work_mode(location, ""),
                      dates=term, description=metadata, posted=posted)
        job["feed_metadata"] = metadata
        jobs.append(job)
    return jobs


def discover_community(settings, resume_info, progress=print):

    from job_parser import parse_job_url
    from matcher import geo_tier
    season = settings.get("target_season", "Summer 2027")
    target_year = int(str(season)[-4:])
    progress("Reading the Simplify/Pitt CSC public internship feed...")
    try:
        records = _get_json(COMMUNITY_URL)
        if not isinstance(records, list):
            raise ValueError("expected a list of internship records")
    except (requests.RequestException, LookupError, ValueError) as exc:
        return {"kept": [], "rejected": [], "report": [("community", "Simplify/Pitt CSC", str(exc), 0, 0)]}
    configured = {employer_key(name) for boards in config.load_companies().values() for name in boards}
    prominent = PROMINENT_EMPLOYERS | configured
    candidates, rejected = [], []
    for job in community_candidates(records, season):
        ok, reasons = evaluate(job, target_year=target_year)
        if ok:
            candidates.append(job)
        else:
            rejected.append((job, reasons))


    candidates.sort(key=lambda job: job.get("posted", ""), reverse=True)
    candidates.sort(key=lambda job: (employer_key(job["company"]) in prominent,
                                    geo_tier(job["location"], job["work_mode"])[0]))
    limit = max(1, int(settings.get("community_read_limit", 45)))
    kept, failures = [], 0
    for n, candidate in enumerate(candidates[:limit], 1):
        progress(f"  [{n}/{min(limit, len(candidates))}] Reading {candidate['company']}: {candidate['title']}")
        try:
            posting = parse_job_url(candidate["apply_url"])
            if not (posting.get("description") or "").strip():
                raise ValueError("no readable job description")
            posting["company"] = candidate["company"]
            posting["title"] = posting.get("title") or candidate["title"]
            posting["source"] = "community"
            posting["posted"] = candidate["posted"]
            posting["dates"] = posting.get("dates") or candidate["dates"]
            posting["location"] = posting.get("location") or candidate["location"]
            posting["work_mode"] = posting.get("work_mode") or candidate["work_mode"]
            posting["description"] += "\n\n" + candidate["feed_metadata"]
            ok, reasons = evaluate(posting, target_year=target_year)
            if ok:
                kept.append(posting)
            else:
                rejected.append((posting, reasons))
        except ValueError as exc:
            failures += 1
            progress(f"    Skipped: {exc}")
        delay = float(settings.get("request_delay_seconds", 1))
        if delay:
            time.sleep(delay)
    progress(f"{len(candidates)} feed candidates passed initial filters; checked up to {limit} employer pages.")
    if failures:
        progress(f"{failures} pages could not be read; they were not ranked as resume matches.")
    return {"kept": kept, "rejected": rejected,
            "report": [("community", "Simplify/Pitt CSC", "ok", len(records), len(kept))]}

TIMEOUT = 25


def _get_json(url: str):
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    if r.status_code == 404:
        raise LookupError("board not found (check the name in companies.json)")
    if r.status_code == 429:
        raise LookupError("rate-limited by the site - try again later")
    r.raise_for_status()
    return r.json()


def fetch_greenhouse(token: str) -> list[dict]:
    data = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
    name = ""
    try:
        name = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}").get("name", "")
    except Exception:
        pass
    return [from_greenhouse(token, j, name) for j in data.get("jobs", [])]


def fetch_lever(company: str) -> list[dict]:
    data = _get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
    return [from_lever(company, j) for j in (data if isinstance(data, list) else [])]


def fetch_ashby(company: str) -> list[dict]:
    data = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{company}")
    return [from_ashby(company, j) for j in data.get("jobs", []) if j.get("isListed", True)]


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}


def discover(settings: dict, companies: dict | None = None, progress=print) -> dict:


    companies = companies if companies is not None else config.load_companies()
    target_year = int(str(settings.get("target_season", "Summer 2027"))[-4:])
    delay = float(settings.get("request_delay_seconds", 1.0))
    kept, rejected, report = [], [], []
    total = sum(len(v) for v in companies.values())
    n = 0
    for source, boards in companies.items():
        fetch = FETCHERS.get(source)
        if not fetch:
            continue
        for board in boards:
            n += 1
            progress(f"  [{n}/{total}] {source}: {board} ...")
            try:
                jobs = fetch(board)
            except LookupError as e:
                report.append((source, board, str(e), 0, 0))
                continue
            except requests.RequestException as e:
                report.append((source, board, f"network error ({e.__class__.__name__})", 0, 0))
                continue
            except ValueError:
                report.append((source, board, "unexpected response (not JSON)", 0, 0))
                continue
            k = 0
            for job in jobs:
                ok, reasons = evaluate(job, target_year=target_year)
                if ok:
                    kept.append(job)
                    k += 1
                elif "Not an internship" not in reasons:
                    rejected.append((job, reasons))
            report.append((source, board, "ok", len(jobs), k))
            if delay:
                time.sleep(delay)
    return {"kept": kept, "rejected": rejected, "report": report}
