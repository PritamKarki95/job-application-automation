import builtins

import pytest

import autofill
import main
import tracker
from job_parser import canonical_job_site_url, job_site_name, new_job, parse_job_url


def test_job_site_detection():
    assert job_site_name("https://www.linkedin.com/jobs/view/4012345678/?refId=abc") == "LinkedIn"
    assert job_site_name("https://www.indeed.com/viewjob?jk=abc123") == "Indeed"
    assert job_site_name("https://app.joinhandshake.com/jobs/123") == "Handshake"
    assert job_site_name("https://job-boards.greenhouse.io/acme/jobs/1") is None
    assert job_site_name("https://notlinkedin.com/x") is None


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/4012345678/?refId=abc&trackingId=xyz",
    "https://linkedin.com/jobs/view/software-engineer-intern-at-acme-4012345678",
    "https://www.linkedin.com/jobs/collections/recommended/?currentJobId=4012345678",
    "https://www.linkedin.com/jobs/search/?keywords=intern&currentJobId=4012345678",
])
def test_linkedin_links_normalize_to_same_job(url):
    assert canonical_job_site_url(url) == ("https://www.linkedin.com/jobs/view/4012345678", "linkedin:4012345678")


def test_job_sites_are_never_fetched(monkeypatch):
    import job_parser
    monkeypatch.setattr(job_parser.requests, "get", lambda *a, **k: pytest.fail("must not fetch LinkedIn"))
    with pytest.raises(ValueError, match="LinkedIn"):
        parse_job_url("https://www.linkedin.com/jobs/view/4012345678")


def test_autofill_refuses_job_site_pages(profile, settings):
    class FakePage:
        url = "https://www.linkedin.com/jobs/view/4012345678"
        frames = []
    rep = autofill.fill_page(FakePage(), profile, settings, {})
    assert "LinkedIn" in rep.blocked and not rep.filled


def scripted(monkeypatch, answers):
    it = iter(answers)
    monkeypatch.setattr(builtins, "input", lambda *a: next(it))


def test_linkedin_with_company_link(monkeypatch):
    company_job = new_job(source="greenhouse", company="Acme", title="Software Engineer Intern",
                          url="https://job-boards.greenhouse.io/acme/jobs/1",
                          apply_url="https://job-boards.greenhouse.io/acme/jobs/1", job_id="gh:acme:1")
    monkeypatch.setattr(main, "parse_job_url", lambda u: dict(company_job))
    scripted(monkeypatch, ["1", "https://job-boards.greenhouse.io/acme/jobs/1"])
    job = main.job_from_link("https://www.linkedin.com/jobs/view/4012345678/?trk=x")
    assert job["url"] == "https://www.linkedin.com/jobs/view/4012345678"
    assert job["apply_url"].startswith("https://job-boards.greenhouse.io")
    assert job["job_id"] == "gh:acme:1"
    assert "Found on LinkedIn" in job["flags"]


def test_linkedin_manual_details_with_description(monkeypatch):
    scripted(monkeypatch, ["2", "Globex", "Machine Learning Intern", "Austin, TX", "y",
                           "Requirements", "- Python and PyTorch", "END"])
    job = main.job_from_link("https://www.linkedin.com/jobs/view/4099999999")
    assert (job["company"], job["title"], job["location"]) == ("Globex", "Machine Learning Intern", "Austin, TX")
    assert "PyTorch" in job["description"] and "PyTorch" in job["required"]
    assert job["job_id"] == "linkedin:4099999999" and job["source"] == "linkedin"


def test_same_linkedin_job_is_not_added_twice(conn, monkeypatch):
    scripted(monkeypatch, ["2", "Globex", "SWE Intern", "", "n"])
    job = main.job_from_link("https://www.linkedin.com/jobs/view/4011111111/?refId=1")
    pk, new = tracker.upsert_job(conn, job)
    assert new
    clean, jid = canonical_job_site_url("https://www.linkedin.com/jobs/collections/x/?currentJobId=4011111111")
    assert tracker.find_duplicate(conn, {"url": clean, "job_id": jid})["id"] == pk


def test_collect_links_from_paste_and_file(monkeypatch, tmp_path):
    f = tmp_path / "job_links.txt"
    f.write_text("# comment\nhttps://a.com/job/1\n\nhttps://www.linkedin.com/jobs/view/4000000001\n")
    monkeypatch.setattr(main, "LINKS_FILE", f)
    scripted(monkeypatch, ["https://b.com/x https://c.com/y", "file", "https://a.com/job/1", ""])
    assert main.collect_links() == ["https://b.com/x", "https://c.com/y", "https://a.com/job/1",
                                    "https://www.linkedin.com/jobs/view/4000000001"]
