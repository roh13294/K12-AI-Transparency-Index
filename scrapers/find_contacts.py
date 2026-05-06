#!/usr/bin/env python3
import argparse
import csv
import html
import re
import sys
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}
REQUEST_TIMEOUT = 15
CRAWL_DELAY_SEC = 2.0
MAX_PAGES_PER_DISTRICT = 8
MAX_DEPTH = 2
RETRY_DELAY_SEC = 3.0
DIRECT_FALLBACK_PATHS = ("/contact", "/about", "/staff", "/administration")

LIKELY_PAGE_KEYWORDS = (
    "contact",
    "about",
    "staff",
    "directory",
    "leadership",
    "administration",
    "superintendent",
    "cabinet",
    "board",
)
SUPERINTENDENT_HINTS = (
    "superintendent",
    "chief executive officer",
    "district leader",
    "schools superintendent",
)
CONTACT_HINTS = (
    "contact",
    "email",
    "district office",
    "main office",
    "communications",
    "info@",
    "webmaster",
)
BAD_EMAIL_PARTS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".css",
    ".js",
    ".pdf",
    ".ico",
    "example.com",
)
EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b")
OBFUSCATED_EMAIL_RE = re.compile(
    r"(?i)\b([a-z0-9._%+\-]+)\s*(?:@|\(at\)|\[at\]|\sat\s)\s*([a-z0-9.\-]+)\s*(?:\.|\(dot\)|\[dot\]|\sdot\s)\s*([a-z]{2,})\b"
)


class DelaySession:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds
        self.last_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get(self, url: str) -> requests.Response:
        elapsed = time.time() - self.last_request_at
        if self.last_request_at and elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            self.last_request_at = time.time()
            return response
        except requests.RequestException:
            self.last_request_at = time.time()
            time.sleep(RETRY_DELAY_SEC)
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            self.last_request_at = time.time()
            return response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find district contact emails for zero-score districts.")
    parser.add_argument(
        "--input",
        dest="input_path",
        default="",
        help="Optional explicit path to district_scores.csv. Defaults to out/district_scores.csv if present, then data/district_scores.csv.",
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        default="scrapers/contacts_output.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only process the first N zero-score districts.",
    )
    return parser.parse_args()


def choose_dataset(explicit_path: str) -> Path:
    candidates = [Path(explicit_path)] if explicit_path else []
    candidates.extend([Path("out/district_scores.csv"), Path("data/district_scores.csv")])
    for path in candidates:
        if path and path.exists():
            return path
    raise FileNotFoundError("Could not find district_scores.csv in out/ or data/.")


def load_zero_score_districts(dataset_path: Path, limit: int) -> List[Dict[str, str]]:
    with dataset_path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if (row.get("index_score") or "").strip() == "0"]
    if limit > 0:
        return rows[:limit]
    return rows


def same_domain(homepage: str, candidate: str) -> bool:
    try:
        home = urlparse(homepage)
        other = urlparse(candidate)
    except Exception:
        return False
    return home.netloc.lower() == other.netloc.lower()


def normalize_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href.strip())


def direct_fallback_urls(homepage: str) -> List[str]:
    return [normalize_url(homepage, path) for path in DIRECT_FALLBACK_PATHS]


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_email(email: str) -> str:
    email = clean_text(email).strip(".,;:()[]{}<>")
    return email.lower()


def extract_emails_from_text(text: str) -> Set[str]:
    matches = {normalize_email(match) for match in EMAIL_RE.findall(text)}
    for local, domain, suffix in OBFUSCATED_EMAIL_RE.findall(text):
        matches.add(normalize_email(f"{local}@{domain}.{suffix}"))
    return {email for email in matches if is_plausible_email(email)}


def is_plausible_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    lowered = email.lower()
    return not any(part in lowered for part in BAD_EMAIL_PARTS)


def extract_page_data(page_url: str, html_bytes: bytes) -> Tuple[str, List[Tuple[str, str]], Set[str]]:
    soup = BeautifulSoup(html_bytes, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    page_text = clean_text(soup.get_text(" ", strip=True))
    mailto_links: Set[str] = set()
    internal_links: List[Tuple[str, str]] = []

    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        anchor_text = clean_text(anchor.get_text(" ", strip=True))
        if not href:
            continue
        if href.lower().startswith("mailto:"):
            address = normalize_email(href.split(":", 1)[1].split("?", 1)[0])
            if is_plausible_email(address):
                mailto_links.add(address)
            continue
        if href.lower().startswith(("tel:", "javascript:")):
            continue
        absolute = normalize_url(page_url, href)
        internal_links.append((absolute, anchor_text))

    return page_text, internal_links, mailto_links


def likely_follow_link(url: str, anchor_text: str) -> bool:
    lowered = f"{url} {anchor_text}".lower()
    return any(keyword in lowered for keyword in LIKELY_PAGE_KEYWORDS)


def score_candidate_email(email: str, context: str, page_url: str, district_name: str, target: str) -> int:
    score = 0
    lowered_context = context.lower()
    lowered_url = page_url.lower()
    district_tokens = [token.lower() for token in re.findall(r"[a-zA-Z]+", district_name) if len(token) >= 4]

    if email.endswith((".gov", ".edu")):
        score += 4
    if any(token in email for token in ("superintendent", "supt")):
        score += 6
    if any(token in email for token in ("info@", "contact@", "communications@", "webmaster@", "publicinfo@")):
        score += 4
    if any(token in lowered_context for token in district_tokens[:4]):
        score += 2
    if any(token in lowered_url for token in ("contact", "about", "staff", "directory", "leadership", "administration", "superintendent")):
        score += 2

    if target == "superintendent":
        if any(hint in lowered_context for hint in SUPERINTENDENT_HINTS):
            score += 8
        if "superintendent" in lowered_url:
            score += 5
        if any(bad in lowered_context for bad in ("assistant superintendent", "deputy superintendent", "associate superintendent")):
            score -= 2
        if any(bad in email for bad in ("info@", "contact@", "webmaster@", "communications@")):
            score -= 4
    else:
        if any(hint in lowered_context for hint in CONTACT_HINTS):
            score += 5
        if "contact" in lowered_url:
            score += 4
        if "superintendent" in lowered_context:
            score -= 2

    return score


def find_best_email(page_text: str, page_url: str, district_name: str, target: str, mailto_emails: Set[str]) -> str:
    candidates = extract_emails_from_text(page_text) | set(mailto_emails)
    if not candidates:
        return ""

    best_email = ""
    best_score = -10**9
    lowered_text = page_text.lower()

    for email in sorted(candidates):
        idx = lowered_text.find(email.lower())
        if idx >= 0:
            start = max(0, idx - 220)
            end = min(len(page_text), idx + len(email) + 220)
            context = page_text[start:end]
        else:
            context = page_text[:500]
        score = score_candidate_email(email, context, page_url, district_name, target)
        if score > best_score:
            best_score = score
            best_email = email

    if target == "superintendent" and best_score < 3:
        return ""
    if target == "contact" and best_score < 1:
        return ""
    return best_email


def crawl_district(row: Dict[str, str], session: DelaySession) -> Dict[str, str]:
    district = (row.get("district") or "").strip()
    state = (row.get("state") or "").strip()
    homepage = (row.get("homepage") or "").strip()
    score = (row.get("index_score") or "").strip()

    result = {
        "district": district,
        "state": state,
        "score": score,
        "homepage": homepage,
        "superintendent_email": "",
        "contact_email": "",
        "source_page": "",
    }

    if not homepage:
        result["source_page"] = "error"
        return result

    queue: Deque[Tuple[str, int]] = deque([(homepage, 0)])
    visited: Set[str] = set()
    seen_links: Set[str] = {homepage}
    fallback_urls = direct_fallback_urls(homepage)
    fallback_enqueued = False

    while queue and len(visited) < MAX_PAGES_PER_DISTRICT:
        url, depth = queue.popleft()
        if depth > MAX_DEPTH:
            continue
        try:
            response = session.get(url)
            response.raise_for_status()
        except Exception:
            if not visited:
                result["source_page"] = "error"
            continue

        final_url = response.url
        if not same_domain(homepage, final_url):
            continue
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "text/html" not in content_type:
            continue
        if final_url in visited:
            continue
        visited.add(final_url)

        page_text, internal_links, mailto_emails = extract_page_data(final_url, response.content)
        if not result["superintendent_email"]:
            superintendent_email = find_best_email(page_text, final_url, district, "superintendent", mailto_emails)
            if superintendent_email:
                result["superintendent_email"] = superintendent_email
                result["source_page"] = final_url

        if not result["contact_email"]:
            contact_email = find_best_email(page_text, final_url, district, "contact", mailto_emails)
            if contact_email:
                result["contact_email"] = contact_email
                if not result["source_page"]:
                    result["source_page"] = final_url

        if result["superintendent_email"] and result["contact_email"]:
            break

        for link_url, anchor_text in internal_links:
            normalized = link_url.split("#", 1)[0]
            if normalized in seen_links:
                continue
            if not normalized.startswith(("http://", "https://")):
                continue
            if not same_domain(homepage, normalized):
                continue
            if likely_follow_link(normalized, anchor_text):
                seen_links.add(normalized)
                queue.append((normalized, depth + 1))

        if not queue and not result["superintendent_email"] and not result["contact_email"] and not fallback_enqueued:
            fallback_enqueued = True
            for fallback_url in fallback_urls:
                if fallback_url in seen_links:
                    continue
                if not same_domain(homepage, fallback_url):
                    continue
                seen_links.add(fallback_url)
                queue.append((fallback_url, 1))

    if not result["source_page"] and not visited:
        result["source_page"] = "error"
    return result


def write_results(output_path: Path, rows: Iterable[Dict[str, str]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "district",
        "state",
        "score",
        "homepage",
        "superintendent_email",
        "contact_email",
        "source_page",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    try:
        dataset_path = choose_dataset(args.input_path)
        zero_score_rows = load_zero_score_districts(dataset_path, args.limit)
    except Exception as exc:
        print(f"Failed to load dataset: {exc}", file=sys.stderr)
        return 1

    session = DelaySession(CRAWL_DELAY_SEC)
    output_rows: List[Dict[str, str]] = []

    for index, row in enumerate(zero_score_rows, start=1):
        district = (row.get("district") or "").strip()
        print(f"[{index}/{len(zero_score_rows)}] {district}", file=sys.stderr)
        output_rows.append(crawl_district(row, session))

    write_results(Path(args.output_path), output_rows)
    print(f"Wrote {len(output_rows)} rows to {args.output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
