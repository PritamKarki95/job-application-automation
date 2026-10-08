# Local release audit

Initial review: October 7, 2026. Final publication review: October 8, 2026.
The owner explicitly approved public repository creation and publication of the
reviewed files on October 8. The repository remains unlicensed by request.

## Project review

Python, Playwright, Requests, BeautifulSoup, pdfplumber, python-docx, ReportLab,
python-dotenv, pytest, SQLite, and optional local Ollama are present. Local HTML
fixtures exercise browser form handling. Matching, source parsing, cover letters,
and dropdown recognition are experimental heuristics. There is no automatic
submission, deployed service, or retained GUI.

## Data and history

Private profile/contact details, employment history, resume text cache, PDFs,
generated letters, and a local application database exist on disk. They were
preserved and excluded from publication. No credential values are included here.
Browser contexts are ephemeral; no saved cookie/session mechanism was found in
the application code.

The folder originally had no Git repository, ancestor repository, or available
commit history. A new empty local repository was initialized on `main`. There is
no earlier history to scan in this checkout, and no history was rewritten. This
does not establish that copies elsewhere have never contained private data.

The local commit identity uses the owner's GitHub username and GitHub noreply
email. Global Git settings are unchanged; the personal contact email is not used
for this release's commit metadata.

## Changes

- Default startup now runs a fictional local demo, not the integration workflow.
- The demo blocks HTTP/HTTPS traffic and disables its form submission button.
- Remote autofill requires explicit testing opt-in and an exact authorized host.
- The automation context blocks requests to unlisted hosts, including redirects.
- Authorization questions, authentication, CAPTCHAs, and Submit remain manual.
- Ollama is off by default and restricted to local loopback URLs.
- Git exclusions cover private data, environment variants, documents, databases,
  sessions, credentials, profiles, logs, cache files, and local IDE settings.
- `.env.example` contains only a local service example and a model placeholder.
- README, configuration, security, release guidance, and fictional examples are included.

## Verification

The Git publication candidate scan checked common key/token patterns and values
from the private applicant profile without printing the values. No findings were
reported in eligible source/example files. Git ignore checks confirmed private
profile, PDFs, database, output files, environment variants, browser state, logs,
and IDE settings are excluded; `.env.example` and fictional examples remain eligible.

Gitleaks and TruffleHog were not installed. The included scanner is a supplemental
pattern check, not a comprehensive credential detector. No exposed credential was
identified, so no specific rotation is recommended. Revoke/rotate any credential
you discover in another published copy or history.

`pip-audit -r requirements.txt` resolved the requirements and reported no known
vulnerabilities at review time. This checks the current resolution, not every older
version allowed by the minimum constraints. Browser binaries and arbitrary local
services are outside that audit. Requirements are not a lockfile.

The mock demo ran headlessly: eight fictional fields were filled, one temporary
mock PDF was attached, and no submission occurred. The private application database
is not used by the demo. Tests use local fixtures and mocked source responses.

## Remaining review

The 69 tests passed, the staged diff passed whitespace checks, and the final
publication candidate scan found no credential-pattern or private-profile matches.
No hosted repository security settings have been enabled; review those settings
on GitHub. A clean scan and passing tests cannot prove the absence of vulnerabilities
or personal information.
