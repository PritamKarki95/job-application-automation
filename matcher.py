from __future__ import annotations

import json
import re
from pathlib import Path

import config


SKILLS = {
    "Python": r"python", "Java": r"java(?!script)", "C++": r"c\+\+|cpp", "C#": r"c#|c sharp",
    "C": r"\bc\b(?![+#])", "JavaScript": r"javascript|\bjs\b", "TypeScript": r"typescript",
    "Go": r"golang|(?<=, )go(?=[,/)])|(?<=: )go(?=[,/])", "Rust": r"rust", "Kotlin": r"kotlin", "Swift": r"swift",
    "SQL": r"sql(?!ite)", "SQLite": r"sqlite", "PostgreSQL": r"postgres(?:ql)?", "MySQL": r"mysql",
    "MongoDB": r"mongo(?:db)?", "Redis": r"redis", "HTML": r"html5?", "CSS": r"css3?",
    "React": r"react(?:\.js|js)?", "Angular": r"angular", "Vue": r"vue(?:\.js)?", "Node.js": r"node(?:\.js|js)?",
    "Express": r"express\.js|expressjs", "Flask": r"flask", "Django": r"django", "FastAPI": r"fastapi",
    "Spring": r"spring boot|spring framework|spring mvc", ".NET": r"\.net|asp\.net", "REST APIs": r"rest(?:ful)? ?apis?|restful|apis?",
    "GraphQL": r"graphql", "Git": r"git(?!hub)|github|gitlab", "Linux": r"linux|unix", "Bash": r"bash|shell scripting",
    "Docker": r"docker", "Kubernetes": r"kubernetes|k8s", "AWS": r"aws|amazon web services",
    "Azure": r"azure", "GCP": r"gcp|google cloud", "CI/CD": r"ci/cd|continuous integration",
    "Unit testing": r"unit test(?:ing|s)?|pytest|junit", "Agile": r"agile|scrum",
    "Data structures": r"data structures?", "Algorithms": r"algorithms?", "OOP": r"object[- ]oriented|oop",
    "Machine learning": r"machine learning|\bml\b", "Deep learning": r"deep learning|neural networks?",
    "NLP": r"\bnlp\b|natural language processing", "Computer vision": r"computer vision|opencv",
    "LLMs": r"\bllms?\b|large language models?|gpt|generative ai|genai", "RAG": r"\brag\b|retrieval[- ]augmented",
    "LangChain": r"langchain", "Hugging Face": r"hugging ?face|transformers library",
    "PyTorch": r"pytorch|torch", "TensorFlow": r"tensorflow|keras", "scikit-learn": r"scikit[- ]learn|sklearn",
    "Pandas": r"pandas", "NumPy": r"numpy", "Matplotlib": r"matplotlib|seaborn", "Jupyter": r"jupyter",
    "Statistics": r"statistics|statistical", "Data analysis": r"data analysis|data analytics",
    "Prompt engineering": r"prompt engineering", "Vector databases": r"vector (?:databases?|stores?)|faiss|pinecone|chroma",
    "Playwright": r"playwright|selenium", "Tableau": r"tableau|power bi",
}
_SKILL_RE = {k: re.compile(rf"(?<![A-Za-z0-9])(?:{v})(?![A-Za-z0-9])", re.I) for k, v in SKILLS.items()}

AI_TERMS = ["Machine learning", "Deep learning", "NLP", "Computer vision", "LLMs", "RAG", "LangChain",
            "Hugging Face", "PyTorch", "TensorFlow", "scikit-learn", "Statistics", "Prompt engineering",
            "Vector databases", "Pandas", "NumPy", "Jupyter"]
SWE_TERMS = ["Java", "C++", "C#", "JavaScript", "TypeScript", "React", "Node.js", "Flask", "Django",
             "FastAPI", "Spring", ".NET", "REST APIs", "GraphQL", "SQL", "PostgreSQL", "Docker",
             "Kubernetes", "AWS", "CI/CD", "Unit testing", "Data structures", "Algorithms", "OOP", "HTML", "CSS"]


def extract_skills(text: str) -> set[str]:
    text = text or ""
    found = {k for k, rx in _SKILL_RE.items() if rx.search(text)}

    if "C" in found and not re.search(r"\b(?:languages?|programming)[^\n]{0,80}\bC\b", text, re.I):
        found.discard("C")
    return found


def read_pdf_text(path: Path) -> str:
    import pdfplumber
    with pdfplumber.open(str(path)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


SECTION_RE = re.compile(r"^\s*(education|experience|work experience|professional experience|projects?|"
                        r"technical skills|skills|certifications?|leadership|activities|awards|"
                        r"relevant coursework|coursework|publications|research)\s*:?\s*$", re.I)
BULLET_RE = re.compile(r"^\s*(?:[•●▪◦·\-*–]|•)\s*")


def parse_projects(text: str) -> list[dict]:

    lines = (text or "").splitlines()
    in_proj, projects, cur = False, [], None
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m = SECTION_RE.match(line)
        if m:
            in_proj = m.group(1).lower().startswith("project")
            continue
        if not in_proj:
            continue
        if BULLET_RE.match(raw) or (cur and line[:1].islower()):
            if cur is not None:
                cur["bullets"].append(BULLET_RE.sub("", line))
            continue

        name = re.split(r"\s[|–—-]\s|\s{2,}|\(", line)[0].strip(" :|")
        cur = {"name": name[:80], "header": line, "bullets": []}
        projects.append(cur)
    out = []
    for p in projects:
        desc = " ".join(p["bullets"]).strip()
        if not desc:
            continue
        out.append({"name": p["name"], "description": desc,
                    "skills": sorted(extract_skills(p["header"] + " " + desc))})
    return out


def load_resume_info(force: bool = False) -> dict:

    cache_file = config.DATA_DIR / "resume_cache.json"
    cache = {}
    if cache_file.exists() and not force:
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cache = {}
    info, changed = {}, False
    for key, path in config.RESUMES.items():
        if not path.exists():
            info[key] = {"exists": False, "path": str(path), "text": "", "skills": [], "projects": []}
            continue
        mtime = path.stat().st_mtime
        c = cache.get(key)
        if c and c.get("mtime") == mtime:
            info[key] = c
            continue
        try:
            text = read_pdf_text(path)
        except Exception as e:
            print(f"  ! Couldn't read {path.name}: {e}")
            text = ""
        info[key] = {"exists": True, "path": str(path), "mtime": mtime, "text": text,
                     "skills": sorted(extract_skills(text)), "projects": parse_projects(text)}
        if not text.strip():
            info[key]["warning"] = "No text found - is this a scanned image PDF? Skills can't be read from it."
        changed = True
    if changed:
        config.ensure_dirs()
        cache_file.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


def my_projects(profile: dict, resume_info: dict, resume_key: str) -> list[dict]:

    if profile.get("projects"):
        out = []
        for p in profile["projects"]:
            skills = p.get("skills") or sorted(extract_skills(f"{p.get('name', '')} {p.get('description', '')}"))
            out.append({"name": p.get("name", ""), "description": p.get("description", ""), "skills": skills})
        return out
    seen, out = set(), []
    for key in [resume_key] + [k for k in resume_info if k != resume_key]:
        for p in resume_info.get(key, {}).get("projects", []):
            if p["name"].lower() not in seen:
                seen.add(p["name"].lower())
                out.append(p)
    return out


def select_resume(job: dict, resume_info: dict) -> tuple[str, float, str]:

    title = job.get("title", "")
    t_ai = bool(re.search(r"\b(machine learning|ml|ai|artificial intelligence|deep learning|nlp|computer vision|"
                          r"llm|genai|data scien\w*|applied scientist|research engineer)\b", title, re.I))
    t_swe = bool(re.search(r"\b(software|developer|backend|back[- ]end|full[- ]?stack|python|web|frontend|"
                           r"front[- ]end|platform|infrastructure|mobile)\b", title, re.I))
    if t_ai and not t_swe:
        return "ai", 0.95, "Title is an AI/ML role"
    if t_swe and not t_ai:

        pass
    text = f"{job.get('description', '')}\n{job.get('required', '')}\n{job.get('preferred', '')}"
    skills = extract_skills(text)
    ai_hits = len(skills & set(AI_TERMS))
    swe_hits = len(skills & set(SWE_TERMS))
    sw = set(resume_info.get("swe", {}).get("skills", []))
    ai = set(resume_info.get("ai", {}).get("skills", []))
    ai_overlap, swe_overlap = len(skills & ai), len(skills & sw)
    ai_score = ai_hits * 2 + ai_overlap + (4 if t_ai else 0)
    swe_score = swe_hits * 2 + swe_overlap + (4 if t_swe else 0)
    total = ai_score + swe_score
    if total == 0:
        return "swe", 0.4, "Not enough information in the posting to choose"
    key = "ai" if ai_score > swe_score else "swe"
    margin = abs(ai_score - swe_score) / total
    conf = min(0.95, 0.5 + margin)
    if t_swe and key == "swe":
        conf = max(conf, 0.85)
    reason = (f"{'AI/ML' if key == 'ai' else 'Software'} signals stronger "
              f"(AI terms {ai_hits}, software terms {swe_hits}; your resume overlap AI {ai_overlap} vs SWE {swe_overlap})")
    if t_swe and t_ai:
        reason = "Title mixes software and AI/ML - " + reason
        conf = min(conf, 0.75 if margin > 0.3 else 0.5)
    return key, round(conf, 2), reason


TIER1 = [
    (r"\bremote\b", "Remote (US)"),
    (r"\bwest monroe\b", "West Monroe, LA"), (r"\bmonroe,?\s*(?:la|louisiana)\b", "Monroe, LA"),
    (r"\b(?:st\.?|saint)\s*cloud\b", "St. Cloud, MN"),
    (r"\bfairborn\b", "Fairborn, OH"), (r"\bdayton\b", "Dayton, OH"),
    (r"\b(?:dallas|fort worth|ft\.? worth|dfw|plano|irving|frisco|richardson|addison|arlington,?\s*tx|"
     r"grapevine|denton|mckinney|carrollton|lewisville|southlake|westlake,?\s*tx)\b", "Dallas-Fort Worth, TX"),
    (r"\b(?:austin|round rock|cedar park|pflugerville)\b", "Austin, TX"),
]
TIER2 = [
    (r"\b(?:shreveport|baton rouge|new orleans|lafayette,?\s*la|ruston|alexandria,?\s*la)\b|,\s*(?:la|louisiana)\b|\blouisiana\b", "Louisiana"),
    (r"\b(?:minneapolis|st\.?\s*paul|saint paul|bloomington,?\s*mn|eden prairie|plymouth,?\s*mn|rochester,?\s*mn)\b|,\s*(?:mn|minnesota)\b|\bminnesota\b", "Minnesota"),
    (r"\b(?:columbus|cincinnati|cleveland|beavercreek|wright-patterson)\b|,\s*(?:oh|ohio)\b|\bohio\b", "Ohio"),
    (r"\b(?:houston|san antonio|el paso|college station)\b|,\s*(?:tx|texas)\b|\btexas\b", "Texas"),
    (r"\b(?:little rock|jackson,?\s*ms|oklahoma city|tulsa|memphis|bentonville|fayetteville,?\s*ar)\b|"
     r",\s*(?:ar|ms|ok|tn|wi|ia|in|mi|ky)\b|\b(?:arkansas|mississippi|oklahoma)\b", "Nearby state"),
]


def geo_tier(location: str, work_mode: str = "") -> tuple[int, str]:
    loc = f"{location or ''} {'remote' if work_mode == 'Remote' else ''}".strip()
    if not loc:
        return 3, "Location not listed"
    for rx, name in TIER1:
        if re.search(rx, loc, re.I):
            return 1, name
    for rx, name in TIER2:
        if re.search(rx, loc, re.I):
            return 2, name
    return 3, location


TRACK_STRONG = re.compile(
    r"\b(software (?:engineer|developer|engineering)|swe|backend|back[- ]end|python developer|full[- ]?stack|"
    r"machine learning|ml engineer|ai engineer|applied ai|ai/ml|artificial intelligence|ai developer)\b", re.I)
TRACK_OK = re.compile(r"\b(developer|engineering|engineer|data scien\w*|platform|infrastructure|web|cloud|"
                      r"devops|mobile|frontend|front[- ]end|research)\b", re.I)


def score_job(job: dict, resume_info: dict, settings: dict) -> dict:

    w = settings.get("weights", config.DEFAULT_SETTINGS["weights"])
    wsum = sum(w.values()) or 1
    resume_key, conf, reason = select_resume(job, resume_info)
    mine = set(resume_info.get(resume_key, {}).get("skills", []))
    if not mine:
        mine = set().union(*[set(v.get("skills", [])) for v in resume_info.values()]) if resume_info else set()
    expl = []


    req = extract_skills(job.get("required", ""))
    pref = extract_skills(job.get("preferred", ""))
    allj = extract_skills(f"{job.get('title', '')}\n{job.get('description', '')}") | req | pref
    if not req:
        req = allj - pref
    if not allj:
        s_skill = 0.5
        expl.append("Skills: posting lists no specific technologies (neutral)")
    elif not mine:
        s_skill = 0.3
        expl.append("Skills: couldn't read your resume skills - add your resume PDFs")
    else:
        r_ratio = len(req & mine) / len(req) if req else 0.6
        p_ratio = len(pref & mine) / len(pref) if pref else r_ratio
        s_skill = 0.75 * r_ratio + 0.25 * p_ratio
        matched = sorted(allj & mine)
        missing = sorted((req or allj) - mine)
        expl.append(f"Skills: you match {', '.join(matched[:8]) or 'none'}"
                    + (f"; not on your resume: {', '.join(missing[:6])}" if missing else ""))


    title = job.get("title", "")
    if TRACK_STRONG.search(title):
        s_track = 1.0
        expl.append("Track: title is a direct match for your target roles")
    elif TRACK_OK.search(title):
        s_track = 0.7
        expl.append("Track: related engineering title")
    else:
        s_track = 0.35
        expl.append("Track: title is only loosely related")


    tier, place = geo_tier(job.get("location", ""), job.get("work_mode", ""))
    s_geo = {1: 1.0, 2: 0.65, 3: 0.4}[tier]
    expl.append(f"Location: Tier {tier} ({place})")


    from job_parser import check_timing
    timing = check_timing(title, f"{job.get('description', '')}\n{job.get('dates', '')}")
    s_time = {"match": 1.0, "unknown": 0.65, "incompatible": 0.0}[timing]
    if any("graduation" in f.lower() for f in job.get("flags", [])):
        s_time = min(s_time, 0.35)
    expl.append({"match": "Timing: explicitly Summer 2027",
                 "unknown": "Timing: term not stated (likely Summer 2027 - confirm)",
                 "incompatible": "Timing: different term/year"}[timing])

    parts = {"skills": s_skill, "track": s_track, "geo": s_geo, "timing": s_time}
    score = round(sum(parts[k] * w.get(k, 0) for k in parts) * 100 / wsum)
    return {"score": score, "parts": {k: round(v, 2) for k, v in parts.items()}, "explanation": expl,
            "resume": resume_key, "resume_conf": conf, "resume_reason": reason, "geo_tier": tier}
