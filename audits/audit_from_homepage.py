#!/usr/bin/env python3
"""
audit_from_homepage.py (tightened scoring, Michigan-first, scalable)

Input CSV:
  district,state,homepage

Run:
  python3 -m pip install --upgrade pip
  python3 -m pip install requests beautifulsoup4 pdfplumber
  python3 audit_from_homepage.py districts_homepages.csv

Output:
  audit_results.csv (written incrementally)

What’s tightened:
- “AI use publicly disclosed” now requires explicit AI tool disclosure language
  (ChatGPT/Copilot/Gemini/etc or “approved AI tools”), not generic “transparency”.
- “Public AI policy exists” is anchored to policy-type language, not random AI mentions.
- Faster + safer: per-district time budget, small crawl budget, skips stuck sites.
"""

import csv
import re
import sys
import time
import urllib.parse
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

# Optional PDF extraction
try:
    import pdfplumber  # type: ignore
    PDF_SUPPORT = True
except Exception:
    PDF_SUPPORT = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; K12-AI-Transparency-Audit/1.2; contact: rohan)"
}

# Speed / safety
TIMEOUT = 10
SLEEP = 0.12
MAX_PAGES_PER_DISTRICT = 14
MAX_DEPTH = 2
MAX_TEXT_CHARS = 280_000
PER_DISTRICT_BUDGET_SEC = 35


@dataclass
class FoundPages:
    policy_url: str = ""
    tech_url: str = ""
    contact_url: str = ""
    board_policy_url: str = ""
    notes: str = ""


def _now() -> float:
    return time.time()


def same_domain(url_a: str, url_b: str) -> bool:
    try:
        a = urllib.parse.urlparse(url_a)
        b = urllib.parse.urlparse(url_b)
        return a.netloc.lower() == b.netloc.lower()
    except Exception:
        return False


def normalize_url(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, href.strip())


def looks_like_pdf(url: str, content_type: str) -> bool:
    return "application/pdf" in content_type or url.lower().endswith(".pdf")


def fetch(url: str) -> Tuple[str, bytes, str]:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    ct = (r.headers.get("Content-Type") or "").lower()
    return ct, r.content, r.url


def extract_text_from_html(html_bytes: bytes) -> str:
    soup = BeautifulSoup(html_bytes, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def extract_links(base_url: str, html_bytes: bytes) -> List[str]:
    soup = BeautifulSoup(html_bytes, "html.parser")
    links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:") or href.startswith("tel:"):
            continue
        url = normalize_url(base_url, href)
        if url.startswith("http://") or url.startswith("https://"):
            links.append(url)

    seen: Set[str] = set()
    out: List[str] = []
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def pdf_to_text(pdf_bytes: bytes) -> str:
    if not PDF_SUPPORT:
        return ""
    path = "/tmp/_audit_one.pdf"
    with open(path, "wb") as f:
        f.write(pdf_bytes)

    parts: List[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:15]:
            t = page.extract_text() or ""
            if t:
                parts.append(t)
    return "\n".join(parts)


def keyword_score_url(url: str) -> int:
    u = url.lower()
    score = 0

    # Strong targets
    if any(k in u for k in ["boardpolicy", "board-policy", "policies", "policy-manual", "policy", "boe", "board-of-education"]):
        score += 5
    if any(k in u for k in ["technology", "edtech", "instructional-technology", "information-technology", "/it", "tech-services"]):
        score += 3
    if any(k in u for k in ["contact", "directory", "staff-directory", "staff", "administration"]):
        score += 3

    # Avoid noise
    if any(k in u for k in ["calendar", "event", "news", "blog", "gallery", "photo", "athletics", "sports"]):
        score -= 3
    if any(k in u for k in ["facebook.com", "twitter.com", "instagram.com", "youtube.com", "tiktok.com"]):
        score -= 10

    return score


def choose_best_url(candidates: List[str], kind: str) -> str:
    if not candidates:
        return ""

    def kind_boost(u: str) -> int:
        ul = u.lower()
        if kind == "policy":
            return 7 if any(k in ul for k in ["boardpolicy", "board-policy", "policies", "policy-manual", "policy", "boe"]) else 0
        if kind == "tech":
            return 6 if any(k in ul for k in ["technology", "edtech", "instructional-technology", "information-technology", "/it"]) else 0
        if kind == "contact":
            return 6 if any(k in ul for k in ["contact", "directory", "staff-directory", "staff"]) else 0
        return 0

    scored = [(keyword_score_url(u) + kind_boost(u), u) for u in candidates]
    scored.sort(reverse=True, key=lambda x: x[0])
    return scored[0][1]


def find_snippet(text: str, patterns: List[str], window: int = 140) -> Optional[str]:
    lowered = text.lower()
    for p in patterns:
        m = re.search(p, lowered)
        if m:
            start = max(m.start() - window, 0)
            end = min(m.end() + window, len(lowered))
            return text[start:end].strip()
    return None


def crawl_and_find(homepage: str) -> Tuple[FoundPages, Dict[str, str]]:
    start_t = _now()
    found = FoundPages()
    visited: Set[str] = set()
    text_by_url: Dict[str, str] = {}

    q = deque()
    q.append((homepage, 0))
    visited.add(homepage)

    candidate_policy: List[str] = []
    candidate_tech: List[str] = []
    candidate_contact: List[str] = []
    candidate_boardpolicy: List[str] = []

    combined_len = 0

    while q and len(visited) <= MAX_PAGES_PER_DISTRICT:
        if _now() - start_t > PER_DISTRICT_BUDGET_SEC:
            found.notes = "Timed out (district budget exceeded)"
            break

        url, depth = q.popleft()
        if depth > MAX_DEPTH:
            continue

        try:
            ct, content, final_url = fetch(url)
            time.sleep(SLEEP)
        except Exception:
            continue

        if not same_domain(homepage, final_url):
            continue

        # Extract text
        page_text = ""
        if looks_like_pdf(final_url, ct):
            page_text = pdf_to_text(content)
        else:
            page_text = extract_text_from_html(content)

        if page_text and combined_len < MAX_TEXT_CHARS:
            remaining = MAX_TEXT_CHARS - combined_len
            text_by_url[final_url] = page_text[:remaining]
            combined_len += min(len(page_text), remaining)

        ul = final_url.lower()

        # Candidate URLs
        if any(k in ul for k in ["boardpolicy", "board-policy", "policies", "policy-manual", "policy", "boe", "board-of-education"]):
            candidate_policy.append(final_url)
        if any(k in ul for k in ["boardpolicy", "board-policy", "boe", "board-of-education", "board"]):
            candidate_boardpolicy.append(final_url)
        if any(k in ul for k in ["technology", "edtech", "instructional-technology", "information-technology", "/it", "tech-services"]):
            candidate_tech.append(final_url)
        if any(k in ul for k in ["contact", "directory", "staff-directory", "staff", "administration"]):
            candidate_contact.append(final_url)

        # Expand crawl (HTML only)
        if looks_like_pdf(final_url, ct):
            continue

        try:
            links = extract_links(final_url, content)
        except Exception:
            links = []

        links_sorted = sorted(links, key=keyword_score_url, reverse=True)

        for link in links_sorted:
            if _now() - start_t > PER_DISTRICT_BUDGET_SEC:
                found.notes = "Timed out (district budget exceeded)"
                break
            if len(visited) >= MAX_PAGES_PER_DISTRICT:
                break
            if link in visited:
                continue
            if not same_domain(homepage, link):
                continue
            visited.add(link)
            q.append((link, depth + 1))

        # Early stop if we found policy + contact candidates (tech often buried)
        if candidate_policy and candidate_contact and len(visited) >= 9:
            break

    found.policy_url = choose_best_url(candidate_policy, "policy")
    found.board_policy_url = choose_best_url(candidate_boardpolicy, "policy")
    found.tech_url = choose_best_url(candidate_tech, "tech")
    found.contact_url = choose_best_url(candidate_contact, "contact")

    if not found.policy_url and found.board_policy_url:
        found.policy_url = found.board_policy_url

    missing = []
    if not found.policy_url:
        missing.append("policy")
    if not found.tech_url:
        missing.append("tech")
    if not found.contact_url:
        missing.append("contact")
    if missing and not found.notes:
        found.notes = f"Missing: {', '.join(missing)} (crawl limited)"

    return found, text_by_url


def score_from_texts(text_by_url: Dict[str, str]) -> Tuple[int, Dict[str, Tuple[int, str]]]:
    combined = " ".join([t for t in text_by_url.values() if t])[:MAX_TEXT_CHARS]
    lower = combined.lower()

    # Tightened patterns

    # 1) Public AI policy exists: requires AI terms + policy/acceptable use/guidelines context
    ai_terms = r"(generative ai|artificial intelligence|\bai\b|chatgpt|copilot|gemini|claude)"
    policy_context = r"(policy|policies|guidelines|acceptable use|a\.u\.p\.|a u p|board policy|policy manual|regulation|procedure)"
    public_ai_policy_patterns = [
        rf"{policy_context}.{{0,80}}{ai_terms}",
        rf"{ai_terms}.{{0,80}}{policy_context}",
    ]

    # 2) AI use publicly disclosed: must name tools or “approved ai tools” style language
    explicit_tools = r"(chatgpt|microsoft copilot|copilot|google gemini|gemini|claude|openai|anthropic|dall[- ]?e|midjourney|perplexity)"
    disclosure_context = r"(approved|district uses|we use|in our classrooms|staff may use|students may use|allowed|permitted|supported tools|district[- ]approved)"
    ai_disclosure_patterns = [
        rf"{disclosure_context}.{{0,120}}(ai tools|{explicit_tools})",
        rf"(ai tools|{explicit_tools}).{{0,120}}{disclosure_context}",
        r"\bapproved ai tools\b",
        r"\bdistrict[- ]approved ai\b",
    ]

    # 3) Oversight named: looks for a responsible role + technology/ai wording
    oversight_patterns = [
        r"(director|chief|coordinator|superintendent|assistant superintendent).{0,60}(technology|information technology|it|digital learning|instructional technology)",
        r"(technology|information technology|it|digital learning|instructional technology).{0,60}(director|chief|coordinator)",
        r"(responsible|oversight|point of contact|designated).{0,80}(ai|artificial intelligence|generative ai)",
    ]

    # 4) Board policy mentions AI: requires board/policy language + AI terms
    board_policy_patterns = [
        rf"(board policy|policy manual|board policies|policy).{{0,120}}{ai_terms}",
        rf"{ai_terms}.{{0,120}}(board policy|policy manual|board policies|policy)",
    ]

    # 5) Public contact available: contact/directory markers
    contact_patterns = [
        r"\bstaff directory\b",
        r"\bcontact\b",
        r"\bdirectory\b",
        r"\bphone\b",
        r"\bemail\b",
    ]

    criteria = {
        "public_ai_policy_exists": public_ai_policy_patterns,
        "ai_use_publicly_disclosed": ai_disclosure_patterns,
        "oversight_named": oversight_patterns,
        "board_policy_mentions_ai": board_policy_patterns,
        "public_contact_available": contact_patterns,
    }

    detail: Dict[str, Tuple[int, str]] = {}
    score = 0

    for name, pats in criteria.items():
        snip = find_snippet(combined, pats)
        hit = 1 if snip else 0
        score += hit
        detail[name] = (hit, (snip[:280] + "…") if snip else "")

    # Extra tightening: if AI disclosure hit but no AI terms exist at all, drop it
    if detail["ai_use_publicly_disclosed"][0] == 1 and not re.search(ai_terms, lower):
        detail["ai_use_publicly_disclosed"] = (0, "")
        score -= 1

    return score, detail


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 audit_from_homepage.py districts_homepages.csv")
        sys.exit(1)

    in_path = sys.argv[1]
    out_path = "audit_results.csv"

    with open(in_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("No rows found in input CSV. Check formatting.")
        sys.exit(1)

    out_fields = [
        "district", "state", "homepage",
        "found_policy_url", "found_tech_url", "found_contact_url", "notes",
        "score_0_to_5",
        "public_ai_policy_exists",
        "ai_use_publicly_disclosed",
        "oversight_named",
        "board_policy_mentions_ai",
        "public_contact_available",
        "evidence_public_ai_policy_exists",
        "evidence_ai_use_publicly_disclosed",
        "evidence_oversight_named",
        "evidence_board_policy_mentions_ai",
        "evidence_public_contact_available",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=out_fields)
        w.writeheader()

        for i, r in enumerate(rows, start=1):
            district = (r.get("district") or "").strip()
            state = (r.get("state") or "").strip()
            homepage = (r.get("homepage") or "").strip()

            if not homepage:
                continue

            try:
                found, text_by_url = crawl_and_find(homepage)
                score, detail = score_from_texts(text_by_url)
            except Exception:
                found = FoundPages(notes="Error")
                score = 0
                detail = {
                    "public_ai_policy_exists": (0, ""),
                    "ai_use_publicly_disclosed": (0, ""),
                    "oversight_named": (0, ""),
                    "board_policy_mentions_ai": (0, ""),
                    "public_contact_available": (0, ""),
                }

            row_out = {
                "district": district,
                "state": state,
                "homepage": homepage,
                "found_policy_url": found.policy_url,
                "found_tech_url": found.tech_url,
                "found_contact_url": found.contact_url,
                "notes": found.notes,
                "score_0_to_5": score,
            }

            for crit in [
                "public_ai_policy_exists",
                "ai_use_publicly_disclosed",
                "oversight_named",
                "board_policy_mentions_ai",
                "public_contact_available",
            ]:
                hit, snip = detail.get(crit, (0, ""))
                row_out[crit] = str(hit)
                row_out[f"evidence_{crit}"] = snip

            w.writerow(row_out)
            f_out.flush()

            print(f"[{i}/{len(rows)}] Audited: {district or homepage} score={score} notes={found.notes}")

    print(f"Done. Wrote {out_path}")
    print("PDF support enabled." if PDF_SUPPORT else "Note: PDF support disabled. Install pdfplumber for better results on policy PDFs.")


if __name__ == "__main__":
    main()