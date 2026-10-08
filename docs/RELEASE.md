# Public release review

Suggested repository name: `job-application-automation`

Description: Experimental Python automation project developed for personal learning
and self-testing. Educational proof of concept, not intended for real job submissions.

Suggested topics: `python`, `automation`, `browser-automation`, `educational-project`,
`proof-of-concept`, `software-engineering`, `experimental`.

The owner approved the first public release on October 8, 2026. A local Git
repository was initialized because none existed. Release commits use the owner's
GitHub username and noreply email; global identity settings are unchanged.
The commands below document the review and publication workflow for future releases.
Author name and email appear in commit metadata; use a GitHub-provided noreply email
if you want email privacy.
To set that only for this repository, run `git config user.email "YOUR_GITHUB_NOREPLY_ADDRESS"`.

## Local review commands

```powershell
.\.venv\Scripts\python.exe scripts/audit_release.py
.\.venv\Scripts\python.exe -m pytest tests -q
git ls-files
git status --short
git diff --cached --stat
git diff --cached
```

Stage only reviewed source and example files, then repeat the checks:

```powershell
git add .gitignore .env.example README.md SECURITY.md requirements.txt companies.json
git add main.py config.py discovery.py job_parser.py matcher.py autofill.py cover_letter.py tracker.py setup_boards.py demo.py safety.py
git add tests docs examples scripts resumes/PUT_RESUMES_HERE.txt
.\.venv\Scripts\python.exe scripts/audit_release.py
git diff --cached --check
git diff --cached --stat
```

Do not use `git add -f` for private files. Inspect the full staged diff locally.

## After explicit approval of the final audit

The following commands are instructions only. Do not publish until the audit and
license choice have been reviewed and approved. Check existing remotes before adding
one; do not overwrite a remote or an existing GitHub repository.

```powershell
git commit -m "docs: prepare experimental project for public GitHub release"
git remote -v
```

Create an empty GitHub repository under your existing account after approval,
without initializing a README or license there. Replace `YOUR_GITHUB_USERNAME`:

```powershell
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/job-application-automation.git
git push -u origin main
```

After approval and publication, configure GitHub's secret scanning/push protection,
dependency alerts, and private vulnerability reporting where available. Local
`.gitignore` rules do not configure those hosted settings.

## License options

- No license for now: public visibility does not grant a general reuse license.
- MIT: broad reuse permission, with copyright and license notices retained.
- Apache 2.0: broad reuse with an explicit patent grant and additional notice terms.
- GPL-3.0: distributed derivative works generally must use the same license.

The owner selected no license for this release. A license is separate from the
educational-use disclaimer; permissive licensing does not restrict reuse to education.
