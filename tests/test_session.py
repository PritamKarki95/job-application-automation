from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
import autofill

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def files(tmp_path):
    r = tmp_path / "software_developer.pdf"
    r.write_bytes(b"%PDF-1.4 test")
    return {"resume": str(r)}


def test_full_session_never_records_unconfirmed_submit(profile, settings, files):

    answers = iter(["s", "no", "k"])
    job = {"apply_url": (FIX / "lever_form.html").as_uri(), "title": "SWE Intern", "company": "Acme"}
    res = autofill.run_application(job, profile, dict(settings, _headless=True), files["resume"],
                                   ask=lambda *_: next(answers))
    assert res["outcome"] == "skipped"


def test_full_session_detects_confirmation(profile, settings, files):
    answers = iter(["s"])
    job = {"apply_url": (FIX / "thanks.html").as_uri()}
    res = autofill.run_application(job, profile, dict(settings, _headless=True), files["resume"],
                                   ask=lambda *_: next(answers))
    assert res == {"outcome": "submitted", "note": "confirmation page detected"}
