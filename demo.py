import copy
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from reportlab.pdfgen import canvas

import autofill
import config
import matcher
from job_parser import new_job


def run_demo(headless=False):
    profile = copy.deepcopy(config.DEFAULT_PROFILE)
    profile.update(first_name="Alex", last_name="Example", email="alex@example.com", phone="202-555-0100",
                   university="Example University", github="https://github.com/example")
    profile["experience"] = [{"employer": "Example Lab", "title": "Student Developer", "location": "Example City",
                              "start_date": "2025-01", "end_date": "2025-05", "current": False,
                              "description": "Built and tested a Python classroom application."}]
    settings = copy.deepcopy(config.DEFAULT_SETTINGS)
    text = "Technical skills: Python, JavaScript, SQL, Git, unit testing"
    resumes = {"swe": {"exists": True, "text": text, "skills": sorted(matcher.extract_skills(text)), "projects": []}}
    job = new_job(company="Example Lab", title="Software Engineer Intern Summer 2027", location="Remote - US",
                  description="Requirements: Python, SQL, Git", required="Python, SQL, Git")
    score = matcher.score_job(job, resumes, settings)
    print("Mock demonstration: fictional applicant and employer; no live job sources or private files.")
    print(f"Resume match: {score['score']}/100 (heuristic, not a hiring prediction)")
    with tempfile.TemporaryDirectory(prefix="job_demo_") as folder:
        resume = Path(folder) / "mock_resume.pdf"
        pdf = canvas.Canvas(str(resume))
        pdf.drawString(50, 750, "Alex Example - fictional demonstration resume")
        pdf.drawString(50, 725, text)
        pdf.save()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            context.route("**/*", lambda route: route.abort() if route.request.url.startswith(("http:", "https:")) else route.continue_())
            page = context.new_page()
            page.goto((config.BASE_DIR / "tests" / "fixtures" / "demo_form.html").as_uri())
            report = autofill.fill_page(page, profile, settings, {"resume": str(resume)})
            print(f"Filled {len(report.filled)} fields; uploaded {len(report.uploaded)} mock file(s).")
            assert page.evaluate("window.__submitted !== true")
            if not headless:
                input("Review the local mock form. Press Enter here to close the demonstration. ")
            browser.close()
    print("Demo complete. No submissions, saved application records, or personal files used.")
    return 0
