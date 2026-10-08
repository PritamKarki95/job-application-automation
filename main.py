from __future__ import annotations

import json
import sys

import config
import tracker
from job_parser import evaluate, parse_job_url
from matcher import load_resume_info, score_job

LINE = "-" * 72


def ask(prompt: str, default: str = "") -> str:
    try:
        ans = input(prompt).strip()
    except EOFError:
        return default
    return ans or default


def yes(prompt: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    a = ask(f"{prompt} [{d}] ").lower()
    return default if not a else a in ("y", "yes")


def ensure_profile() -> dict:
    profile = config.load_profile()
    missing = config.missing_profile_fields(profile)
    if missing or not config.PROFILE_FILE.exists():
        print("\nFirst, a few details for your applications (saved only on this computer in data/profile.json).")
        prompts = {"first_name": "Legal first name", "last_name": "Legal last name", "email": "Email",
                   "phone": "Phone number"}
        for f in missing:
            while not profile.get(f):
                profile[f] = ask(f"  {prompts[f]}: ")
        for f, label in [("linkedin", "LinkedIn URL"), ("github", "GitHub URL"), ("portfolio", "Portfolio URL")]:
            if not profile.get(f):
                profile[f] = ask(f"  {label} (Enter to skip): ")
        if not profile.get("extra_links"):
            print("  Any other links to fill in automatically (Kaggle, Devpost, Hugging Face, personal site...)?")
            add_extra_links(profile)
        print(f"  School: {profile['university']} | {profile['degree']} in {profile['major']} | {profile['graduation']}")
        print("  (Edit data/profile.json any time to change these, add your address, or adjust answers.)")
        config.save_profile(profile)
    return profile


def add_extra_links(profile: dict) -> None:

    links = profile.setdefault("extra_links", [])
    print("  Type one per line as  Label = URL   (e.g.  Kaggle = https://kaggle.com/you). Enter when done.")
    while True:
        line = ask("    > ")
        if not line:
            return
        label, sep, url = line.partition("=")
        label, url = label.strip(), url.strip()
        if not sep or not label or not url.lower().startswith(("http://", "https://")):
            print("    Please use the format  Label = https://...")
            continue
        links[:] = [l for l in links if l.get("label", "").lower() != label.lower()]
        links.append({"label": label, "url": url})
        print(f"    Added {label}.")


def edit_extra_links(profile: dict) -> None:
    while True:
        links = profile.get("extra_links") or []
        print("\n  Your extra links:")
        if not links:
            print("    (none)")
        for i, l in enumerate(links, 1):
            kw = f"  (also matches: {', '.join(l['keywords'])})" if l.get("keywords") else ""
            print(f"    {i}. {l.get('label')}: {l.get('url')}{kw}")
        c = ask("  [a] add  [r 2] remove #2  [Enter] done: ").lower()
        if not c:
            config.save_profile(profile)
            return
        if c == "a":
            add_extra_links(profile)
        elif c.startswith("r") and c[1:].strip().isdigit() and 1 <= int(c[1:].strip()) <= len(links):
            removed = links.pop(int(c[1:].strip()) - 1)
            print(f"  Removed {removed.get('label')}.")
        config.save_profile(profile)


def check_resumes(resume_info: dict) -> None:
    for key, info in resume_info.items():
        if not info.get("exists"):
            print(f"  ! Missing {config.RESUMES[key]} - put your {config.RESUME_LABELS[key]} there.")
        elif info.get("warning"):
            print(f"  ! {config.RESUMES[key].name}: {info['warning']}")


def show_job_line(n: int, row: dict) -> None:
    flag = " [REVIEW]" if row.get("flags") else ""
    mode = row.get("work_mode") or ""
    print(f"{n:>3}. [{row.get('score', '?'):>3}] {row['company'][:22]:<22} {row['title'][:42]:<42}"
          f" {row.get('location', '')[:24]} {('(' + mode + ')') if mode else ''}{flag}")


def show_job_detail(row: dict) -> None:
    print(LINE)
    print(f"{row['title']} - {row['company']}")
    print(f"Location: {row.get('location') or 'not listed'} ({row.get('work_mode') or '?'})"
          f"   Posted: {row.get('posted') or '?'}   Dates: {row.get('dates') or '?'}")
    print(f"Link: {row.get('apply_url') or row.get('url')}")
    expl = row.get("score_explain")
    if isinstance(expl, str):
        try:
            expl = json.loads(expl)
        except json.JSONDecodeError:
            expl = [expl]
    print(f"Match score: {row.get('score', '?')}/100")
    for e in expl or []:
        print(f"   - {e}")
    for f in row.get("flags") or []:
        print(f"   ! {f}")
    print(LINE)


def parse_selection(text: str, n: int) -> list[int]:
    picked = []
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        if part.lower() == "all":
            return list(range(1, n + 1))
        if "-" in part:
            a, _, b = part.partition("-")
            if a.isdigit() and b.isdigit():
                picked += [i for i in range(int(a), int(b) + 1) if 1 <= i <= n]
        elif part.isdigit() and 1 <= int(part) <= n:
            picked.append(int(part))
    return list(dict.fromkeys(picked))


def process_job(conn, job_pk: int, settings: dict, profile: dict, resume_info: dict) -> str:

    import autofill
    import cover_letter
    from matcher import select_resume

    row = tracker.row_to_job(tracker.get_job(conn, job_pk))
    show_job_detail(row)
    if row["status"] == "Submitted":
        print("  You already applied to this one - skipping.")
        return "Submitted"
    done = tracker.submitted_today(conn)
    if done >= settings["daily_limit"]:
        print(f"  Daily limit reached ({done}/{settings['daily_limit']} submitted today). Change it in Settings if you want.")
        return row["status"]
    if row.get("flags") and not yes("  This posting has items to review (above). Continue anyway?", default=True):
        tracker.set_status(conn, job_pk, "Skipped")
        return "Skipped"
    if not yes("  Prepare this application?", default=True):
        tracker.set_status(conn, job_pk, "Skipped")
        return "Skipped"


    key, conf, reason = select_resume(row, resume_info)
    if conf < 0.6:
        print(f"  I'm not sure which resume fits best: {reason}")
        a = ask("  Use [1] Software Developer or [2] AI/ML resume? ", "1" if key == "swe" else "2")
        key = "ai" if a.strip() == "2" else "swe"
    else:
        print(f"  Resume: {config.RESUME_LABELS[key]} ({reason})")
    resume_path = config.RESUMES[key]
    if not resume_path.exists():
        print(f"  ! {resume_path} is missing. Add it and try again.")
        tracker.set_status(conn, job_pk, "Failed", notes="resume file missing")
        return "Failed"


    letter = {}

    def make_letter():
        if not letter:
            print("  Generating cover letter...")
            letter.update(cover_letter.generate(row, profile, resume_info, key, settings))
            print(f"  Saved: {letter['docx']}" + (f" and {letter['pdf']}" if letter.get("pdf") else "")
                  + f"  [{letter['method']}]")
            tracker.update_fields(conn, job_pk, cover_letter=letter["docx"])
        return letter

    wants_cl = "cover letter" in (row.get("description") or "").lower()
    if yes("  Generate a cover letter now?" + (" (the posting mentions one)" if wants_cl else ""), default=wants_cl):
        make_letter()

    def cover_getter(kind: str):
        if not letter and not yes("  This form has a cover letter field. Generate one?", default=True):
            return None
        make_letter()
        if kind == "text":
            return letter["text"]
        return letter.get("pdf") or letter.get("docx")

    tracker.set_status(conn, job_pk, "Prepared", resume=key)
    if not yes("  Open the application in the browser and fill it?", default=True):
        print("  Saved as Prepared - you can finish it later from 'Process saved internships'.")
        return "Prepared"
    result = autofill.run_application(row, profile, settings, str(resume_path), cover_getter, ask=ask)
    outcome = result["outcome"]
    if outcome == "submitted":
        tracker.set_status(conn, job_pk, "Submitted", notes=result["note"])
        print(f"  Recorded as SUBMITTED. ({tracker.submitted_today(conn)}/{settings['daily_limit']} today)")
        return "Submitted"
    if outcome == "skipped":
        tracker.set_status(conn, job_pk, "Skipped")
        print("  Skipped.")
        return "Skipped"
    tracker.set_status(conn, job_pk, "Failed", notes=result["note"])
    print(f"  Marked as Failed ({result['note']}). It stays in your list for a retry.")
    return "Failed"


def process_many(conn, ids: list[int], settings, profile, resume_info) -> None:
    for n, job_pk in enumerate(ids, 1):
        print(f"\n=== {n} of {len(ids)} ===")
        try:
            process_job(conn, job_pk, settings, profile, resume_info)
        except KeyboardInterrupt:
            print("\n  Stopped. Remaining jobs stay in your list.")
            return
        if tracker.submitted_today(conn) >= settings["daily_limit"]:
            print("\n  Daily limit reached - stopping here.")
            return
        if n < len(ids) and not yes("\n  Continue to the next one?", default=True):
            return


def find_internships(conn, settings, profile, resume_info) -> None:
    import discovery
    print("\n  [1] Broader employer search (other employers first)")
    print("  [2] Configured company boards (companies.json)")
    choice = ask("  Search source [1]: ", "1")
    if choice != "2":
        res = discovery.discover_community(settings, resume_info)
        save_discovery_results(conn, settings, profile, resume_info, res)
        return
    companies = config.load_companies()
    total = sum(len(v) for v in companies.values())
    if not total:
        print("  companies.json has no boards listed. Add some and try again.")
        return
    print(f"\nSearching {total} public job boards from companies.json "
          f"(Greenhouse {len(companies['greenhouse'])}, Lever {len(companies['lever'])}, Ashby {len(companies['ashby'])})...")
    res = discovery.discover(settings, companies)
    save_discovery_results(conn, settings, profile, resume_info, res)


def save_discovery_results(conn, settings, profile, resume_info, res):
    print("\nSources searched:")
    for source, board, status, n, k in res["report"]:
        mark = "ok " if status == "ok" else "!! "
        print(f"  {mark}{source:<10} {board:<22} {status if status != 'ok' else f'{n} postings, {k} matching internships'}")
    print("  (Only the sources above were searched. Google and job-site searches are available in menu 7.)")
    new = 0
    found_ids = []
    for job in res["kept"]:
        s = score_job(job, resume_info, settings)
        pk, is_new = tracker.upsert_job(conn, job, s)
        found_ids.append(pk)
        new += is_new
    print(f"\n  {len(res['kept'])} internships passed the filters ({new} new). "
          f"{len(res['rejected'])} other internship postings were filtered out.")
    if res["rejected"] and yes("  Show why some were filtered out?"):
        for job, reasons in res["rejected"][:30]:
            print(f"    x {job['company']}: {job['title'][:50]} - {'; '.join(reasons)}")
    pick_and_apply(conn, settings, profile, resume_info, ["Discovered", "Shortlisted", "Failed"], found_ids)


def search_google(settings, resume_info):
    import webbrowser
    from urllib.parse import urlencode
    season = settings.get("target_season", "Summer 2027")
    skills = set().union(*(set(info.get("skills", [])) for info in resume_info.values()))
    skill = "Python" if "Python" in skills else "Java" if "Java" in skills else "software"
    queries = [
        f'"{season}" "software" "intern" ("Louisiana" OR "Monroe" OR "Baton Rouge")',
        f'"{season}" "software" "intern" ("Dallas" OR "Austin" OR "Texas")',
        f'"{season}" "{skill}" "intern" ("startup" OR "small business")',
        f'"{season}" "software" "intern" ("Minnesota" OR "Ohio")',
        f'"{season}" "machine learning" "intern" "remote"',
        f'"{season}" "software" "intern" (site:wellfound.com OR site:workatastartup.com)',
    ]
    print("\nTargeted Google searches:")
    for i, query in enumerate(queries, 1):
        print(f"  {i}. {query}")
    print("  Open a result, copy its company Apply link, then use menu 2 to add and score it.")
    selection = ask("  Open search 1-6 (Enter to return): ")
    if selection.isdigit() and 1 <= int(selection) <= len(queries):
        url = "https://www.google.com/search?" + urlencode({"q": queries[int(selection) - 1]})
        print(f"  Search: {url}")
        webbrowser.open(url)


def pick_and_apply(conn, settings, profile, resume_info, statuses, allowed_ids=None) -> None:
    rows = [tracker.row_to_job(r) for r in tracker.list_jobs(conn, statuses, limit=2000 if allowed_ids is not None else 200)]
    if allowed_ids is not None:
        allowed = set(allowed_ids)
        rows = [row for row in rows if row["id"] in allowed]
    rows = [r for r in rows if (r.get("score") or 0) >= settings["min_score"]][: settings["max_display"]]
    if not rows:
        print(f"\n  Nothing to show (status {', '.join(statuses)}, score >= {settings['min_score']}).")
        return
    print(f"\nTop matches (score >= {settings['min_score']}):")
    for i, r in enumerate(rows, 1):
        show_job_line(i, r)
    while True:
        print("\n  Type numbers to apply now (e.g. 1,3,5-7), 'd 2' for details, 'save 1,4' to shortlist,"
              " 'skip 2' to hide, or Enter to go back.")
        cmd = ask("  > ")
        if not cmd:
            return
        low = cmd.lower()
        if low.startswith("d "):
            for i in parse_selection(cmd[2:], len(rows)):
                show_job_detail(rows[i - 1])
            continue
        if low.startswith("save "):
            for i in parse_selection(cmd[5:], len(rows)):
                tracker.set_status(conn, rows[i - 1]["id"], "Shortlisted")
            print("  Shortlisted.")
            continue
        if low.startswith("skip "):
            for i in parse_selection(cmd[5:], len(rows)):
                tracker.set_status(conn, rows[i - 1]["id"], "Skipped")
            print("  Hidden.")
            continue
        picked = parse_selection(cmd, len(rows))
        if not picked:
            print("  I didn't understand that.")
            continue
        for i in picked:
            if rows[i - 1]["status"] in ("Discovered", "Skipped"):
                tracker.set_status(conn, rows[i - 1]["id"], "Shortlisted")
        process_many(conn, [rows[i - 1]["id"] for i in picked], settings, profile, resume_info)
        return


LINKS_FILE = config.BASE_DIR / "job_links.txt"


def read_multiline(prompt: str) -> str:
    print(prompt)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def job_from_link(url: str) -> dict | None:

    from job_parser import canonical_job_site_url, job_site_name, new_job, split_qualifications
    url = url.strip()
    site = job_site_name(url)
    if not site:
        try:
            print(f"  Reading {url[:70]} ...")
            return parse_job_url(url)
        except ValueError as e:
            print(f"  ! {e}")
            if not yes("  Add it anyway and enter the details yourself?", default=True):
                return None
            return manual_job(url, url, "", "manual")

    clean, site_id = canonical_job_site_url(url)
    print(f"\n  {site} link: {clean}")
    print(f"  I can't read {site} pages automatically ({site}'s rules don't allow it), so pick one:")
    print("    [1] Paste the company's own Apply link (on the posting, click Apply -> copy the address).")
    print("        Best option: I can read the full posting and fill the form.")
    print(f"    [2] Type the company, title and (optionally) paste the job description from {site}.")
    print(f"        Use this for {site} 'Easy Apply' jobs or if you'll click Apply in the browser later.")
    print("    [3] Skip this link")
    c = ask("  Choose 1-3 [1]: ", "1")
    if c == "3":
        return None
    if c == "1":
        company_url = ask("  Company Apply link: ")
        if company_url and not job_site_name(company_url):
            try:
                job = parse_job_url(company_url)
                job["url"] = clean
                job["flags"] = list(job.get("flags") or []) + [f"Found on {site}"]
                return job
            except ValueError as e:
                print(f"  ! {e} Let's enter the details instead.")
                return manual_job(clean, company_url, site_id, site.lower())
        print("  No company link given - let's enter the details instead.")
    return manual_job(clean, clean, site_id, site.lower())


def manual_job(url: str, apply_url: str, job_id: str, source: str) -> dict:
    from job_parser import detect_work_mode, extract_dates, new_job, split_qualifications
    company = ask("  Company name: ", "Unknown")
    title = ask("  Internship title: ", "Internship")
    location = ask("  Location (e.g. Dallas, TX or Remote; Enter to skip): ")
    desc = ""
    if yes("  Paste the job description? (makes the match score and cover letter much better)", default=True):
        desc = read_multiline("  Paste it below, then type END on its own line and press Enter:")
    req, pref = split_qualifications(desc)
    job = new_job(source=source, company=company, title=title, location=location,
                  work_mode=detect_work_mode(location, desc), description=desc, required=req, preferred=pref,
                  dates=extract_dates(f"{title} {desc}"), url=url, apply_url=apply_url, job_id=job_id)
    if not desc:
        job["flags"].append("No job description saved - score is a rough guess")
    return job


def collect_links() -> list[str]:
    import re as _re
    print("\n  Paste one or more job links (LinkedIn, Indeed, Handshake, company career pages...),")
    print(f"  one per line, then press Enter on an empty line. Or type 'file' to load {LINKS_FILE.name}.")
    links = []
    while True:
        line = ask("  > ")
        if not line:
            break
        if line.lower() == "file":
            if not LINKS_FILE.exists():
                LINKS_FILE.write_text("# Put one job link per line. Lines starting with # are ignored.\n", encoding="utf-8")
                print(f"  Created {LINKS_FILE} - add your links there and choose 'file' again.")
                continue
            got = [l.strip() for l in LINKS_FILE.read_text(encoding="utf-8").splitlines()
                   if l.strip() and not l.strip().startswith("#")]
            print(f"  Loaded {len(got)} links from {LINKS_FILE.name}.")
            links += got
            continue
        links += _re.findall(r"https?://\S+", line) or [line]
    return list(dict.fromkeys(links))


def apply_by_links(conn, settings, profile, resume_info) -> None:
    from job_parser import canonical_job_site_url, job_site_name
    links = collect_links()
    if not links:
        return
    ids = []
    for n, url in enumerate(links, 1):
        print(f"\n--- Link {n} of {len(links)} ---")

        probe = {"url": canonical_job_site_url(url)[0] if job_site_name(url) else url,
                 "job_id": canonical_job_site_url(url)[1] if job_site_name(url) else ""}
        dup = tracker.find_duplicate(conn, probe)
        if dup:
            print(f"  Already in your list: {dup['company']} - {dup['title']} (status: {dup['status']})")
            if dup["status"] not in ("Submitted",):
                ids.append(dup["id"])
            continue
        job = job_from_link(url)
        if not job:
            continue
        ok, reasons = evaluate(job)
        s = score_job(job, resume_info, settings)
        pk, is_new = tracker.upsert_job(conn, job, s)
        row = tracker.row_to_job(tracker.get_job(conn, pk))
        if not is_new:
            print(f"  You've seen this one before (status: {row['status']}).")
            if row["status"] == "Submitted":
                continue
        print(f"  Added: [{s['score']}] {row['company']} - {row['title']}")
        if not ok:
            print("  Heads up - this may not fit your rules: " + "; ".join(reasons))
            if not yes("  Keep it anyway?", default=True):
                tracker.set_status(conn, pk, "Skipped")
                continue
        ids.append(pk)
    if not ids:
        return
    ids = list(dict.fromkeys(ids))
    print(f"\n  {len(ids)} job(s) ready.")
    c = ask("  [a] apply now, one by one   [s] save them for later (menu 3)   [a]: ", "a").lower()
    if c == "s":
        for pk in ids:
            if tracker.get_job(conn, pk)["status"] in ("Discovered", "Skipped"):
                tracker.set_status(conn, pk, "Shortlisted")
        print("  Saved to your shortlist.")
        return
    process_many(conn, ids, settings, profile, resume_info)


def view_applications(conn) -> None:
    counts = dict(conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall())
    print("\n  " + "  ".join(f"{s}: {counts.get(s, 0)}" for s in tracker.STATUSES))
    print(f"  Submitted today: {tracker.submitted_today(conn)}")
    f = ask("  Show which status? (e.g. Submitted, Failed, all) [Submitted]: ", "Submitted")
    statuses = None if f.lower() == "all" else [s for s in tracker.STATUSES if s.lower() == f.lower()]
    if statuses == []:
        print("  Unknown status.")
        return
    rows = [tracker.row_to_job(r) for r in tracker.list_jobs(conn, statuses, order="updated_at DESC")]
    if not rows:
        print("  None yet.")
        return
    for i, r in enumerate(rows, 1):
        when = (r.get("applied_at") or r.get("updated_at") or "")[:10]
        print(f"{i:>3}. {r['status']:<11} {when}  [{r.get('score') or '?':>3}] {r['company'][:20]:<20} "
              f"{r['title'][:38]:<38} {('resume: ' + r['resume']) if r.get('resume') else ''}")
    c = ask("\n  'd 3' details, 'mark 3 Submitted' to fix a status, or Enter to go back: ")
    if c.lower().startswith("d "):
        for i in parse_selection(c[2:], len(rows)):
            show_job_detail(rows[i - 1])
            if rows[i - 1].get("cover_letter"):
                print(f"  Cover letter: {rows[i - 1]['cover_letter']}")
            if rows[i - 1].get("notes"):
                print(f"  Notes: {rows[i - 1]['notes']}")
    elif c.lower().startswith("mark "):
        parts = c.split()
        if len(parts) == 3 and parts[1].isdigit() and 1 <= int(parts[1]) <= len(rows):
            new = next((s for s in tracker.STATUSES if s.lower() == parts[2].lower()), None)
            try:
                if not new:
                    raise tracker.TransitionError("Unknown status")
                if new == "Submitted" and not yes("  Confirm you actually submitted this application?"):
                    return
                tracker.set_status(conn, rows[int(parts[1]) - 1]["id"], new)
                print("  Updated.")
            except tracker.TransitionError as e:
                print(f"  ! {e}")


def change_settings(settings, profile, resume_info):
    while True:
        w = settings["weights"]
        print(f"""
  1. Daily submission limit ......... {settings['daily_limit']}
  2. Minimum match score ............ {settings['min_score']}
  3. Score weights .................. skills {w['skills']}, track {w['track']}, location {w['geo']}, timing {w['timing']}
  4. Use local Ollama for letters ... {'on' if settings['use_ollama'] else 'off'} (model {settings['ollama_model']})
  5. Fill voluntary demographic answers {'on' if settings['fill_demographics'] else 'off'}
  6. Browser ........................ {settings['browser_channel'] or 'Playwright Chromium'}
  7. Edit my contact details (email, phone, LinkedIn, GitHub, portfolio)
  8. Edit my extra links (Kaggle, Devpost, etc.) ... {len(profile.get('extra_links') or [])} saved
  9. Show what was read from my resumes
  10. Back""")
        c = ask("  Choose: ", "10")
        try:
            if c == "1":
                settings["daily_limit"] = max(1, int(ask("  New daily limit: ", str(settings["daily_limit"]))))
            elif c == "2":
                settings["min_score"] = max(0, min(100, int(ask("  Minimum score 0-100: ", str(settings["min_score"])))))
            elif c == "3":
                for k, name in [("skills", "Skills"), ("track", "Role/track"), ("geo", "Location"), ("timing", "Timing")]:
                    w[k] = max(0, int(ask(f"  {name} weight [{w[k]}]: ", str(w[k]))))
                if sum(w.values()) == 0:
                    print("  Weights can't all be zero - resetting.")
                    settings["weights"] = dict(config.DEFAULT_SETTINGS["weights"])
            elif c == "4":
                settings["use_ollama"] = yes("  Use Ollama when it's running?", settings["use_ollama"])
                settings["ollama_model"] = ask(f"  Model name [{settings['ollama_model']}]: ", settings["ollama_model"])
            elif c == "5":
                settings["fill_demographics"] = yes("  Fill voluntary race/veteran/disability questions from your profile?",
                                                    settings["fill_demographics"])
            elif c == "6":
                b = ask("  Browser: [1] Playwright Chromium  [2] Microsoft Edge  [3] Google Chrome: ", "1")
                settings["browser_channel"] = {"2": "msedge", "3": "chrome"}.get(b, "")
            elif c == "7":
                for f in ["first_name", "last_name", "email", "phone", "linkedin", "github", "portfolio"]:
                    cur = profile.get(f, "")
                    a = ask(f"  {f.replace('_', ' ').title()} [{cur or 'blank'}] (Enter = keep, '-' = clear): ", cur)
                    profile[f] = "" if a == "-" else a
                config.save_profile(profile)
                print("  Saved. Leave a link blank and that field is simply left empty on forms.")
                print("  (Address, demographics and work-authorization answers are in data/profile.json.)")
            elif c == "8":
                edit_extra_links(profile)
            elif c == "9":
                info = load_resume_info(force=True)
                resume_info.clear()
                resume_info.update(info)
                for key, ri in info.items():
                    print(f"\n  {config.RESUME_LABELS[key]}: {'found' if ri.get('exists') else 'MISSING'}")
                    if ri.get("exists"):
                        print(f"    Skills found: {', '.join(ri['skills']) or '(none)'}")
                        for p in ri.get("projects", []):
                            print(f"    Project: {p['name']} - {p['description'][:90]}...")
                        if not ri.get("projects"):
                            print("    No projects section detected. You can list projects in data/profile.json.")
            else:
                config.save_settings(settings)
                return
            config.save_settings(settings)
        except ValueError:
            print("  Please enter a number.")


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Experimental job workflow project; mock demo by default.")
    parser.add_argument("--authorized-testing", action="store_true", help="Enable integrations only for explicitly authorized testing")
    parser.add_argument("--headless", action="store_true", help="Run the mock demonstration without a visible browser")
    args = parser.parse_args(argv)
    if not args.authorized_testing:
        from demo import run_demo
        return run_demo(headless=args.headless)
    if not yes("Enable experimental integrations for an explicitly authorized testing environment?", default=False):
        return 0
    config.ensure_dirs()
    print(LINE)
    print("  Internship Application Helper  -  nothing is submitted without you")
    print(LINE)
    settings = config.load_settings()
    settings["authorized_testing"] = True
    profile = ensure_profile()
    resume_info = load_resume_info()
    check_resumes(resume_info)
    conn = tracker.connect()
    try:
        while True:
            print(f"""
  1. Find internships automatically
  2. Add jobs from links (LinkedIn, Indeed, company sites...)
  3. Process saved shortlisted internships
  4. View previous applications
  5. Change settings
  6. Exit
  7. Search Google for local / startup internships
  (submitted today: {tracker.submitted_today(conn)}/{settings['daily_limit']})""")
            c = ask("  Choose 1-7: ")
            try:
                if c == "1":
                    find_internships(conn, settings, profile, resume_info)
                elif c == "2":
                    apply_by_links(conn, settings, profile, resume_info)
                elif c == "3":
                    pick_and_apply(conn, settings, profile, resume_info, ["Shortlisted", "Prepared", "Failed"])
                elif c == "4":
                    view_applications(conn)
                elif c == "5":
                    change_settings(settings, profile, resume_info)
                elif c == "7":
                    search_google(settings, resume_info)
                elif c in ("6", "q", "exit"):
                    print("  Good luck!")
                    return 0
            except KeyboardInterrupt:
                print("\n  (cancelled - back to menu)")
            except tracker.TransitionError as e:
                print(f"  ! {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n  Bye.")
