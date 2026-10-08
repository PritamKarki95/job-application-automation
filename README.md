# Job Application Automation — Experimental Python Project

**Experimental | Educational | Personal Learning Project**

## Overview

This personal learning project explores Python programming, browser automation,
workflow design, and job-posting data processing. It is an experimental proof of
concept, not a production application or a job-submission service.

The default entry point runs a local demonstration with fictional data. Real
integrations are retained for development in explicitly authorized test environments.

## Motivation

I developed this project to learn how repetitive workflows can be studied and
automated through programming. The focus is experimentation with parsing,
matching, browser state, error handling, and tests.

## Technologies Used

- Python 3.11+ and SQLite through Python's standard library.
- Playwright with Chromium for browser automation.
- Requests and BeautifulSoup for public API and HTML processing.
- pdfplumber for extracting text from PDFs.
- python-docx and ReportLab for documents and mock PDFs.
- python-dotenv for optional local configuration.
- pytest for automated tests.
- Optional local Ollama through HTTP; no hosted model API integration.
- HTML and JavaScript for local form fixtures.

## Experimental Features

### Implemented and tested components

- Resume skill extraction and heuristic job matching.
- Internship, location, season, and eligibility filters.
- SQLite records, duplicate detection, and workflow state transitions.
- Recognized contact, education, work-history, link, and document fields.
- Cover-letter templates and optional local model generation.
- Mock browser tests that verify forms are not submitted automatically.
- A mock-only demo that blocks HTTP/HTTPS requests and uses temporary documents.

### Partial and experimental integrations

Public Greenhouse, Lever, and Ashby sources and the
[Simplify/Pitt CSC internship feed](https://github.com/SimplifyJobs/Summer2027-Internships)
are implemented, but their availability and formats can change. Generic HTML
parsing and custom dropdown matching are best effort. Some forms are unsupported.
Workday is handled manually. Google searches open in a browser; search results
and restricted job sites are not scraped.

There is no automated submission feature, production deployment, or active GUI.
No planned features are claimed as implemented.

## Learning Objectives

The code exercises Python modules, structured data processing, browser DOM
inspection, workflow state, error handling, local persistence, debugging, and
automated tests. Scores and generated text remain subject to manual review.

## Installation and Setup

Install Python 3.11 or newer. From the project folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

Run the safe demonstration:

```powershell
.\.venv\Scripts\python.exe main.py
```

The demo opens a local form with fictional applicant details and a generated mock
resume. It does not load a private profile, search live job sources, or create
application history. Press Enter in the terminal to close it.

Run without a visible browser, or run the tests:

```powershell
.\.venv\Scripts\python.exe main.py --headless
.\.venv\Scripts\python.exe -m pytest tests -q
```

Tests use temporary files, fictional profiles, mocked network responses, and local
HTML forms. They do not contact employment websites or submit real applications.

See [configuration](docs/CONFIGURATION.md) for private settings and authorized
test-host controls, and [security](SECURITY.md) for the boundaries and audit limits.
Normal demonstrations do not need `.env`, personal resumes, or an Ollama model.

## Project Structure

| Path | Purpose |
| --- | --- |
| `main.py` | Mock-default entry point and retained terminal workflow |
| `demo.py` | Fictional local demonstration |
| `safety.py` | Test-host and local-model checks |
| `config.py` | Defaults and private configuration loading |
| `discovery.py` | Public posting sources |
| `job_parser.py` | Posting normalization and filters |
| `matcher.py` | PDF text, skills, and heuristic scoring |
| `autofill.py` | Form recognition and browser filling |
| `cover_letter.py` | Template and optional local-model letters |
| `tracker.py` | SQLite tracking and duplicate detection |
| `setup_boards.py` | Optional public board availability checks |
| `tests/` | Automated tests and local fixtures |
| `examples/` | Fictional configuration examples |
| `scripts/audit_release.py` | Supplemental publication checks |
| `docs/` | Configuration, audit, and release guidance |
| `data/`, `resumes/`, `outputs/` | Private local files excluded from publication |

## Screenshots or Demonstrations

Run the mock demo above to see the form-filling workflow. No screenshots from real
application sessions are included. Use fictional data for any future recording.

## Limitations

This project is not intended for real-world deployment or job submissions. Form
recognition, repeated sections, extraction, and matching are incomplete heuristics.
Source metadata can be stale. Resume dates may omit days, and some questions remain
manual. Template and model-generated letters can require correction.

Remote testing requires explicit opt-in and an exact allowed hostname. Authorization,
sponsorship, credentials, CAPTCHAs, and final submission remain manual. These controls
reduce accidental use; they are not a security sandbox or a guarantee of correctness.
Dependencies use minimum-version constraints and are not a reproducible lockfile.

## Disclaimer — Experimental and Educational Use Only

This repository is a personal learning and self-testing project developed to explore Python programming, browser automation, and automated workflows.

It is an experimental proof of concept (PoC), not a fully functional, production-ready application or commercial service.

The project was created solely for educational purposes, technical experimentation, and personal skill development.

It is not intended to be used for submitting real job applications, mass-applying to positions, spamming employers, or circumventing employment platform policies.

All demonstrations and testing should be performed using mock data or explicitly authorized testing environments.

The code is provided as-is, without guarantees of functionality, reliability, security, or suitability for real-world use.

