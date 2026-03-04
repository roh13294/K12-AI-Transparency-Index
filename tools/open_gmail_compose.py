#!/usr/bin/env python3
import csv
import os
import sys
import time
import urllib.parse
import webbrowser

DEFAULT_TARGETS = os.path.join("outreach_out", "targets.csv")

def q(s: str) -> str:
    return urllib.parse.quote(s or "", safe="")

def gmail_compose_url(to: str, cc: str, subject: str, body: str) -> str:
    # Gmail compose endpoint (works without any API)
    base = "https://mail.google.com/mail/?view=cm&fs=1"
    params = []
    if to:
        params.append(("to", to))
    if cc:
        params.append(("cc", cc))
    if subject:
        params.append(("su", subject))
    if body:
        params.append(("body", body))
    return base + "&" + urllib.parse.urlencode(params)

def read_text(path: str) -> str:
    if not path or not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def main():
    targets_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGETS
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8  # seconds between opening tabs

    if not os.path.exists(targets_path):
        print(f"Missing: {targets_path}")
        sys.exit(1)

    opened = 0
    with open(targets_path, newline="", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            if opened >= limit:
                break

            to = (row.get("priority_email") or "").strip()
            cc = (row.get("cc_emails") or "").strip()
            district = (row.get("district") or "").strip()
            state = (row.get("state") or "").strip()
            score = (row.get("index_score") or "").strip()
            packet_dir = (row.get("packet_dir") or "").strip()

            # These are created by your outreach pipeline (adjust if your filenames differ)
            subject_path = os.path.join(packet_dir, "subject.txt")
            body_path = os.path.join(packet_dir, "email_body.txt")

            subject = read_text(subject_path).strip()
            body = read_text(body_path).strip()

            # Fallbacks if subject/body files are missing
            if not subject:
                subject = f"AI transparency request — {district} ({state})"
            if not body:
                body = (
                    f"Hello,\n\n"
                    f"I’m reaching out regarding AI transparency signals for {district} ({state}).\n"
                    f"Your current index score is {score}/100 based on publicly visible governance signals.\n\n"
                    f"My dashboard: https://roh13294.github.io/K12-AI-Transparency-Index/\n\n"
                    f"I can share a 1-page summary + a district implementation checklist.\n\n"
                    f"Thanks,\n"
                    f"Rohan Nagaram\n"
                )

            if not to:
                # Skip rows where you didn’t find an email
                continue

            url = gmail_compose_url(to=to, cc=cc, subject=subject, body=body)
            webbrowser.open_new_tab(url)
            opened += 1

            print(f"[{opened}] Opened Gmail draft tab for: {district} ({state}) to={to}")

            time.sleep(delay)

    print(f"Done. Opened {opened} Gmail compose tabs.")
    print("Next: attach the PDF from each packet_dir and hit Send.")

if __name__ == "__main__":
    main()