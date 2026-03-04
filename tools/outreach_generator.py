#!/usr/bin/env python3
import os
import re
import csv
import time
import urllib.parse
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

USER_NAME = "Rohan Nagaram"
DASHBOARD_URL = "https://roh13294.github.io/K12-AI-Transparency-Index/"

DISTRICT_SCORES_CSV = "out/district_scores.csv"
AUDIT_FLAT_CSV = "out_flat/audit_results_ALL_flat.csv"
OUTPUT_DIR = "outreach_out"

N_TARGETS = 25

TIMEOUT = 14
SLEEP_BETWEEN_REQUESTS = 0.6
MAX_PAGES_PER_DISTRICT = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; K12-AI-Transparency-Index/2.0)"
}

EMAIL_REGEX = re.compile(r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})")

# Hard preference buckets (higher wins). We want decision-makers first.
BUCKETS = [
    ("SUPERINTENDENT", [r"superintendent", r"\bsupt\b"]),
    ("BOARD", [r"\bboard\b", r"trustee", r"president", r"vicechair", r"vice-chair", r"clerk", r"secretary"]),
    ("EXEC_OFFICE", [r"cabinet", r"chief", r"executive", r"ea\b", r"assistant", r"superintendent\.office"]),
    ("COMMS", [r"communications", r"pr\b", r"publicinfo", r"info\.officer"]),
    ("GENERIC", [r"\bcontact\b", r"\binfo\b", r"office"]),
]

# Emails we avoid unless nothing else exists
AVOID = [
    r"webmaster",
    r"noreply",
    r"no-reply",
    r"helpdesk",
    r"support",
    r"\bit\b",
    r"\btech\b",
    r"enrollment",
    r"substitute",
    r"jobs",
    r"hr\b",
]

@dataclass
class DistrictRow:
    district: str
    state: str
    homepage: str
    index_score: int
    tier: str

@dataclass
class AuditRow:
    district: str
    state: str
    homepage: str
    found_policy_url: str
    found_tech_url: str
    found_contact_url: str
    notes: str
    score_0_to_5: str

def norm(s: str) -> str:
    return (s or "").strip()

def safe_slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.strip())
    return s.strip("_")[:80] or "district"

def read_csv_rows(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))

def sanitize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    u = u.replace("%7D", "").replace("%7B", "")
    u = u.replace("{", "").replace("}", "")
    u = u.strip()
    if not re.match(r"^https?://", u, re.IGNORECASE):
        u = "https://" + u
    return u

def fetch(url: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return None, None
        ct = (r.headers.get("content-type") or "").lower()
        if "text/html" not in ct and "application/xhtml" not in ct and "text/plain" not in ct:
            return None, None
        return r.url, r.text
    except Exception:
        return None, None

def extract_emails_from_text(text: str) -> List[str]:
    if not text:
        return []
    hits = EMAIL_REGEX.findall(text)
    out, seen = [], set()
    for e in hits:
        e = e.strip().lower()
        if e and e not in seen:
            seen.add(e)
            out.append(e)
    return out

def extract_emails_from_html(html: str) -> List[str]:
    emails = []
    emails.extend(extract_emails_from_text(html))
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if href.lower().startswith("mailto:"):
                mail = href.split(":", 1)[1].split("?")[0].strip().lower()
                if mail:
                    emails.append(mail)
    except Exception:
        pass

    out, seen = [], set()
    for e in emails:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out

def soup_links(base_url: str, html: str) -> List[str]:
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return []
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue
        if href.lower().startswith("javascript:") or href.lower().startswith("mailto:"):
            continue
        links.append(urllib.parse.urljoin(base_url, href))
    out, seen = [], set()
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def pick_candidate_pages(homepage: str, found_contact_url: str) -> List[str]:
    candidates = []
    if found_contact_url:
        candidates.append(found_contact_url)
    if homepage:
        candidates.append(homepage)
        root = homepage.rstrip("/")
        for suffix in [
            "/contact", "/contact-us", "/staff", "/staff-directory", "/directory",
            "/district-office", "/administration", "/board", "/school-board", "/about"
        ]:
            candidates.append(root + suffix)

    out, seen = [], set()
    for u in candidates:
        u = sanitize_url(u)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out

def scrape_emails_for_district(homepage: str, found_contact_url: str) -> List[str]:
    homepage = sanitize_url(homepage)
    found_contact_url = sanitize_url(found_contact_url)

    emails = []
    visited = set()
    queue = pick_candidate_pages(homepage, found_contact_url)

    while queue and len(visited) < MAX_PAGES_PER_DISTRICT:
        url = queue.pop(0)
        if not url or url in visited:
            continue
        visited.add(url)

        final_url, html = fetch(url)
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        if not html:
            continue

        emails.extend(extract_emails_from_html(html))

        if len(set(emails)) < 4:
            for link in soup_links(final_url or url, html):
                low = link.lower()
                if any(k in low for k in ["staff", "directory", "contact", "board", "administration", "district", "office"]):
                    if link not in visited and link not in queue:
                        queue.append(link)

    out, seen = [], set()
    for e in emails:
        e = e.strip().lower()
        if e and e not in seen:
            seen.add(e)
            out.append(e)
    return out[:25]

def bucket_score(email: str) -> Tuple[int, int]:
    """
    Returns (bucket_rank, penalty) where higher bucket_rank is better,
    penalty is subtracted.
    """
    e = email.lower()

    # penalty for avoid terms
    penalty = 0
    for pat in AVOID:
        if re.search(pat, e):
            penalty += 50  # strong penalty

    # bucket rank
    for i, (bucket, pats) in enumerate(BUCKETS):
        for pat in pats:
            if re.search(pat, e):
                # higher bucket is better -> invert index
                return (100 - i * 10, penalty)

    # no match, generic rank
    return (10, penalty)

def pick_priority_and_cc(emails: List[str]) -> Tuple[str, str, str]:
    if not emails:
        return "", "", "MANUAL_LOOKUP"

    ranked = sorted(emails, key=lambda e: (bucket_score(e)[0] - bucket_score(e)[1]), reverse=True)

    priority = ranked[0]
    pr = priority.lower()

    if re.search(r"superintendent|\bsupt\b", pr):
        send_class = "SUPERINTENDENT"
    elif re.search(r"\bboard\b|clerk|secretary|trustee|president|vice", pr):
        send_class = "BOARD"
    elif re.search(r"assistant|executive|chief|cabinet", pr):
        send_class = "EXEC_OFFICE"
    else:
        send_class = "GENERIC"

    # CC: next best 2–4, but avoid stacking low-value or duplicates
    cc_list = []
    for e in ranked[1:]:
        if len(cc_list) >= 4:
            break
        if e == priority:
            continue
        # skip clearly bad CCs
        if re.search(r"noreply|no-reply", e):
            continue
        cc_list.append(e)

    return priority, ";".join(cc_list), send_class

def make_email_text(d: DistrictRow, a: Optional[AuditRow]) -> Tuple[str, str]:
    subject = f"Student AI Transparency Review — {d.district} ({d.state})"
    lines = []
    lines.append("Dear District Leadership,")
    lines.append("")
    lines.append(f"My name is {USER_NAME}. I run the National K–12 AI Transparency Index, a public, student-led review of publicly available AI governance disclosures across 1,913 school districts nationwide.")
    lines.append("")
    lines.append(f"I reviewed {d.district}’s publicly accessible materials and recorded an index score of {d.index_score}/100 ({d.tier}). If I missed an existing AI policy or disclosure page, I would appreciate the correct link so I can update the record for accuracy.")
    lines.append("")
    lines.append("If these disclosures are not currently published, I can share a free, lightweight 30-day transparency implementation template designed to reduce administrative burden and improve trust with families.")
    lines.append("")
    lines.append(f"Dashboard: {DASHBOARD_URL}")
    lines.append(f"District homepage reviewed: {d.homepage}")
    if a:
        if a.found_contact_url:
            lines.append(f"Contact/Directory URL found: {a.found_contact_url}")
        if a.notes:
            lines.append(f"Notes: {a.notes}")
    lines.append("")
    lines.append("Thank you for your time and service to students and families.")
    lines.append("")
    lines.append("Respectfully,")
    lines.append(USER_NAME)
    lines.append(DASHBOARD_URL)
    return subject, "\n".join(lines)

def draw_one_page_pdf(out_path: str, d: DistrictRow, a: Optional[AuditRow], emails: List[str]) -> None:
    c = canvas.Canvas(out_path, pagesize=letter)
    width, height = letter
    x = 54
    y = height - 54

    def line(txt: str, size: int = 11, dy: int = 15, bold: bool = False):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, y, txt[:120])
        y -= dy

    line("National K–12 AI Transparency Index — District Summary", 14, 22, True)
    line(f"District: {d.district} ({d.state})", 12, 18, True)
    line(f"Index Score: {d.index_score}/100  |  Tier: {d.tier}", 11, 16, False)
    line(f"Dashboard: {DASHBOARD_URL}", 10, 14, False)
    line(" ", 10, 10, False)

    line("Homepage reviewed:", 11, 16, True)
    line(d.homepage, 9, 12, False)

    if a and a.found_contact_url:
        line("Contact/Directory link:", 11, 16, True)
        line(a.found_contact_url, 9, 12, False)

    line(" ", 9, 10, False)
    line("Emails found (public pages):", 11, 16, True)
    if emails:
        for e in emails[:10]:
            line(e, 10, 13, False)
    else:
        line("None found automatically.", 10, 13, False)

    c.showPage()
    c.save()

def load_audit_map(audit_flat_csv: str) -> Dict[Tuple[str, str], AuditRow]:
    rows = read_csv_rows(audit_flat_csv)
    out = {}
    for r in rows:
        district = norm(r.get("district"))
        state = norm(r.get("state")).upper()
        out[(district.lower(), state)] = AuditRow(
            district=district,
            state=state,
            homepage=sanitize_url(norm(r.get("homepage"))),
            found_policy_url=sanitize_url(norm(r.get("found_policy_url"))),
            found_tech_url=sanitize_url(norm(r.get("found_tech_url"))),
            found_contact_url=sanitize_url(norm(r.get("found_contact_url"))),
            notes=norm(r.get("notes")),
            score_0_to_5=norm(r.get("score_0_to_5")),
        )
    return out

def load_bottom_targets(scores_csv: str, n: int) -> List[DistrictRow]:
    rows = read_csv_rows(scores_csv)
    parsed = []
    for r in rows:
        district = norm(r.get("district"))
        state = norm(r.get("state")).upper()
        if not district or not state:
            continue
        try:
            score = int(float(r.get("index_score", "0") or "0"))
        except Exception:
            score = 0
        parsed.append(DistrictRow(
            district=district,
            state=state,
            homepage=sanitize_url(norm(r.get("homepage"))),
            index_score=score,
            tier=norm(r.get("tier")),
        ))
    parsed.sort(key=lambda x: (x.index_score, x.state, x.district))
    return parsed[:n]

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def write_manual_steps(packet_dir: str, d: DistrictRow):
    path = os.path.join(packet_dir, "manual_steps.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("MANUAL LOOKUP NEEDED\n\n")
        f.write(f"District: {d.district} ({d.state})\n")
        f.write(f"Homepage: {d.homepage}\n\n")
        f.write("Steps:\n")
        f.write("1) Open homepage.\n")
        f.write("2) Search for: 'Board', 'School Board', 'Staff Directory', 'District Office'.\n")
        f.write("3) Copy superintendent/board clerk email into targets.csv (priority_email) and rerun drafts.\n")

def main():
    if not os.path.exists(DISTRICT_SCORES_CSV):
        raise SystemExit(f"Missing: {DISTRICT_SCORES_CSV}")
    if not os.path.exists(AUDIT_FLAT_CSV):
        raise SystemExit(f"Missing: {AUDIT_FLAT_CSV}")

    ensure_dir(OUTPUT_DIR)
    audit_map = load_audit_map(AUDIT_FLAT_CSV)
    targets = load_bottom_targets(DISTRICT_SCORES_CSV, N_TARGETS)

    targets_csv_path = os.path.join(OUTPUT_DIR, "targets.csv")
    with open(targets_csv_path, "w", newline="", encoding="utf-8") as fcsv:
        w = csv.writer(fcsv)
        w.writerow([
            "district","state","index_score","tier","homepage",
            "found_policy_url","found_tech_url","found_contact_url",
            "emails_found","priority_email","cc_emails","send_class","packet_dir"
        ])

        for i, d in enumerate(targets, 1):
            a = audit_map.get((d.district.lower(), d.state))
            found_contact = a.found_contact_url if a else ""
            emails = scrape_emails_for_district(d.homepage, found_contact)

            priority_email, cc_emails, send_class = pick_priority_and_cc(emails)

            packet_dir = os.path.join(OUTPUT_DIR, f"{d.state}_{safe_slug(d.district)}")
            ensure_dir(packet_dir)

            subject, body = make_email_text(d, a)
            with open(os.path.join(packet_dir, "email_subject.txt"), "w", encoding="utf-8") as fsub:
                fsub.write(subject + "\n")
            with open(os.path.join(packet_dir, "email.txt"), "w", encoding="utf-8") as fmail:
                fmail.write(body + "\n")

            draw_one_page_pdf(os.path.join(packet_dir, "summary.pdf"), d, a, emails)

            if send_class == "MANUAL_LOOKUP":
                write_manual_steps(packet_dir, d)

            w.writerow([
                d.district, d.state, d.index_score, d.tier, d.homepage,
                (a.found_policy_url if a else ""),
                (a.found_tech_url if a else ""),
                (a.found_contact_url if a else ""),
                ";".join(emails),
                priority_email,
                cc_emails,
                send_class,
                packet_dir
            ])

            print(f"[{i}/{len(targets)}] Packet: {d.district} ({d.state}) score={d.index_score} send_class={send_class} emails={len(emails)}")

    print("\nDone.")
    print(f"Wrote: {targets_csv_path}")
    print(f"Packets: {os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    main()