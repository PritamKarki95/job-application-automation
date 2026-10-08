import discovery
import main
from job_parser import new_job


def record(**overrides):
    row = {"company_name": "Local Software", "title": "Software Engineer Intern", "active": True,
           "is_visible": True, "terms": ["Summer 2027"], "url": "https://example.com/job",
           "locations": ["Austin, TX"], "degrees": ["Bachelor's"], "sponsorship": "Other"}
    row.update(overrides)
    return row


def test_feed_excludes_closed_hidden_wrong_season_and_duplicates():
    rows = [record(), record(), record(active=False), record(is_visible=False),
            record(terms=["Summer 2026"]), record(url="javascript:alert(1)")]
    jobs = discovery.community_candidates(rows, "Summer 2027")
    assert len(jobs) == 1
    assert jobs[0]["dates"] == "Summer 2027"
    assert "2026" not in jobs[0]["description"]


def test_feed_multi_season_and_eligibility(settings, monkeypatch):
    rows = [record(terms=["Summer 2026", "Summer 2027"], url="https://example.com/one"),
            record(sponsorship="U.S. Citizenship is Required", url="https://example.com/two"),
            record(degrees=["Master's", "PhD"], url="https://example.com/three")]
    monkeypatch.setattr(discovery, "_get_json", lambda url: rows)
    import job_parser
    monkeypatch.setattr(job_parser, "parse_job_url", lambda url: new_job(
        title="Software Engineer Intern", company="Local", description="Requirements: Python", url=url))
    result = discovery.discover_community(settings, {}, progress=lambda text: None)
    assert len(result["kept"]) == 1
    assert len(result["rejected"]) == 2


def test_other_employers_first_and_unreadable_pages_not_ranked(settings, monkeypatch):
    rows = [record(company_name="Google", url="https://example.com/google"),
            record(company_name="Small Employer", url="https://example.com/local"),
            record(company_name="Another Employer", url="https://example.com/fail")]
    monkeypatch.setattr(discovery, "_get_json", lambda url: rows)
    import job_parser
    reads = []
    def parse(url):
        reads.append(url)
        if url.endswith("fail"):
            raise ValueError("closed")
        return new_job(title="Software Engineer Intern", description="Python and SQL", url=url)
    monkeypatch.setattr(job_parser, "parse_job_url", parse)
    settings["community_read_limit"] = 2
    result = discovery.discover_community(settings, {}, progress=lambda text: None)
    assert reads == ["https://example.com/local", "https://example.com/fail"]
    assert len(result["kept"]) == 1
    assert "Python and SQL" in result["kept"][0]["description"]


def test_actual_posting_requirements_override_stale_feed(settings, monkeypatch):
    monkeypatch.setattr(discovery, "_get_json", lambda url: [record()])
    import job_parser
    monkeypatch.setattr(job_parser, "parse_job_url", lambda url: new_job(
        title="Senior Software Engineer", description="Python", url=url))
    result = discovery.discover_community(settings, {}, progress=lambda text: None)
    assert not result["kept"]


def test_google_queries_open_search_not_scrape(monkeypatch, settings, resume_info):
    import webbrowser
    opened = []
    monkeypatch.setattr(main, "ask", lambda *args: "3")
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))
    main.search_google(settings, resume_info)
    assert len(opened) == 1
    assert opened[0].startswith("https://www.google.com/search?")
    assert "startup" in opened[0]


def test_search_results_exclude_old_employers_and_keep_fifteen_limit(conn, monkeypatch, settings, capsys):
    import tracker
    tracker.upsert_job(conn, new_job(company="Old Big Employer", title="Software Intern", url="https://example.com/old"),
                       {"score": 100, "explanation": [], "resume": "swe"})
    ids = []
    for i in range(20):
        pk, _ = tracker.upsert_job(conn, new_job(company=f"Local{i:02d}", title="Software Intern", url=f"https://example.com/{i}"),
                                   {"score": 90 - i, "explanation": [], "resume": "swe"})
        ids.append(pk)
    monkeypatch.setattr(main, "ask", lambda *args: "")
    main.pick_and_apply(conn, settings, {}, {}, ["Discovered"], ids)
    output = capsys.readouterr().out
    assert "Old Big Employer" not in output
    assert "Local14" in output
    assert "Local15" not in output
