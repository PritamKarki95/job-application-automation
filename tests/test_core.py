import json
from pathlib import Path

import pytest

import tracker
from job_parser import (check_timing, classify_title, detect_ats, eligibility_flags, evaluate,
                        from_greenhouse, from_lever, new_job, split_qualifications)
from matcher import extract_skills, geo_tier, score_job, select_resume

SWE_DESC = """About the role
You'll build backend services used by millions.
Minimum Qualifications
- Pursuing a BS in Computer Science, graduating 2027 or 2028
- Experience with Python or Java
- Familiarity with REST APIs, SQL and Git
Preferred Qualifications
- Experience with Docker or Kubernetes
- React
"""
ML_DESC = """Requirements
- Coursework in machine learning
- Python, PyTorch, scikit-learn
- Experience with LLMs or NLP
Nice to have
- RAG or LangChain experience
"""


def job(title, desc="", location="Austin, TX", company="Acme", **kw):
    req, pref = split_qualifications(desc)
    return new_job(company=company, title=title, location=location, description=desc,
                   required=req, preferred=pref, url=f"https://example.com/{title.replace(' ', '-')}", **kw)


@pytest.mark.parametrize("title,intern,track,senior", [
    ("Software Engineer Intern (Summer 2027)", True, "swe", False),
    ("Machine Learning Engineer Intern", True, "ai", False),
    ("Backend Developer Internship", True, "swe", False),
    ("Applied AI Intern", True, "ai", False),
    ("Senior Software Engineer", False, "swe", True),
    ("Marketing Intern", True, None, False),
    ("Internal Tools Engineer", False, None, False),
    ("Mechanical Engineering Intern", True, None, False),
])
def test_classify_title(title, intern, track, senior):
    c = classify_title(title)
    assert c["is_internship"] == intern
    assert c["track"] == track
    assert c["is_senior"] == senior


def test_timing():
    assert check_timing("Software Engineer Intern - Summer 2027", "") == "match"
    assert check_timing("Software Engineer Intern - Summer 2026", "") == "incompatible"
    assert check_timing("Software Engineering Co-op, Fall 2027", "") == "incompatible"
    assert check_timing("Software Engineer Intern", "Join our Summer 2026 intern program") == "incompatible"

    assert check_timing("Software Engineer Intern", "for students graduating Fall 2026 - Spring 2028") == "unknown"


def test_eligibility_flags():
    hard, _ = eligibility_flags("Must be a U.S. citizen. Requires an active Secret clearance.")
    assert hard
    hard, review = eligibility_flags("We are unable to sponsor visas for this role.")
    assert not hard and review
    _, review = eligibility_flags("Graduating between December 2026 and June 2027", grad_year=2028)
    assert any("graduation" in r.lower() for r in review)


def test_evaluate_filters():
    ok, _ = evaluate(job("Software Engineer Intern", SWE_DESC))
    assert ok
    ok, reasons = evaluate(job("Software Engineer, New Grad", SWE_DESC))
    assert not ok
    ok, reasons = evaluate(job("Software Engineer Intern", SWE_DESC, location="Toronto, Canada"))
    assert not ok and "Outside the United States" in reasons
    ok, _ = evaluate(job("Software Engineer Intern", SWE_DESC, location="New York, NY or Toronto, ON"))
    assert ok
    j = job("Software Engineer Intern", SWE_DESC + "\nWe will not sponsor work visas.")
    ok, _ = evaluate(j)
    assert ok and j["flags"]


def test_split_qualifications():
    req, pref = split_qualifications(SWE_DESC)
    assert "Python or Java" in req and "Docker" not in req
    assert "Docker" in pref


def test_extract_skills_no_false_positives():
    s = extract_skills("Spring 2027 internship. Please express interest. Take a rest. Go to our site.")
    assert not s & {"Spring", "Express", "REST APIs", "Go"}
    assert {"Python", "Java", "C++", "REST APIs"} <= extract_skills("Python, Java, C++ and RESTful APIs")
    assert "JavaScript" not in extract_skills("Java") and "Java" not in extract_skills("JavaScript")


def test_detect_ats():
    assert detect_ats("https://job-boards.greenhouse.io/stripe/jobs/123456")[1] == {"token": "stripe", "id": "123456"}
    assert detect_ats("https://jobs.lever.co/palantir/abc-123")[0] == "lever"
    assert detect_ats("https://acme.com/careers?gh_jid=999")[0] == "greenhouse"
    assert detect_ats("https://acme.wd5.myworkdayjobs.com/x")[0] == "workday"


def test_resume_reading(resume_info):
    assert {"Python", "Flask", "React"} <= set(resume_info["swe"]["skills"])
    assert {"PyTorch", "LLMs", "RAG"} <= set(resume_info["ai"]["skills"])
    names = [p["name"] for p in resume_info["swe"]["projects"]]
    assert "EnergyIQ" in names


def test_resume_selection(resume_info):
    assert select_resume(job("Software Engineer Intern", SWE_DESC), resume_info)[0] == "swe"
    k, conf, _ = select_resume(job("Machine Learning Engineer Intern", ML_DESC), resume_info)
    assert k == "ai" and conf >= 0.9

    assert select_resume(job("Engineering Intern", ML_DESC), resume_info)[0] == "ai"

    assert select_resume(job("Engineering Intern", "Join us!"), resume_info)[1] < 0.6


def test_scoring(resume_info, settings):
    good = score_job(job("Software Engineer Intern - Summer 2027", SWE_DESC, "Remote - US"), resume_info, settings)
    weak = score_job(job("Engineering Intern", "Experience with Kubernetes, Go, Rust, Swift required.",
                         "Seattle, WA"), resume_info, settings)
    assert 0 <= weak["score"] < good["score"] <= 100
    assert good["score"] >= 75
    assert any(e.startswith("Location: Tier 1") for e in good["explanation"])

    s2 = dict(settings, weights={"skills": 0, "track": 0, "geo": 100, "timing": 0})
    assert score_job(job("Software Engineer Intern", SWE_DESC, "Remote"), resume_info, s2)["score"] == 100


@pytest.mark.parametrize("loc,tier", [
    ("Remote", 1), ("Monroe, LA", 1), ("West Monroe, Louisiana", 1), ("St. Cloud, MN", 1),
    ("Dayton, OH", 1), ("Plano, TX", 1), ("Austin, Texas", 1), ("Baton Rouge, LA", 2),
    ("Minneapolis, MN", 2), ("Houston, TX", 2), ("Seattle, WA", 3), ("", 3),
])
def test_geo(loc, tier):
    assert geo_tier(loc)[0] == tier


def test_cover_letter_fallback(resume_info, profile, settings):
    import cover_letter
    j1 = job("Backend Developer Intern", SWE_DESC, company="Globex")
    j2 = job("Machine Learning Engineer Intern", ML_DESC, company="Initech")
    a = cover_letter.generate(j1, profile, resume_info, "swe", settings, want_pdf=False)
    b = cover_letter.generate(j2, profile, resume_info, "ai", settings, want_pdf=False)
    assert a["method"] == b["method"] == "template"
    assert Path(a["docx"]).exists() and Path(a["txt"]).exists()
    assert "Globex" in a["text"] and "Backend Developer Intern" in a["text"]
    assert "EnergyIQ" in a["text"]
    assert "Course Notes Assistant" in b["text"]
    assert a["text"].replace("Globex", "X") != b["text"].replace("Initech", "X")

    mine = set(resume_info["swe"]["skills"]) | set(resume_info["ai"]["skills"])
    assert extract_skills(a["text"]) <= mine and extract_skills(b["text"]) <= mine
    words = len(a["text"].split())
    assert 120 <= words <= 450


def test_ollama_output_rejected_when_ungrounded(resume_info):
    import cover_letter
    j = job("Backend Developer Intern", SWE_DESC, company="Globex")
    content = cover_letter.relevant_content(j, {}, resume_info, "swe")
    filler = " ".join(["I enjoy building software that people rely on every day."] * 20)
    assert cover_letter.letter_is_grounded(f"At Globex I would use Python. {filler}", j, content)
    assert not cover_letter.letter_is_grounded(f"At Globex I would use Kubernetes and Rust. {filler}", j, content)
    assert not cover_letter.letter_is_grounded(f"I would use Python. {filler}", j, content)


def test_ollama_unavailable_is_safe(settings):
    import cover_letter
    s = dict(settings, use_ollama=True, ollama_url="http://127.0.0.1:9")
    assert cover_letter.ollama_available(s) is False


def test_duplicates(conn):
    a = job("Software Engineer Intern", SWE_DESC, job_id="gh:acme:1")
    pk, new = tracker.upsert_job(conn, a)
    assert new

    assert tracker.upsert_job(conn, dict(a, url="https://other.com/x"))[1] is False

    b = job("Different title", job_id="gh:acme:2")
    b["url"] = "https://www.example.com/Software-Engineer-Intern/apply?utm_source=li"
    assert tracker.find_duplicate(conn, b)["id"] == pk

    c = job("Software Engineer Internship", company="ACME, Inc.", job_id="lever:acme:9")
    c["url"] = "https://jobs.lever.co/acme/9"
    assert tracker.find_duplicate(conn, c)["id"] == pk

    d = job("ML Engineer Intern", company="Acme", job_id="gh:acme:3")
    assert tracker.find_duplicate(conn, d) is None
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_status_transitions(conn):
    pk, _ = tracker.upsert_job(conn, job("Software Engineer Intern", SWE_DESC))
    with pytest.raises(tracker.TransitionError):
        tracker.set_status(conn, pk, "Submitted")
    tracker.set_status(conn, pk, "Shortlisted")
    tracker.set_status(conn, pk, "Prepared")
    tracker.set_status(conn, pk, "Failed")
    tracker.set_status(conn, pk, "Prepared")
    assert tracker.submitted_today(conn) == 0
    tracker.set_status(conn, pk, "Submitted")
    assert tracker.submitted_today(conn) == 1
    assert tracker.get_job(conn, pk)["applied_at"]
    with pytest.raises(tracker.TransitionError):
        tracker.set_status(conn, pk, "Skipped")

    tracker.upsert_job(conn, job("Software Engineer Intern", "changed text"))
    assert tracker.get_job(conn, pk)["status"] == "Submitted"
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


GH_RESPONSE = {"jobs": [
    {"id": 11, "title": "Software Engineer Intern (Summer 2027)", "location": {"name": "Dallas, TX"},
     "absolute_url": "https://acme.com/careers?gh_jid=11", "updated_at": "2026-09-30T00:00:00Z",
     "content": "&lt;h3&gt;Requirements&lt;/h3&gt;&lt;ul&gt;&lt;li&gt;Python, SQL, Git&lt;/li&gt;&lt;/ul&gt;"},
    {"id": 12, "title": "Senior Software Engineer", "location": {"name": "Remote"}, "absolute_url": "x", "content": ""},
    {"id": 13, "title": "Software Engineer Intern", "location": {"name": "London, UK"}, "absolute_url": "y", "content": ""},
]}
LEVER_RESPONSE = [
    {"id": "abc", "text": "Machine Learning Intern", "categories": {"location": "Remote", "commitment": "Intern"},
     "workplaceType": "remote", "descriptionPlain": "Work on LLMs.", "createdAt": 1790000000000,
     "lists": [{"text": "Requirements", "content": "<li>Python</li><li>PyTorch</li>"}],
     "hostedUrl": "https://jobs.lever.co/acme/abc", "applyUrl": "https://jobs.lever.co/acme/abc/apply"},
]


class FakeResp:
    def __init__(self, data, code=200):
        self._d, self.status_code = data, code

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


def test_parsers():
    g = from_greenhouse("acme", GH_RESPONSE["jobs"][0], "Acme Corp")
    assert g["company"] == "Acme Corp" and g["job_id"] == "gh:acme:11"
    assert "Python" in g["required"] and g["apply_url"].endswith("/acme/jobs/11")
    l = from_lever("acme", LEVER_RESPONSE[0])
    assert l["work_mode"] == "Remote" and "PyTorch" in l["description"] and l["posted"].startswith("2026")


def test_discover_with_mocked_apis(monkeypatch, settings):
    import requests

    import discovery

    def fake_get(url, **kw):
        if "boards-api.greenhouse.io/v1/boards/acme/jobs" in url:
            return FakeResp(GH_RESPONSE)
        if "boards-api.greenhouse.io/v1/boards/acme" in url:
            return FakeResp({"name": "Acme Corp"})
        if "api.lever.co" in url:
            return FakeResp(LEVER_RESPONSE)
        if "missing" in url:
            return FakeResp({}, 404)
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(discovery.requests, "get", fake_get)
    res = discovery.discover(settings, {"greenhouse": ["acme", "missing"], "lever": ["acme"], "ashby": ["down"]},
                             progress=lambda *_: None)
    titles = sorted(j["title"] for j in res["kept"])
    assert titles == ["Machine Learning Intern", "Software Engineer Intern (Summer 2027)"]
    status = {(s, b): st for s, b, st, *_ in res["report"]}
    assert status[("greenhouse", "acme")] == "ok"
    assert "not found" in status[("greenhouse", "missing")]
    assert "network error" in status[("ashby", "down")]
