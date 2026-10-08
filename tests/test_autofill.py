from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
import autofill

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"Chromium not available: {e}")
        yield b
        b.close()


@pytest.fixture
def files(tmp_path):
    r = tmp_path / "software_developer.pdf"
    r.write_bytes(b"%PDF-1.4 test")
    c = tmp_path / "Globex_CoverLetter.pdf"
    c.write_bytes(b"%PDF-1.4 test")
    return {"resume": str(r), "cover_letter": str(c)}


def open_fixture(browser, name):
    page = browser.new_page()
    page.goto((FIX / name).as_uri())
    return page


def val(page, sel):
    return page.eval_on_selector(sel, "e => e.value")


def test_lever_form(browser, profile, settings, files):
    page = open_fixture(browser, "lever_form.html")
    rep = autofill.fill_page(page, profile, settings, {"resume": files["resume"], "cover_letter": None},
                             cover_text_getter=lambda kind: "My cover letter text." if kind == "text" else None)
    assert val(page, "[name=name]") == "Alex Student"
    assert val(page, "[name=email]") == "alex@example.com"
    assert val(page, "[name='urls[LinkedIn]']") == "https://linkedin.com/in/alex"
    assert val(page, "[name=org]") == ""
    assert page.eval_on_selector("[name=resume]", "e => e.files.length") == 1

    sel = lambda n: page.eval_on_selector(f"[name='{n}']", "e => e.options[e.selectedIndex].text")
    assert sel("eeo[race]") == "Asian"
    assert sel("eeo[veteran]") == "I am not a veteran"
    assert sel("eeo[disability]").startswith("No, I do not have a disability")
    assert sel("eeo[gender]") == "Select ..."

    assert sel("cards[a][field0]") == "Select..."
    assert not page.eval_on_selector_all("[name='cards[a][field1]']", "els => els.some(e => e.checked)")
    manual = " ".join(f"{a} {b}" for a, b in rep.manual)
    assert "WORK AUTHORIZATION" in manual and "VISA SPONSORSHIP" in manual
    assert "Why do you want to work at Acme?" in manual

    assert page.evaluate("() => window.__submitted === undefined")
    page.close()


def test_greenhouse_form(browser, profile, settings, files):
    page = open_fixture(browser, "greenhouse_form.html")
    rep = autofill.fill_page(page, profile, settings, files)
    assert val(page, "#first_name") == "Alex" and val(page, "#last_name") == "Student"
    assert val(page, "#phone") == "555-already-there"
    assert val(page, "#school--0") == "University of Louisiana at Monroe"
    text = lambda s: page.eval_on_selector(s, "e => e.options[e.selectedIndex].text")
    assert text("#degree--0") == "Bachelor's Degree"
    assert text("#discipline--0") == "Computer Science"
    assert text("#q_grad") == "2028"
    assert text("#hispanic_ethnicity") == "No"
    assert text("#race") == "Asian"
    assert text("#disability_status") == "No, I do not have a disability"
    assert page.eval_on_selector("input[name=veteran_status][value='2']", "e => e.checked")
    assert val(page, "#q_linkedin") == "https://linkedin.com/in/alex"
    assert page.eval_on_selector("#resume", "e => e.files.length") == 1
    assert page.eval_on_selector("#cover_letter", "e => e.files.length") == 1
    assert any("years of professional experience" in a for a, _ in rep.manual)
    assert page.evaluate("() => window.__submitted === undefined")
    page.close()


def test_demographics_can_be_turned_off(browser, profile, settings, files):
    page = open_fixture(browser, "greenhouse_form.html")
    autofill.fill_page(page, profile, dict(settings, fill_demographics=False), files)
    assert page.eval_on_selector("#race", "e => e.value") == ""
    page.close()


def test_login_page_stops(browser, profile, settings, files):
    page = open_fixture(browser, "login.html")
    rep = autofill.fill_page(page, profile, settings, files)
    assert "sign in" in rep.blocked.lower()
    assert val(page, "#u") == ""
    page.close()


def test_success_detection(browser):
    page = open_fixture(browser, "lever_form.html")
    assert not autofill.detect_success(page)
    page.goto((FIX / "thanks.html").as_uri())
    assert autofill.detect_success(page)
    page.close()


def test_choose_option_never_guesses():
    assert autofill.choose_option(["Select...", "Yes", "No"], "eeo_race", "Asian") is None
    assert autofill.choose_option(["Asian", "Asian American"], "eeo_race", "Asian") is None
    assert autofill.choose_option(["--", "Male", "Female", "Decline to self-identify"], "eeo_gender", "decline") == 3
    assert autofill.choose_option(["Select", "Jan", "May", "Dec"], "grad_month", "05") == 2


def test_extra_links_and_blank_linkedin(browser, profile, settings, files):
    p = dict(profile, linkedin="", portfolio="", extra_links=[
        {"label": "Kaggle", "url": "https://kaggle.com/alex"},
        {"label": "Hugging Face", "url": "https://huggingface.co/alex"},
        {"label": "Devpost", "url": "https://devpost.com/alex", "keywords": ["hackathon"]},
        {"label": "Broken", "url": ""},
    ])
    page = open_fixture(browser, "links_form.html")
    autofill.fill_page(page, p, settings, files)
    assert val(page, "#li") == ""
    assert val(page, "#gh") == "https://github.com/alex"
    assert val(page, "#kg") == "https://kaggle.com/alex"
    assert val(page, "#hf") == "https://huggingface.co/alex"
    assert val(page, "#hack") == "https://devpost.com/alex"
    assert val(page, "#web") == "https://kaggle.com/alex"
    assert val(page, "#why") == ""
    assert page.evaluate("() => window.__submitted === undefined")
    page.close()


def test_portfolio_wins_over_fallback(browser, profile, settings, files):
    p = dict(profile, portfolio="https://alex.dev", extra_links=[{"label": "Kaggle", "url": "https://kaggle.com/alex"}])
    page = open_fixture(browser, "links_form.html")
    autofill.fill_page(page, p, settings, files)
    assert val(page, "#web") == "https://alex.dev"
    page.close()
