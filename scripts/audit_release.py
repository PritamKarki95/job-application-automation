import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "private key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "GitHub token": r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b",
    "AWS key": r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    "OpenAI-style key": r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b",
    "Slack token": r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b",
    "credential assignment": r'''(?i)(?:api_key|access_token|client_secret|password)\s*[:=]\s*["'][A-Za-z0-9/+_=.-]{16,}["']''',
    "user-specific path": r"(?i)[A-Z]:[\\/]+Users[\\/]+(?!<|example|you\b)[A-Za-z0-9_.-]+",
}


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout


def main():
    try:
        tracked = git("ls-files", "-z").decode().split("\0")
        candidates = sorted(set(git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")) - {""})
        ignored_tracked = [p for p in git("ls-files", "-ci", "--exclude-standard", "-z").decode().split("\0") if p]
    except subprocess.CalledProcessError:
        print("Audit requires a Git repository. No files were published.")
        return 2
    private_values = set()
    private_profile = ROOT / "data" / "profile.json"
    if private_profile.exists():
        profile = json.loads(private_profile.read_text(encoding="utf-8"))
        for key in ("first_name", "last_name", "email", "phone", "linkedin", "github", "portfolio"):
            value = profile.get(key, "")
            if isinstance(value, str) and len(value) >= 4:
                private_values.add(value.lower())
        for row in profile.get("experience", []):
            if row.get("employer"):
                private_values.add(row["employer"].lower())
    findings = [(path, "ignored file already tracked") for path in ignored_tracked]
    for name in candidates:
        path = ROOT / name
        if not path.is_file():
            continue
        if path.suffix.lower() in {".pdf", ".doc", ".docx", ".db", ".sqlite", ".sqlite3", ".png", ".jpg", ".jpeg", ".lnk"}:
            findings.append((name, "binary or personal artifact needs explicit review"))
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            findings.append((name, "unrecognized binary needs review"))
            continue
        for category, pattern in PATTERNS.items():
            if re.search(pattern, text):
                findings.append((name, category))
        if any(value in text.lower() for value in private_values):
            findings.append((name, "matches local private applicant data"))
        emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        if any(email.rsplit("@", 1)[1] not in {"example.com", "example.org", "example.net"} for email in emails):
            findings.append((name, "non-example email address needs review"))
    print(f"Reviewed {len(candidates)} publication candidates; {len([p for p in tracked if p])} tracked files.")
    for name, category in sorted(set(findings)):
        print(f"REVIEW: {name}: {category}")
    print("Pattern and private-value checks cannot prove the absence of secrets.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
