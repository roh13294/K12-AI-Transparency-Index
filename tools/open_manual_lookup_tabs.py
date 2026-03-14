#!/usr/bin/env python3
import csv
import os
import sys
import urllib.parse
import webbrowser

DEFAULT_TARGETS = os.path.join("outreach_out", "targets.csv")

CANDIDATE_PATHS = [
    "/staff",
    "/staff-directory",
    "/directory",
    "/contact",
    "/contact-us",
    "/administration",
    "/superintendent",
    "/board",
    "/board-of-education",
    "/school-board",
    "/boe",
]

def sanitize(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    u = u.replace("%7D", "").replace("%7B", "").replace("{","").replace("}","").strip()
    if not u.lower().startswith("http"):
        u = "https://" + u
    return u

def join(base: str, path: str) -> str:
    return urllib.parse.urljoin(base.rstrip("/") + "/", path.lstrip("/"))

def find_manual_rows(targets_path: str):
    rows = []
    with open(targets_path, newline="", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        for row in r:
            if (row.get("send_class") or "").strip().upper() == "MANUAL_LOOKUP":
                rows.append(row)
    return rows

def main():
    targets_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGETS
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 1  # 1-based
    mode = (sys.argv[3] if len(sys.argv) > 3 else "2tabs").lower()

    if not os.path.exists(targets_path):
        print(f"Missing: {targets_path}")
        sys.exit(1)

    manual = find_manual_rows(targets_path)
    if not manual:
        print("No MANUAL_LOOKUP rows found.")
        sys.exit(0)

    if idx < 1 or idx > len(manual):
        print(f"Index out of range. There are {len(manual)} MANUAL_LOOKUP rows.")
        print("Example: python3 tools/open_manual_lookup_tabs.py outreach_out/targets.csv 1")
        sys.exit(1)

    row = manual[idx - 1]
    district = (row.get("district") or "").strip()
    state = (row.get("state") or "").strip()
    homepage = sanitize(row.get("homepage") or "")
    found_contact = sanitize(row.get("found_contact_url") or "")

    print(f"MANUAL [{idx}/{len(manual)}]: {district} ({state})")
    print("Goal: find ONE email (superintendent or board clerk).")

    # Always open homepage
    if homepage:
        webbrowser.open_new_tab(homepage)

    # Second tab: best guess for directory/contact
    second = found_contact if found_contact else ""
    if not second and homepage:
        # pick ONE best candidate path (we don't spam tabs)
        # Try /contact first (usually works), otherwise /staff
        second = join(homepage, "/contact")

    if second and second != homepage:
        webbrowser.open_new_tab(second)

    # Optional: if you want 3 tabs, open board page as the third
    if mode == "3tabs" and homepage:
        third = join(homepage, "/board")
        if third not in {homepage, second}:
            webbrowser.open_new_tab(third)

    print("Opened 2 tabs (or 3 if you used 3tabs).")

if __name__ == "__main__":
    main()