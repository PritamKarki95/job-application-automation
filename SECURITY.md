# Security and testing scope

Use fictional data and local fixtures. This project is an educational experiment,
not an application-submission service. Do not test against employment websites
without authorization.

## Defaults

- `python main.py` runs the mock demonstration without reading private profiles.
- The demonstration blocks HTTP/HTTPS requests and disables its submit button.
- The browser automation does not click Submit or press Enter in forms.
- Autofill permits local forms by default. Remote forms require both explicit
  testing opt-in and an exact hostname in `authorized_test_hosts`.
- Browser sessions are ephemeral; cookies and storage state are not saved.
- Ollama is off by default and restricted to loopback addresses when enabled.

## Local data

`data/`, `outputs/`, personal resumes, environment files, browser state, logs,
databases, and local IDE settings are excluded from Git. Do not force-add them.
Ignored files remain on disk and may contain personal information. Uploading
the entire folder through a browser or sharing a ZIP does not apply `.gitignore`.

Authorized testing may upload profile fields and documents to a test form.
Only use fictional data. Terminal output can contain filled field values;
do not publish recordings or logs from sessions using a real profile.

## Audit limits

Run `python scripts/audit_release.py` before staging or publishing. It inspects
the Git publication candidate set, ignored tracked files, common secret patterns,
and values from the local private profile without printing their contents.
It is a supplemental check, not a replacement for Gitleaks or manual review.

Inspect the staged diff before committing. A clean scan cannot prove the absence
of secrets. Dependency advisories change, and the requirements are minimum-version
constraints rather than a reproducible lockfile.

If a credential is committed, revoke or rotate it first. Removing the current
file does not remove earlier commits. Review any history cleanup separately;
this project does not automatically rewrite Git history.

## Reporting

Do not include credentials or personal applicant data in public issues. For a
public release, enable GitHub private vulnerability reporting and secret scanning
where available. No hosted GitHub repository or repository settings are configured
by the local preparation process.
