from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import config
from safety import allowed_test_url


FIELD_RULES = [
    ("work_auth", r"authori[sz]ed to work|work authori[sz]ation|legally (?:authorized|eligible|permitted)|"
                  r"eligible to work|right to work|employment eligibility"),
    ("sponsorship", r"sponsor|\bvisa\b|immigration|h-?1b|\bcpt\b|\bopt\b(?!-?\s*(?:in|out)\b)|work permit"),
    ("eeo_hispanic", r"hispanic|latin[oax]"),
    ("eeo_race", r"\brace\b|ethnicit|racial"),
    ("eeo_veteran", r"veteran"),
    ("eeo_disability", r"disabilit"),
    ("eeo_gender", r"\bgender\b|\bsex\b"),
    ("preferred_name", r"preferred (?:first )?name|nickname"),
    ("first_name", r"first[\s_-]*name|given[\s_-]*name|\bfname\b"),
    ("last_name", r"last[\s_-]*name|family[\s_-]*name|surname|\blname\b"),
    ("full_name", r"full[\s_-]*name|legal name|your name|^name\b|\|\s*name\s*\|"),
    ("email", r"e-?mail"),
    ("phone", r"phone|mobile|\bcell\b|telephone"),
    ("linkedin", r"linked\s*in"),
    ("github", r"git\s*hub"),
    ("portfolio", r"portfolio|personal (?:web)?site|^website|\|\s*website|urls\[other\]|\bblog\b"),
    ("school", r"\bschool\b|universit|college|institution"),
    ("degree", r"\bdegree\b"),
    ("major", r"\bmajor\b|discipline|field of study|area of study"),
    ("grad_year", r"graduat\w*[^|]*\byear\b|\byear\b[^|]*graduat"),
    ("grad_month", r"graduat\w*[^|]*\bmonth\b|\bmonth\b[^|]*graduat"),
    ("grad_date", r"graduat|degree completion|completion date"),
    ("cover_letter_text", r"cover[\s_-]*letter"),
    ("street", r"street|address line 1|^address\b|\|\s*address\s*\|"),
    ("city", r"^city\b|\|\s*city\b"),
    ("state", r"^state\b|\|\s*state\b|province"),
    ("zip", r"\bzip\b|postal"),
    ("country", r"^country\b|\|\s*country\b"),
    ("location", r"current location|^location\b|\|\s*location\b|where are you (?:located|based)"),
]
FIELD_RULES = [(k, re.compile(rx, re.I)) for k, rx in FIELD_RULES]

MANUAL_ONLY = {"work_auth", "sponsorship"}
EEO_KEYS = {"eeo_hispanic", "eeo_race", "eeo_veteran", "eeo_disability", "eeo_gender"}

SUCCESS_RE = re.compile(
    r"thank(?:s| you) for (?:applying|your application|submitting)|application (?:has been |was )?"
    r"(?:received|submitted)|we(?:'ve| have) received your application|successfully submitted|"
    r"your application is (?:complete|in)", re.I)
DECLINE_RE = re.compile(r"decline|don'?t wish|do not wish|prefer not|not to (?:answer|disclose|self)|choose not|"
                        r"not wish to", re.I)
PLACEHOLDER_RE = re.compile(r"^\s*(?:--+|select\b|please select|choose\b|-+\s*select|none selected)?\s*\.{0,3}\s*$|"
                            r"^\s*(?:select|choose|please select)\b", re.I)

COLLECT_JS = r"""
() => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return (r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'); };
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  const labelOf = el => {
    const parts = [];
    if (el.labels && el.labels.length) parts.push([...el.labels].map(l => l.innerText).join(' '));
    if (el.getAttribute('aria-label')) parts.push(el.getAttribute('aria-label'));
    const lb = el.getAttribute('aria-labelledby');
    if (lb) lb.split(/\s+/).forEach(id => { const e = document.getElementById(id); if (e) parts.push(e.innerText); });
    if (!clean(parts.join(' '))) {
      const fs = el.closest('fieldset'); const lg = fs && fs.querySelector('legend');
      if (lg) parts.push(lg.innerText);
    }
    if (!clean(parts.join(' '))) {
      let p = el.parentElement;
      for (let i = 0; i < 4 && p; i++, p = p.parentElement) {
        const l = p.querySelector('label, legend, .application-label, [class*="label"], [class*="question"]');
        if (l && l !== el && clean(l.innerText)) { parts.push(l.innerText); break; }
      }
    }
    return clean(parts.join(' '));
  };
  const els = [...document.querySelectorAll('input, textarea, select')];
  let i = 0; const out = [];
  for (const el of els) {
    const type = (el.getAttribute('type') || el.tagName).toLowerCase();
    if (['hidden', 'submit', 'button', 'image', 'reset', 'search'].includes(type) && type !== 'file') continue;
    const visible = vis(el) || type === 'file';
    if (!visible) continue;
    const idx = 'ia' + (i++);
    el.setAttribute('data-ia', idx);
    const label = labelOf(el);
    let question = '';
    const workContainer = el.closest('fieldset, [data-experience], [class*="work-experience"], [class*="employment-history"]');
    const heading = workContainer && workContainer.querySelector('legend, h2, h3, h4');
    const context = heading ? clean(heading.innerText) : '';
    let workGroup = '';
    if (workContainer) {
      const groups = [...document.querySelectorAll('fieldset, [data-experience], [class*="work-experience"], [class*="employment-history"]')];
      workGroup = String(groups.indexOf(workContainer));
    }
    if (type === 'radio' || type === 'checkbox') {
      const fs = el.closest('fieldset'); const lg = fs && fs.querySelector('legend');
      if (lg) question = clean(lg.innerText);
      let p = el.parentElement;
      for (let k = 0; k < 5 && p && !question; k++, p = p.parentElement) {
        const l = [...p.querySelectorAll('label, legend, .application-label, [class*="label"], [class*="question"]')]
          .find(x => !x.contains(el) && !(el.labels && [...el.labels].includes(x)) && clean(x.innerText) && !x.querySelector('input'));
        if (l) question = clean(l.innerText);
      }
    }
    out.push({ question, context, workGroup,
      selectedText: el.tagName === 'SELECT' && el.selectedIndex >= 0 ? clean(el.options[el.selectedIndex].text) : '',
      idx, tag: el.tagName.toLowerCase(), type,
      name: el.getAttribute('name') || '', id: el.id || '',
      label, placeholder: el.getAttribute('placeholder') || '',
      autocomplete: el.getAttribute('autocomplete') || '',
      role: el.getAttribute('role') || '', ariaAuto: el.getAttribute('aria-autocomplete') || '',
      required: el.required || el.getAttribute('aria-required') === 'true' || /\*|✱|required/i.test(label),
      value: el.type === 'checkbox' || el.type === 'radio' ? (el.checked ? 'on' : '') : (el.value || ''),
      accept: el.getAttribute('accept') || '',
      options: el.tagName === 'SELECT' ? [...el.options].map(o => clean(o.text)) : [],
    });
  }
  return out;
}
"""


@dataclass
class FillReport:
    provider: str = "generic"
    filled: list = field(default_factory=list)
    uploaded: list = field(default_factory=list)
    manual: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    blocked: str = ""

    def merge(self, other: "FillReport"):
        self.filled += other.filled
        self.uploaded += other.uploaded
        self.manual += other.manual
        self.notes += other.notes
        self.blocked = self.blocked or other.blocked


def provider_for(url: str) -> str:
    u = (url or "").lower()
    if "greenhouse.io" in u or "gh_jid=" in u:
        return "greenhouse"
    if "lever.co" in u:
        return "lever"
    if "ashbyhq.com" in u:
        return "ashby"
    if "myworkdayjobs" in u or "workday" in u:
        return "workday"
    if "icims.com" in u or "taleo" in u or "successfactors" in u or "smartrecruiters" in u:
        return "other-ats"
    return "generic"


def application_url(job: dict) -> str:
    url = job.get("apply_url") or job.get("url") or ""
    if "jobs.lever.co" in url and not url.rstrip("/").endswith("/apply"):
        url = url.rstrip("/") + "/apply"
    if "jobs.ashbyhq.com" in url and "/application" not in url:
        url = url.rstrip("/") + "/application"
    return url


def classify_field(f: dict) -> str | None:
    key_text = " | ".join(x for x in [f["label"], f["name"], f["id"], f["autocomplete"], f["placeholder"]] if x)
    key_text = key_text.replace("_", " ")
    if f["type"] == "file":
        if re.search(r"cover", key_text, re.I):
            return "cover_letter_file"
        if re.search(r"resume|résumé|\bcv\b|curriculum", key_text, re.I):
            return "resume_file"
        return None

    for key, rx in FIELD_RULES[:2]:
        if rx.search(key_text):
            return key
    work_key = classify_experience_field(f)
    if work_key:
        return work_key

    lever_names = {"name": "full_name", "email": "email", "phone": "phone", "urls[LinkedIn]": "linkedin",
                   "urls[GitHub]": "github", "urls[Portfolio]": "portfolio", "urls[Other]": "portfolio",
                   "location": "location", "eeo[race]": "eeo_race", "eeo[gender]": "eeo_gender",
                   "eeo[veteran]": "eeo_veteran", "eeo[disability]": "eeo_disability"}
    if f["name"] in lever_names:
        return lever_names[f["name"]]
    label = f["label"] or ""

    long_question = len(label) > 120
    for key, rx in FIELD_RULES:
        if rx.search(key_text):
            if long_question and key not in MANUAL_ONLY | EEO_KEYS:
                return None
            if key in ("street", "city", "state", "zip", "country") and len(label) > 45:
                continue
            return key
    return None


def classify_experience_field(f):
    text = " | ".join(str(f.get(key) or "") for key in ("label", "name", "id", "placeholder")).replace("_", " ")
    context = f.get("context", "")
    if re.search(r"years? (?:of )?(?:work |professional )?experience|how (?:many|much)|why |salary|compensation", text, re.I):
        return None
    if re.search(r"(?:work|employment|professional) (?:history|experience)(?: summary)?", text, re.I) and f.get("tag") == "textarea":
        return "experience_summary"
    current = bool(re.search(r"current (?:employer|company|job title|position)", text, re.I))
    work_context = bool(re.search(r"experience|employment|work history|previous job", context + " " + text, re.I))
    rules = [("employer", r"employer|company name|organization name|current company"),
             ("title", r"job title|position title|role title|^title\b|^position\b"),
             ("description", r"responsibilities|job description|duties|description"),
             ("location", r"location|city"),
             ("start_month", r"start.*month|month.*start"), ("start_year", r"start.*year|year.*start"),
             ("end_month", r"end.*month|month.*end"), ("end_year", r"end.*year|year.*end"),
             ("start_date", r"start date|date started|from date"), ("end_date", r"end date|date ended|to date")]
    for key, pattern in rules:
        if re.search(pattern, text, re.I) and (work_context or current or key == "employer" and re.search(r"employer", text, re.I) or key == "title" and re.search(r"job title", text, re.I)):
            return ("current_work_" if current else "work_") + key
    return None


def experience_value(key, profile, index=0, field_type="text"):
    experiences = profile.get("experience") or []
    if key == "experience_summary":
        return "\n\n".join("\n".join(filter(None, [
            f"{row.get('title', '')} — {row.get('employer', '')}", row.get("location", ""),
            f"{row.get('start_date', '')} to {'Present' if row.get('current') else row.get('end_date', '')}",
            row.get("description", "")])) for row in experiences)
    if key.startswith("current_work_"):
        row = next((row for row in experiences if row.get("current") is True), {})
        part = key.removeprefix("current_work_")
    else:
        row = experiences[index] if index < len(experiences) else {}
        part = key.removeprefix("work_")
    if part in ("start_month", "end_month", "start_year", "end_year"):
        date = row.get(part.split("_")[0] + "_date", "")
        if not re.fullmatch(r"\d{4}-\d{2}", date):
            return ""
        return date[:4] if part.endswith("year") else MONTHS[int(date[5:]) - 1].title()
    value = row.get(part, "")
    if part in ("start_date", "end_date"):

        if field_type == "date":
            return value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else ""
        if part == "end_date" and row.get("current"):
            return "Present" if field_type == "text" else ""
    return str(value or "")


def profile_value(key: str, profile: dict) -> str:
    a = profile.get("address") or {}
    city_state = ", ".join(x for x in [a.get("city"), a.get("state")] if x)
    return {
        "first_name": profile.get("first_name", ""), "last_name": profile.get("last_name", ""),
        "preferred_name": profile.get("preferred_name", ""), "full_name": config.full_name(profile),
        "email": profile.get("email", ""), "phone": profile.get("phone", ""),
        "linkedin": profile.get("linkedin", ""), "github": profile.get("github", ""),
        "portfolio": profile.get("portfolio", ""), "school": profile.get("university", ""),
        "degree": profile.get("degree", ""), "major": profile.get("major", ""),
        "grad_year": profile.get("graduation_year", ""), "grad_month": profile.get("graduation_month", ""),
        "grad_date": profile.get("graduation", ""),
        "street": a.get("street", ""), "city": a.get("city", ""), "state": a.get("state", ""),
        "zip": a.get("zip", ""), "country": a.get("country", "") if a.get("street") else "",
        "location": city_state,
    }.get(key, "")


MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower())) - {"of", "the", "in", "a", "an", "and", "at"}


def choose_option(options: list[str], key: str, value: str, demographics: dict | None = None) -> int | None:

    opts = [(i, o) for i, o in enumerate(options) if o and not PLACEHOLDER_RE.match(o)]
    if not opts:
        return None
    v = (value or "").strip()
    if not v:
        return None

    def only(pred):
        hits = [i for i, o in opts if pred(o)]
        return hits[0] if len(hits) == 1 else None

    if key in EEO_KEYS:
        if v.lower() == "decline":
            return only(lambda o: bool(DECLINE_RE.search(o)))
        if key == "eeo_race":
            want = v.lower()
            return only(lambda o: re.search(rf"\b{re.escape(want)}\b", o, re.I) and not DECLINE_RE.search(o)
                        and not re.search(r"two or more", o, re.I))
        yes_no = "no" if re.match(r"\s*(no|i am not|not)\b", v, re.I) else ("yes" if re.match(r"\s*yes\b", v, re.I) else None)
        if key == "eeo_hispanic" and yes_no:
            if yes_no == "no":
                return only(lambda o: re.match(r"\s*no\b", o, re.I) or re.search(r"not hispanic|non-hispanic", o, re.I))
            return only(lambda o: re.match(r"\s*yes\b", o, re.I))
        if key == "eeo_veteran" and yes_no == "no":
            return only(lambda o: (re.search(r"\bnot\b[^.]*veteran|\bnot a veteran", o, re.I) or re.match(r"\s*no\b", o, re.I))
                        and not DECLINE_RE.search(o))
        if key == "eeo_disability" and yes_no == "no":
            return only(lambda o: (re.match(r"\s*no\b", o, re.I) or re.search(r"(?:do not|don'?t) have a disability", o, re.I))
                        and not DECLINE_RE.search(o))

        return only(lambda o: o.strip().lower() == v.lower())


    if key == "grad_month":
        m = int(v) if v.isdigit() else (MONTHS.index(v.lower()) + 1 if v.lower() in MONTHS else 0)
        if not m:
            return None
        return only(lambda o: o.strip().lower() in (MONTHS[m - 1], MONTHS[m - 1][:3], f"{m:02d}", str(m)))
    if key == "grad_year":
        return only(lambda o: o.strip() == v)

    alts = [v]
    if key == "degree" and re.search(r"bachelor", v, re.I):
        alts += ["Bachelor's Degree", "Bachelor's", "Bachelors", "BS", "B.S.", "Bachelor of Science (BS)"]
    for alt in alts:
        hit = only(lambda o: o.strip().lower() == alt.lower())
        if hit is not None:
            return hit
    want = _tokens(v)
    best, best_s, tie = None, 0.0, False
    for i, o in opts:
        ot = _tokens(o)
        if not ot:
            continue
        s = len(want & ot) / max(len(want), len(ot))
        if s > best_s:
            best, best_s, tie = i, s, False
        elif s == best_s and s > 0:
            tie = True
    if key == "degree" and best_s < 0.75:
        return only(lambda o: re.search(r"bachelor", o, re.I) and not re.search(r"\bart", o, re.I)) \
            if re.search(r"science", v, re.I) else only(lambda o: re.search(r"bachelor", o, re.I))
    return best if best_s >= 0.75 and not tie else None


LINK_KEYS = {"linkedin", "github", "portfolio"}


def _extra_links(profile: dict) -> list[dict]:
    out = []
    for item in profile.get("extra_links") or []:
        if isinstance(item, dict) and str(item.get("url", "")).strip() and str(item.get("label", "")).strip():
            out.append(item)
    return out


def match_extra_link(f: dict, profile: dict) -> str | None:

    if f["tag"] == "select" or f["type"] in ("file", "checkbox", "radio", "email", "tel", "password"):
        return None
    text = " ".join(x for x in [f["label"], f["name"], f["id"], f["placeholder"]] if x)
    if len(f["label"] or "") > 120:
        return None
    for item in _extra_links(profile):
        words = [item["label"]] + list(item.get("keywords") or [])
        for w in words:
            w = str(w).strip()
            if w and re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text, re.I):
                return item["url"].strip()
    return None


def fallback_link(profile: dict) -> str:

    links = _extra_links(profile)
    return links[0]["url"].strip() if links else ""


def eeo_value(key: str, profile: dict) -> str:
    d = profile.get("demographics") or {}
    return {"eeo_race": d.get("race", ""), "eeo_hispanic": d.get("hispanic_latino", ""),
            "eeo_veteran": d.get("veteran", ""), "eeo_disability": d.get("disability", ""),
            "eeo_gender": d.get("gender", "")}.get(key, "")


def manual_reason(key: str, profile: dict) -> str:
    wa = profile.get("work_authorization") or {}
    if key == "work_auth":
        return (f"WORK AUTHORIZATION - answer yourself. Your saved preference is "
                f"'{wa.get('current_authorization_preference', '?')}'; make sure it's true for THIS question "
                f"(current authorization vs. CPT/OPT for this internship).")
    if key == "sponsorship":
        conf = "" if wa.get("sponsorship_confirmed") else " (not yet confirmed by you as truthful)"
        return (f"VISA SPONSORSHIP - answer yourself. Saved preference '{wa.get('future_sponsorship_preference', '?')}'"
                f"{conf}. Read whether it asks about now, the internship, or future employment.")
    return "Needs your answer"


def fill_frame(frame, profile: dict, settings: dict, files: dict, cover_text_getter=None) -> FillReport:

    rep = FillReport()
    if not allowed_test_url(frame.url, settings):
        rep.blocked = "Autofill is restricted to local fixtures or explicitly authorized test hosts."
        return rep
    try:
        fields = frame.evaluate(COLLECT_JS)
    except Exception as e:
        rep.notes.append(f"Couldn't read a frame ({e.__class__.__name__})")
        return rep
    if not fields:
        return rep
    if any(f["type"] == "password" for f in fields) and len([f for f in fields if f["type"] not in ("password", "checkbox")]) <= 2:
        rep.blocked = "This page asks you to sign in or create an account. Please do that yourself."
        return rep

    def loc(f):
        return frame.locator(f'[data-ia="{f["idx"]}"]')

    def label_of(f):
        return (f["label"] or f["placeholder"] or f["name"] or f["id"] or "(unlabeled field)")[:90]

    handled = set()

    for f in fields:
        k = classify_field(f)
        if f["type"] != "file" or not k:
            continue
        if k == "resume_file" and files.get("resume"):
            path = files["resume"]
        elif k == "cover_letter_file":
            path = files.get("cover_letter") or (cover_text_getter("file") if cover_text_getter else None)
            if not path:
                rep.manual.append((label_of(f), "Cover letter upload (none generated)"))
                handled.add(f["idx"])
                continue
        else:
            continue
        try:
            loc(f).set_input_files(path, timeout=10000)
            rep.uploaded.append((label_of(f), Path(path).name))
        except Exception as e:
            rep.manual.append((label_of(f), f"Upload failed ({e.__class__.__name__}) - attach {Path(path).name} yourself"))
        handled.add(f["idx"])
    if rep.uploaded:
        frame.wait_for_timeout(1500)


        try:
            fields = frame.evaluate(COLLECT_JS)
            handled = set()
        except Exception:
            rep.notes.append("Could not refresh fields after upload; review the page and fill again.")
            return rep


    groups: dict[str, list] = {}
    for f in fields:
        if f["type"] == "radio" and f["name"]:
            groups.setdefault(f["name"], []).append(f)
    for name, group in groups.items():
        q = (group[0]["question"] or name)[:90]
        key = classify_field({**group[0], "label": group[0]["question"], "type": "text"})
        if key in MANUAL_ONLY:
            rep.manual.append((q, manual_reason(key, profile)))
        elif key in EEO_KEYS and settings.get("fill_demographics", True) and eeo_value(key, profile):
            if any(g["value"] for g in group):
                continue
            i = choose_option([g["label"] for g in group], key, eeo_value(key, profile))
            if i is None:
                rep.manual.append((q, "Voluntary self-identification - no option clearly matched"))
                continue
            try:
                loc(group[i]).check(timeout=5000)
                rep.filled.append((q, group[i]["label"]))
            except Exception as e:
                rep.manual.append((q, f"Couldn't select ({e.__class__.__name__})"))


    work_groups = {}
    for f in fields:
        if f["idx"] in handled or f["type"] == "file":
            continue
        key = classify_field(f)
        lab = label_of(f)
        if f["type"] in ("radio", "checkbox"):
            continue
        if key in MANUAL_ONLY:
            rep.manual.append((lab, manual_reason(key, profile)))
            continue
        if key in EEO_KEYS:
            if not settings.get("fill_demographics", True):
                rep.manual.append((lab, "Voluntary self-identification (auto-fill is off)"))
                continue
            val = eeo_value(key, profile)
            if not val:
                rep.manual.append((lab, "Voluntary self-identification - left for you"))
                continue
        elif key and (key.startswith(("work_", "current_work_")) or key == "experience_summary"):
            group = f.get("workGroup") or "flat"
            if key.startswith("work_") and group not in work_groups:
                work_groups[group] = len(work_groups)
            index = work_groups.get(group, 0)
            val = experience_value(key, profile, index, f["type"])
        elif key == "cover_letter_text":
            if f["tag"] != "textarea":
                continue
            val = cover_text_getter("text") if cover_text_getter else ""
            if not val:
                rep.manual.append((lab, "Cover letter text (none generated)"))
                continue
        else:
            extra = match_extra_link(f, profile) if key in LINK_KEYS | {None} else None
            if extra:
                key, val = "extra_link", extra
            elif key:
                val = profile_value(key, profile)
                if not val and key == "portfolio":
                    val = fallback_link(profile)
            else:
                continue
        if not val:
            if f["required"]:
                rep.manual.append((lab, f"Required, but your profile has no value for '{key}'"))
            continue
        already_set = (f["value"].strip() and f["tag"] != "select") or \
            (f["tag"] == "select" and f["value"] and f["selectedText"] and not PLACEHOLDER_RE.match(f["selectedText"]))
        if already_set:
            rep.notes.append(f"Left '{lab}' as it was (already had a value)")
            continue
        try:
            if f["tag"] == "select":
                i = choose_option(f["options"], key, val)
                if i is None:
                    rep.manual.append((lab, f"No option clearly matches '{val}' - choose yourself"))
                    continue
                loc(f).select_option(index=i, timeout=5000)
                rep.filled.append((lab, f["options"][i]))
            elif f["role"] == "combobox" or f["ariaAuto"] in ("list", "both"):
                chosen = _fill_combobox(frame, loc(f), key, val)
                if chosen:
                    rep.filled.append((lab, chosen))
                else:
                    rep.manual.append((lab, f"Dropdown has no clear match for '{val}' - choose yourself"))
            else:
                loc(f).fill(val, timeout=5000)
                rep.filled.append((lab, val if key != "cover_letter_text" else "(cover letter text)"))
        except Exception as e:
            rep.manual.append((lab, f"Couldn't fill ({e.__class__.__name__})"))


    try:
        after = frame.evaluate(COLLECT_JS)
    except Exception:
        after = []
    already = {m[0] for m in rep.manual}
    groups_seen = set()
    for f in after:
        if not f["required"] or f["type"] == "file":
            continue
        if f["type"] in ("radio", "checkbox"):
            g = f["name"] or f["label"]
            if g in groups_seen:
                continue
            groups_seen.add(g)
            checked = frame.evaluate("n => [...document.getElementsByName(n)].some(e => e.checked)", f["name"]) if f["name"] else bool(f["value"])
            if not checked:
                lab = (f["question"] or label_of(f))[:90]
                if lab not in already:
                    rep.manual.append((lab, "Required choice - answer yourself"))
            continue
        if not f["value"].strip():
            lab = label_of(f)
            if lab not in already:
                rep.manual.append((lab, "Required question not recognized - answer yourself"))
    return rep


def _fill_combobox(frame, locator, key: str, value: str) -> str | None:

    search = value if key not in EEO_KEYS else ""
    try:
        locator.click(timeout=5000)
        if search:
            locator.fill(search[:30], timeout=5000)
        frame.wait_for_timeout(900)
        opts = frame.locator('[role="option"]:visible')
        texts = [t.strip() for t in opts.all_inner_texts()]
        i = choose_option(texts, key, value)
        if i is None and search and key == "school":

            short = " ".join(value.split()[-3:])
            locator.fill(short, timeout=5000)
            frame.wait_for_timeout(900)
            texts = [t.strip() for t in opts.all_inner_texts()]
            i = choose_option(texts, key, value)
        if i is None:
            locator.press("Escape")
            if search:
                locator.fill("")
            return None
        opts.nth(i).click(timeout=5000)
        return texts[i]
    except Exception:
        try:
            locator.press("Escape")
        except Exception:
            pass
        return None


def fill_page(page, profile: dict, settings: dict, files: dict, cover_text_getter=None) -> FillReport:
    rep = FillReport(provider=provider_for(page.url))
    from job_parser import job_site_name
    site = job_site_name(page.url)
    if site:
        rep.blocked = (f"This is a {site} page - I don't fill anything on {site}. Click its 'Apply' button: "
                       f"if it takes you to the company's site, choose [r] there and I'll fill that form. "
                       f"If it's {site}'s own quick-apply, please complete it yourself.")
        return rep
    if not allowed_test_url(page.url, settings):
        rep.blocked = "Remote autofill is disabled. Use mock forms or an explicitly authorized test host."
        return rep
    if rep.provider == "workday":
        rep.blocked = ("Workday isn't supported yet (it needs an account and multi-page flow). "
                       "Please complete this one by hand.")
        return rep
    for frame in page.frames:
        rep.merge(fill_frame(frame, profile, settings, files, cover_text_getter))
    if _has_captcha(page):
        rep.notes.append("This site uses a CAPTCHA. If one appears, solve it yourself.")
    if not rep.filled and not rep.uploaded and not rep.manual and not rep.blocked:
        rep.notes.append("No application form found on this page. If there's an 'Apply' button, click it, "
                         "then choose [r] to fill again.")
    return rep


def _has_captcha(page) -> bool:
    try:
        return any(re.search(r"recaptcha|hcaptcha|turnstile|captcha", f.url or "", re.I) for f in page.frames)
    except Exception:
        return False


def detect_success(page) -> bool:
    try:
        if re.search(r"confirm|thank|success", page.url, re.I):
            return True
        for frame in page.frames:
            if SUCCESS_RE.search(frame.evaluate("() => document.body ? document.body.innerText : ''")):
                return True
    except Exception:
        return False
    return False


def print_report(rep: FillReport) -> None:
    print()
    if rep.blocked:
        print(f"  ! {rep.blocked}")
    if rep.uploaded:
        print("  Uploaded:")
        for lab, fn in rep.uploaded:
            print(f"    + {lab}: {fn}")
    if rep.filled:
        print("  Filled:")
        for lab, val in rep.filled:
            print(f"    + {lab}: {val[:60]}")
    if rep.manual:
        print("  YOU need to answer:")
        for lab, why in rep.manual:
            print(f"    ? {lab} -> {why}")
    for n in rep.notes:
        print(f"  - {n}")


def run_application(job: dict, profile: dict, settings: dict, resume_path: str,
                    cover_text_getter=None, ask=input) -> dict:

    try:
        from playwright.sync_api import sync_playwright, Error as PWError
    except ImportError:
        return {"outcome": "failed", "note": "Playwright isn't installed (see README setup)."}
    url = application_url(job)
    if not url:
        return {"outcome": "failed", "note": "No application link saved for this job."}
    if not allowed_test_url(url, settings):
        return {"outcome": "failed", "note": "Remote applications are disabled; this host is not authorized for testing."}
    files = {"resume": resume_path, "cover_letter": None}
    with sync_playwright() as p:
        browser = None
        try:
            kw = {"headless": bool(settings.get("_headless"))}
            if settings.get("browser_channel"):
                kw["channel"] = settings["browser_channel"]
            try:
                browser = p.chromium.launch(**kw)
            except PWError as e:
                print(f"  Couldn't start Chromium ({str(e).splitlines()[0][:90]}) - trying Microsoft Edge instead.")
                print("  (Tip: run  python -m playwright install chromium  once to fix this.)")
                browser = p.chromium.launch(headless=kw["headless"], channel="msedge")
            context = browser.new_context(viewport=None)
            context.route("**/*", lambda route: route.continue_() if allowed_test_url(route.request.url, settings) else route.abort())
            page = context.new_page()
            print(f"  Opening {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2500)
            except PWError as e:
                print(f"  ! Page didn't load cleanly ({str(e).splitlines()[0][:100]}). You can still work in the browser.")
            rep = fill_page(page, profile, settings, files, cover_text_getter)
            print_report(rep)
            print("\n  >>> Review everything in the browser. Answer the '?' items, then click Submit YOURSELF.")
            print("      Nothing has been submitted.")
            while True:
                choice = ask("\n  [s] I submitted it   [r] fill the page I'm on now   [k] skip   [f] couldn't finish\n  > ").strip().lower()
                if choice == "r":
                    try:
                        page = browser.contexts[0].pages[-1]
                        rep = fill_page(page, profile, settings, files, cover_text_getter)
                        print_report(rep)
                    except PWError:
                        print("  ! The browser window seems closed.")
                elif choice == "s":
                    ok = False
                    try:
                        ok = any(detect_success(pg) for pg in browser.contexts[0].pages)
                    except PWError:
                        pass
                    if ok:
                        print("  Confirmation page detected.")
                        return {"outcome": "submitted", "note": "confirmation page detected"}
                    if ask("  I can't see a confirmation message. Are you sure it was submitted? (yes/no) ").strip().lower() in ("y", "yes"):
                        return {"outcome": "submitted", "note": "confirmed by you"}
                elif choice == "k":
                    return {"outcome": "skipped", "note": ""}
                elif choice == "f":
                    why = ask("  What stopped it? (optional) ").strip()
                    return {"outcome": "failed", "note": why or "couldn't finish"}
        except KeyboardInterrupt:
            return {"outcome": "failed", "note": "interrupted"}
        except PWError as e:
            print(f"  ! Browser problem: {str(e).splitlines()[0][:120]}")
            ans = ask("  Did you manage to submit before that happened? (yes/no) ").strip().lower()
            if ans in ("y", "yes"):
                return {"outcome": "submitted", "note": "confirmed by you after browser error"}
            return {"outcome": "failed", "note": "browser error"}
        finally:
            try:
                if browser:
                    browser.close()
            except Exception:
                pass
