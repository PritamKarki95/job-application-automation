from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (personal internship tracker; manual review before every submission)"
TIMEOUT = 20


def new_job(**kw) -> dict:
    job = {"source": "", "company": "", "title": "", "location": "", "work_mode": "",
           "description": "", "required": "", "preferred": "", "dates": "",
           "url": "", "apply_url": "", "job_id": "", "posted": "", "flags": []}
    job.update({k: v for k, v in kw.items() if v is not None})
    return job


def html_to_text(raw: str) -> str:

    if not raw:
        return ""
    raw = html.unescape(raw)
    soup = BeautifulSoup(raw, "html.parser")
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
    for tag in soup.find_all(["p", "br", "div", "h1", "h2", "h3", "h4", "h5", "ul", "ol"]):
        tag.insert_after("\n")
    text = soup.get_text()
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


_REQ_HEAD = re.compile(
    r"^\s*(?:#+\s*)?(minimum qualifications|basic qualifications|required qualifications|requirements|"
    r"what you(?:'|’)ll need|what we(?:'|’)re looking for|you have|you should have|qualifications|"
    r"who you are|must have|required skills)\s*:?\s*$", re.I | re.M)
_PREF_HEAD = re.compile(
    r"^\s*(?:#+\s*)?(preferred qualifications|preferred|nice to have|nice-to-haves?|bonus points?|"
    r"bonus|it(?:'|’)s a plus if|plus(?:es)?|additional qualifications|preferred skills)\s*:?\s*$", re.I | re.M)
_ANY_HEAD = re.compile(r"^\s*(?:#+\s*)?[A-Z][A-Za-z ’'&/,-]{2,60}:?\s*$", re.M)


def _section_after(text: str, match: re.Match) -> str:
    start = match.end()
    rest = text[start:]

    for m in _ANY_HEAD.finditer(rest):
        line = m.group(0).strip()
        if line.startswith("-") or len(line.split()) > 7:
            continue
        if m.start() > 0:
            return rest[:m.start()].strip()
    return rest[:2500].strip()


def split_qualifications(text: str) -> tuple[str, str]:
    req = pref = ""
    m = _REQ_HEAD.search(text or "")
    if m:
        req = _section_after(text, m)
    m = _PREF_HEAD.search(text or "")
    if m:
        pref = _section_after(text, m)
    return req, pref


def detect_work_mode(location: str, text: str = "", hint: str = "") -> str:
    h = (hint or "").lower()
    if "remote" in h:
        return "Remote"
    if "hybrid" in h:
        return "Hybrid"
    if h in ("onsite", "on-site", "in office", "inperson"):
        return "Onsite"
    loc = (location or "").lower()
    if "hybrid" in loc:
        return "Hybrid"
    if "remote" in loc:
        return "Remote"
    body = (text or "").lower()
    if re.search(r"\bhybrid\b", body):
        return "Hybrid"
    if re.search(r"\b(fully remote|100% remote|remote-first|this (?:role|position|internship) is remote)\b", body):
        return "Remote"
    return "Onsite" if loc else "Unknown"


def extract_dates(text: str) -> str:
    pats = [
        r"((?:May|June|Jun)\s*\d{0,2},?\s*2027\s*(?:-|–|to|through)\s*(?:July|Jul|August|Aug|September|Sept?)\s*\d{0,2},?\s*2027)",
        r"(\d{1,2}\s*-\s*\d{1,2}\s*weeks?)",
        r"((?:summer|fall|spring|winter)\s*20\d\d)",
    ]
    for p in pats:
        m = re.search(p, text or "", re.I)
        if m:
            return m.group(1).strip()
    return ""


INTERN_RE = re.compile(r"\b(intern|interns|internship|co-?op)\b", re.I)
NOT_INTERN_RE = re.compile(r"\b(internal|international)\b", re.I)
SENIOR_RE = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director|head of|vp|architect)\b", re.I)
FULLTIME_RE = re.compile(r"\b(new grad|new graduate|full[- ]time|university grad|early career|entry level)\b", re.I)
GRAD_ONLY_RE = re.compile(r"\b(phd|ph\.d|doctoral|mba|master'?s)\b", re.I)

AI_TITLE_RE = re.compile(
    r"\b(machine learning|ml|ai|a\.i\.|artificial intelligence|applied ai|deep learning|nlp|"
    r"natural language|computer vision|llm|genai|generative ai|data scien\w*|ml ?ops|perception|research engineer)\b", re.I)
SWE_TITLE_RE = re.compile(
    r"\b(software|swe|developer|backend|back[- ]end|full[- ]?stack|frontend|front[- ]end|python|"
    r"platform|infrastructure|web|mobile|application|programmer|engineering intern|devops|cloud|systems)\b", re.I)
UNRELATED_RE = re.compile(
    r"\b(marketing|sales|finance|accounting|legal|recruit\w*|human resources|hr|design(?:er)?|ux|ui/ux|"
    r"mechanical|electrical|civil|chemical|hardware|supply chain|operations|business|communications|"
    r"content|social media|people|product manag\w*|program manag\w*|account|analyst)\b", re.I)


def classify_title(title: str) -> dict:
    t = title or ""
    is_intern = bool(INTERN_RE.search(t))
    ai = bool(AI_TITLE_RE.search(t))
    swe = bool(SWE_TITLE_RE.search(t))
    unrelated = bool(UNRELATED_RE.search(t)) and not (ai or re.search(r"\b(software|developer)\b", t, re.I))
    track = "ai" if ai else ("swe" if swe else None)
    return {
        "is_internship": is_intern,
        "is_senior": bool(SENIOR_RE.search(t)),
        "is_fulltime": bool(FULLTIME_RE.search(t)) and not is_intern,
        "grad_only": bool(GRAD_ONLY_RE.search(t)) and not re.search(r"\b(bachelor|undergrad)", t, re.I),
        "track": None if unrelated else track,
        "unrelated": unrelated or track is None,
    }


def check_timing(title: str, text: str, target_year: int = 2027) -> str:

    t = (title or "").lower()
    blob = f"{t}\n{(text or '').lower()}"
    if re.search(rf"summer\s*(?:of\s*)?{target_year}|{target_year}\s*summer", blob):
        return "match"
    term = r"\b(summer|fall|spring|winter)\s*(?:of\s*)?'?(20\d\d|\d\d)\b"

    for season, year in re.findall(term, t):
        y = int(year) if len(year) == 4 else 2000 + int(year)
        if y != target_year or season != "summer":
            return "incompatible"

    body_term = term + r"\s*(?:intern|internship|co-?op|program|cohort)"
    for season, year in re.findall(body_term, blob):
        y = int(year) if len(year) == 4 else 2000 + int(year)
        if y < target_year or (y == target_year and season != "summer"):
            return "incompatible"
    return "unknown"


CITIZEN_RE = re.compile(
    r"(u\.?s\.?\s*citizenship (?:is )?required|must be (?:a )?u\.?s\.?\s*citizen|"
    r"requires? (?:an? )?(?:active )?(?:secret|top secret|ts/sci|security) clearance|"
    r"only u\.?s\.?\s*citizens|itar)", re.I)
NO_SPONSOR_RE = re.compile(
    r"(not (?:able|willing) to sponsor|unable to (?:provide )?sponsor|will not sponsor|does not sponsor|"
    r"no (?:visa )?sponsorship|without (?:the need for )?(?:current or future )?sponsorship|"
    r"authorized to work in the (?:u\.?s\.?|united states) without)", re.I)
GRAD_YEAR_RE = re.compile(r"(?:graduat\w+|degree)[^.\n]{0,60}?\b(20\d\d)\b", re.I)
PHD_ONLY_RE = re.compile(r"(currently (?:enrolled in|pursuing) a (?:ph\.?d|doctoral|master'?s)[^.\n]*)", re.I)


def eligibility_flags(text: str, grad_year: int = 2028) -> tuple[list[str], list[str]]:

    hard, review = [], []
    t = text or ""
    if CITIZEN_RE.search(t):
        hard.append("Requires U.S. citizenship or a security clearance")
    if NO_SPONSOR_RE.search(t):
        review.append("Posting mentions sponsorship/work-authorization limits - check whether CPT/OPT qualifies")
    m = PHD_ONLY_RE.search(t)
    if m and not re.search(r"bachelor|undergrad|b\.?s\.?\b", t, re.I):
        hard.append("Graduate students only")
    years = {int(y) for y in GRAD_YEAR_RE.findall(t)}
    if years and grad_year not in years and all(y < grad_year for y in years) and max(years) >= 2026:
        review.append(f"Mentions graduation year(s) {sorted(years)} - you graduate in {grad_year}")
    return hard, review


def evaluate(job: dict, target_year: int = 2027, grad_year: int = 2028) -> tuple[bool, list[str]]:

    reasons = []
    c = classify_title(job.get("title", ""))
    if not c["is_internship"]:
        reasons.append("Not an internship")
    if c["is_senior"]:
        reasons.append("Senior-level title")
    if c["is_fulltime"]:
        reasons.append("Full-time / new-grad role")
    if c["grad_only"]:
        reasons.append("Graduate-degree internship")
    if c["unrelated"]:
        reasons.append("Not a software or AI/ML role")
    text = f"{job.get('description', '')}\n{job.get('required', '')}"
    if check_timing(job.get("title", ""), text, target_year) == "incompatible":
        reasons.append("Different term/year than Summer 2027")
    if not is_us_location(job.get("location", ""), job.get("work_mode", "")):
        reasons.append("Outside the United States")
    if job.get("expired"):
        reasons.append("Posting is closed")
    hard, review = eligibility_flags(text, grad_year)
    reasons.extend(hard)
    flags = list(job.get("flags") or [])
    for f in review:
        if f not in flags:
            flags.append(f)
    job["flags"] = flags
    return (not reasons), reasons


NON_US = re.compile(
    r"\b(canada|toronto|vancouver|montreal|ontario|united kingdom|\buk\b|london|england|ireland|dublin|"
    r"germany|berlin|munich|france|paris|netherlands|amsterdam|spain|madrid|india|bangalore|bengaluru|"
    r"hyderabad|pune|singapore|japan|tokyo|china|beijing|shanghai|australia|sydney|brazil|mexico|"
    r"poland|warsaw|israel|tel aviv|korea|seoul|philippines|emea|apac|latam|europe|switzerland|zurich|sweden|"
    r"stockholm|denmark|norway|finland|portugal|lisbon|italy|argentina|colombia|chile|costa rica|uae|dubai)\b", re.I)
US_STATE_RE = re.compile(
    r",\s*(AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|"
    r"NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b")


def is_us_location(location: str, work_mode: str = "") -> bool:
    loc = location or ""
    if not loc.strip():
        return True
    if NON_US.search(loc):

        return bool(re.search(r"\b(united states|usa|u\.s\.|remote - us)\b", loc, re.I) or US_STATE_RE.search(loc))
    return True


JOB_SITES = {"linkedin.com": "LinkedIn", "indeed.com": "Indeed", "glassdoor.com": "Glassdoor",
             "ziprecruiter.com": "ZipRecruiter", "joinhandshake.com": "Handshake",
             "simplyhired.com": "SimplyHired", "monster.com": "Monster", "wellfound.com": "Wellfound",
             "dice.com": "Dice"}


def job_site_name(url: str) -> str | None:
    host = urlparse(url or "").netloc.lower()
    for domain, name in JOB_SITES.items():
        if host == domain or host.endswith("." + domain):
            return name
    return None


def canonical_job_site_url(url: str) -> tuple[str, str]:

    u = urlparse(url)
    q = parse_qs(u.query)
    site = job_site_name(url) or ""
    if site == "LinkedIn":
        m = re.search(r"/jobs/view/(?:[^/]*?-)?(\d{6,})", u.path)
        jid = m.group(1) if m else (q.get("currentJobId") or [""])[0]
        if jid:
            return f"https://www.linkedin.com/jobs/view/{jid}", f"linkedin:{jid}"
    if site == "Indeed":
        jid = (q.get("jk") or q.get("vjk") or [""])[0]
        if jid:
            return f"https://www.indeed.com/viewjob?jk={jid}", f"indeed:{jid}"
    clean = urlunparse((u.scheme or "https", u.netloc.lower(), u.path.rstrip("/"), "", "", ""))
    return clean, ""

def detect_ats(url: str) -> tuple[str, dict]:

    u = urlparse(url)
    host = u.netloc.lower()
    parts = [p for p in u.path.split("/") if p]
    q = parse_qs(u.query)
    if "greenhouse.io" in host:
        if "embed" in parts:
            return "greenhouse", {"token": (q.get("for") or [""])[0], "id": (q.get("token") or [""])[0]}
        if "jobs" in parts:
            i = parts.index("jobs")
            if i >= 1 and i + 1 < len(parts):
                return "greenhouse", {"token": parts[i - 1], "id": parts[i + 1]}
        return "greenhouse", {}
    if "gh_jid" in q:
        return "greenhouse", {"token": "", "id": q["gh_jid"][0], "external": True}
    if host.endswith("lever.co"):
        if len(parts) >= 2:
            return "lever", {"company": parts[0], "id": parts[1]}
        return "lever", {}
    if "ashbyhq.com" in host:
        if len(parts) >= 2:
            return "ashby", {"company": parts[0], "id": parts[1]}
        return "ashby", {}
    if "myworkdayjobs.com" in host or "workday" in host:
        return "workday", {}
    return "generic", {}


def greenhouse_apply_url(token: str, job_id: str) -> str:
    return f"https://job-boards.greenhouse.io/{token}/jobs/{job_id}"


def from_greenhouse(token: str, raw: dict, company_name: str = "") -> dict:
    desc = html_to_text(raw.get("content", ""))
    loc = (raw.get("location") or {}).get("name", "")
    req, pref = split_qualifications(desc)
    jid = str(raw.get("id", ""))
    return new_job(
        source="greenhouse", company=company_name or raw.get("company_name") or token.replace("-", " ").title(),
        title=(raw.get("title") or "").strip(), location=loc, work_mode=detect_work_mode(loc, desc),
        description=desc, required=req, preferred=pref, dates=extract_dates(f"{raw.get('title', '')} {desc}"),
        url=raw.get("absolute_url") or greenhouse_apply_url(token, jid),
        apply_url=greenhouse_apply_url(token, jid), job_id=f"gh:{token}:{jid}",
        posted=(raw.get("first_published") or raw.get("updated_at") or "")[:10])


def from_lever(company: str, raw: dict) -> dict:
    parts = [raw.get("descriptionPlain") or ""]
    for lst in raw.get("lists") or []:
        parts.append(f"{lst.get('text', '')}:\n{html_to_text(lst.get('content', ''))}")
    parts.append(raw.get("additionalPlain") or "")
    desc = "\n\n".join(p for p in parts if p).strip()
    cats = raw.get("categories") or {}
    loc = cats.get("location") or ", ".join(cats.get("allLocations") or [])
    req, pref = split_qualifications(desc)
    posted = ""
    if raw.get("createdAt"):
        posted = datetime.fromtimestamp(raw["createdAt"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    hosted = raw.get("hostedUrl") or f"https://jobs.lever.co/{company}/{raw.get('id', '')}"
    return new_job(
        source="lever", company=company.replace("-", " ").title(), title=(raw.get("text") or "").strip(),
        location=loc, work_mode=detect_work_mode(loc, desc, raw.get("workplaceType", "")),
        description=desc, required=req, preferred=pref,
        dates=extract_dates(f"{raw.get('text', '')} {desc}"), url=hosted,
        apply_url=raw.get("applyUrl") or hosted.rstrip("/") + "/apply",
        job_id=f"lever:{company}:{raw.get('id', '')}", posted=posted)


def from_ashby(company: str, raw: dict) -> dict:
    desc = raw.get("descriptionPlain") or html_to_text(raw.get("descriptionHtml", ""))
    loc = raw.get("location") or ""
    if raw.get("isRemote") and "remote" not in loc.lower():
        loc = f"{loc} (Remote)".strip()
    req, pref = split_qualifications(desc)
    return new_job(
        source="ashby", company=company.replace("-", " ").title(), title=(raw.get("title") or "").strip(),
        location=loc, work_mode=detect_work_mode(loc, desc, raw.get("workplaceType", "")),
        description=desc, required=req, preferred=pref,
        dates=extract_dates(f"{raw.get('title', '')} {desc}"),
        url=raw.get("jobUrl", ""), apply_url=raw.get("applyUrl") or raw.get("jobUrl", ""),
        job_id=f"ashby:{company}:{raw.get('id', '')}", posted=(raw.get("publishedAt") or "")[:10])


def _get(url: str, **kw):
    return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, **kw)


def parse_job_url(url: str) -> dict:

    url = url.strip()
    if not re.match(r"https?://", url):
        raise ValueError("That doesn't look like a web address (it should start with https://).")
    if job_site_name(url):
        raise ValueError(f"{job_site_name(url)} pages can't be read automatically.")
    provider, info = detect_ats(url)
    try:
        if provider == "greenhouse" and info.get("token") and info.get("id"):
            r = _get(f"https://boards-api.greenhouse.io/v1/boards/{info['token']}/jobs/{info['id']}")
            if r.status_code == 404:
                raise ValueError("Greenhouse says this posting no longer exists (it may be closed).")
            r.raise_for_status()
            return from_greenhouse(info["token"], r.json())
        if provider == "lever" and info.get("company") and info.get("id"):
            r = _get(f"https://api.lever.co/v0/postings/{info['company']}/{info['id']}")
            if r.status_code == 404:
                raise ValueError("Lever says this posting no longer exists (it may be closed).")
            r.raise_for_status()
            return from_lever(info["company"], r.json())
        if provider == "ashby" and info.get("company"):
            r = _get(f"https://api.ashbyhq.com/posting-api/job-board/{info['company']}")
            r.raise_for_status()
            for raw in r.json().get("jobs", []):
                if raw.get("id") == info.get("id") or info.get("id", "-") in (raw.get("jobUrl") or ""):
                    return from_ashby(info["company"], raw)
            raise ValueError("Couldn't find that posting on the company's Ashby board (it may be closed).")
        r = _get(url)
        r.raise_for_status()
    except requests.RequestException as e:
        raise ValueError(f"Couldn't load the page ({e.__class__.__name__}). Check the link or your connection.")
    return from_generic_html(url, r.text, provider)


def from_generic_html(url: str, page_html: str, provider: str = "generic") -> dict:
    soup = BeautifulSoup(page_html, "html.parser")

    def meta(name):
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        return (tag.get("content") or "").strip() if tag else ""

    title = meta("og:title") or (soup.title.string.strip() if soup.title and soup.title.string else "")
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)
    company = meta("og:site_name") or urlparse(url).netloc.replace("www.", "").split(".")[0].title()
    for s in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        s.decompose()
    desc = html_to_text(str(soup.find("main") or soup.body or soup))[:15000]
    loc = ""
    m = re.search(r"Location\s*[:\n]\s*([^\n]{3,80})", desc)
    if m:
        loc = m.group(1).strip()
    req, pref = split_qualifications(desc)
    jid = ""
    q = parse_qs(urlparse(url).query)
    for key in ("gh_jid", "jobId", "job_id", "jid", "id"):
        if key in q:
            jid = f"{provider}:{q[key][0]}"
            break
    job = new_job(source=provider, company=company, title=title, location=loc,
                  work_mode=detect_work_mode(loc, desc), description=desc, required=req,
                  preferred=pref, dates=extract_dates(f"{title} {desc}"), url=url, apply_url=url, job_id=jid)
    if not desc.strip():
        job["flags"].append("Couldn't read the job description (page may need JavaScript) - review it in the browser")
    return job
