#!/usr/bin/env python3
import csv
import os
import subprocess

PROJECT_ROOT = os.path.expanduser("~/Desktop/AI_Transparency_Audit")
TARGETS_CSV = os.path.join(PROJECT_ROOT, "outreach_out", "targets.csv")

MAX_DRAFTS = 25

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().strip()

def applescript_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace('"', '\\"')

def make_draft(to_addr: str, cc_addrs: str, subject: str, body: str, attachment_path: str) -> None:
    as_to = applescript_escape(to_addr)
    as_cc = applescript_escape(cc_addrs)
    as_subject = applescript_escape(subject)
    as_body = applescript_escape(body)
    attachment_posix = applescript_escape(attachment_path)

    # CC list is semicolon-separated in our CSV
    cc_items = [x.strip() for x in (cc_addrs or "").split(";") if x.strip()]

    cc_block = ""
    if cc_items:
        # build AppleScript lines to add cc recipients
        cc_lines = []
        for addr in cc_items:
            addr_esc = applescript_escape(addr)
            cc_lines.append(f'make new cc recipient at end of cc recipients with properties {{address:"{addr_esc}"}}')
        cc_block = "\n        " + "\n        ".join(cc_lines)

    script = f'''
tell application "Mail"
    activate
    set newMessage to make new outgoing message with properties {{subject:"{as_subject}", content:"{as_body}" & return & return, visible:true}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:"{as_to}"}}{cc_block}
        try
            make new attachment with properties {{file name:(POSIX file "{attachment_posix}")}} at after the last paragraph
        end try
    end tell
end tell
'''
    subprocess.run(["osascript", "-e", script], check=True)

def main():
    if not os.path.exists(TARGETS_CSV):
        raise SystemExit(f"Missing: {TARGETS_CSV}. Run the outreach generator first.")

    created = 0

    with open(TARGETS_CSV, newline="", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            if created >= MAX_DRAFTS:
                break

            district = (row.get("district") or "").strip()
            state = (row.get("state") or "").strip()
            to_addr = (row.get("priority_email") or "").strip()
            cc_addrs = (row.get("cc_emails") or "").strip()
            packet_dir = (row.get("packet_dir") or "").strip()

            if not packet_dir:
                continue

            subj_path = os.path.join(packet_dir, "email_subject.txt")
            body_path = os.path.join(packet_dir, "email.txt")
            pdf_path  = os.path.join(packet_dir, "summary.pdf")

            if not (os.path.exists(subj_path) and os.path.exists(body_path) and os.path.exists(pdf_path)):
                print(f"SKIP (missing files): {district} ({state}) -> {packet_dir}")
                continue

            if not to_addr:
                print(f"SKIP (no priority_email): {district} ({state})")
                continue

            subject = read_text(subj_path)
            body = read_text(body_path)

            try:
                make_draft(to_addr, cc_addrs, subject, body, pdf_path)
                created += 1
                print(f"DRAFT [{created}]: {district} ({state}) -> TO:{to_addr} CC:{len([x for x in cc_addrs.split(';') if x.strip()])}")
            except subprocess.CalledProcessError as e:
                print(f"ERROR creating draft for {district} ({state}): {e}")

    print(f"\nDone. Drafts created: {created}")
    print("Open Mail -> Drafts to review/send.")

if __name__ == "__main__":
    main()