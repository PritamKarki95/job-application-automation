import pytest
from playwright.sync_api import sync_playwright

import autofill


@pytest.fixture
def work_profile(profile):
    profile["experience"] = [
        {"employer": "School", "title": "Developer Intern", "location": "Biratnagar, Nepal",
         "start_date": "2023-07", "end_date": "2024-04", "current": False, "description": "Built a Python application."},
        {"employer": "Hash", "title": "Engineering Intern", "location": "Nepal",
         "start_date": "2022-10", "end_date": "2023-01", "current": False, "description": "Tested Java applications."}]
    return profile


def test_current_employer_and_exact_dates_not_invented(work_profile):
    assert autofill.experience_value("current_work_employer", work_profile) == ""
    assert autofill.experience_value("work_start_date", work_profile, field_type="date") == ""
    assert autofill.experience_value("work_start_date", work_profile, field_type="month") == "2023-07"
    assert autofill.experience_value("work_start_month", work_profile) == "July"
    assert autofill.experience_value("work_end_year", work_profile, 1) == "2023"
    assert autofill.experience_value("work_employer", work_profile, 2) == ""


def test_repeated_work_history_fills_and_preserves_values(work_profile, settings):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content('''<form onsubmit="window.submitted=true;return false">
          <fieldset><legend>Work Experience 1</legend>
          <label>Employer<input id="employer1"></label><label>Job title<input id="title1"></label>
          <label>Start date<input type="month" id="start1"></label>
          <label>End date<input type="date" id="end1"></label>
          <label>Location<input id="location1"></label><label>Responsibilities<textarea id="duties1"></textarea></label>
          </fieldset><fieldset><legend>Work Experience 2</legend>
          <label>Employer<input id="employer2"></label><label>Job title<input id="title2" value="Keep this"></label>
          <label>Start year<select id="year2"><option>Select</option><option>2022</option><option>2023</option></select></label>
          </fieldset><fieldset><legend>Education</legend><label>School<input id="school"></label>
          <label>Start date<input id="education_start"></label></fieldset>
          <label>Current employer<input id="current"></label>
          <label>Work experience summary<textarea id="summary"></textarea></label>
          <label>Years of professional experience<input id="years"></label>
          <label>Do you require visa sponsorship?<input id="visa"></label>
          <button type="submit">Submit</button></form>''')
        autofill.fill_page(page, work_profile, settings, {})
        assert page.locator("#employer1").input_value() == "School"
        assert page.locator("#title1").input_value() == "Developer Intern"
        assert page.locator("#start1").input_value() == "2023-07"
        assert page.locator("#end1").input_value() == ""
        assert page.locator("#location1").input_value() == "Biratnagar, Nepal"
        assert page.locator("#duties1").input_value() == "Built a Python application."
        assert page.locator("#employer2").input_value() == "Hash"
        assert page.locator("#title2").input_value() == "Keep this"
        assert page.locator("#year2").input_value() == "2022"
        assert page.locator("#school").input_value() == work_profile["university"]
        assert page.locator("#education_start").input_value() == ""
        assert page.locator("#current").input_value() == ""
        assert "Hash" in page.locator("#summary").input_value()
        assert page.locator("#years").input_value() == ""
        assert page.locator("#visa").input_value() == ""
        assert page.evaluate("window.submitted === undefined")
        browser.close()
