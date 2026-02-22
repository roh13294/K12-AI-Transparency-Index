#!/usr/bin/env python3
import csv
import os
import random
import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS


OUTPUT_DIR = "inputs_44_states"
DISTRICTS_PER_STATE = 40

EXCLUDE = {"MI", "CA", "TX", "FL", "NY", "IL"}

HEADERS = {"User-Agent": "K12-AI-Index/2.1"}
TIMEOUT = 25

SLEEP_API = 0.35
SLEEP_SEARCH = 0.75
SEARCH_RESULTS_PER_QUERY = 12

# Your Wikipedia pages
WIKI_URLS: Dict[str, str] = {
    "AL": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Alabama",
    "AK": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Alaska",
    "AZ": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Arizona",
    "AR": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Arkansas",
    "CO": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Colorado",
    "CT": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Connecticut",
    "DE": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Delaware",
    "GA": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Georgia",
    "ID": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Idaho",
    "IN": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Indiana",
    "IA": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Iowa",
    "KS": "https://en.wikipedia.org/wiki/List_of_unified_school_districts_in_Kansas",
    "KY": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Kentucky",
    "LA": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Louisiana",
    "ME": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Maine",
    "MD": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Maryland",
    "MA": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Massachusetts",
    "MN": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Minnesota",
    "MS": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Mississippi",
    "MO": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Missouri",
    "MT": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Montana",
    "NE": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Nebraska",
    "NV": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Nevada",
    "NH": "https://en.wikipedia.org/wiki/List_of_school_districts_in_New_Hampshire",
    "NJ": "https://en.wikipedia.org/wiki/List_of_school_districts_in_New_Jersey",
    "NM": "https://en.wikipedia.org/wiki/List_of_school_districts_in_New_Mexico",
    "NY": "https://en.wikipedia.org/wiki/List_of_school_districts_in_New_York",
    "NC": "https://en.wikipedia.org/wiki/List_of_school_districts_in_North_Carolina",
    "ND": "https://en.wikipedia.org/wiki/List_of_school_districts_in_North_Dakota",
    "OH": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Ohio",
    "OK": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Oklahoma",
    "OR": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Oregon",
    "PA": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Pennsylvania",
    "RI": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Rhode_Island",
    "SC": "https://en.wikipedia.org/wiki/List_of_school_districts_in_South_Carolina",
    "SD": "https://en.wikipedia.org/wiki/List_of_school_districts_in_South_Dakota",
    "TN": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Tennessee",
    "UT": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Utah",
    "VT": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Vermont",
    "VA": "https://en.wikipedia.org/wiki/List_of_school_divisions_in_Virginia",
    "WA": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Washington",
    "WV": "https://en.wikipedia.org/wiki/List_of_school_districts_in_West_Virginia",
    "WI": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Wisconsin",
    "WY": "https://en.wikipedia.org/wiki/List_of_school_districts_in_Wyoming",
}

BAD_DOMAINS = {
    "wikipedia.org", "wikidata.org",
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "linkedin.com", "tiktok.com",
    "greatschools.org", "niche.com", "usnews.com",
    "microsoft.com", "support.microsoft.com",
    "google.com", "gemini.google.com",
    "merriam-webster.com", "webmd.com", "ebay.com", "community.ebay.com",
    "lonelyplanet.com", "nhl.com", "genius.com", "army.mil"
}


def clean(s: str) -> str:
    s = re.sub(r"\[\d+\]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def is_bad_domain(url: str) -> bool:
    h = host(url)
    if not h:
        return True
    if h in BAD_DOMAINS:
        return True
    for d in BAD_DOMAINS:
        if h.endswith(d):
            return True
    return False


def fetch(url: str) -> Optional[str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return None
        return r.text
    except Exception:
        return None


def extract_article_titles(list_url: str) -> List[Tuple[str, str]]:
    """
    Returns (district_name, MediaWiki title)
    """
    html = fetch(list_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    out: List[Tuple[str, str]] = []

    for table in soup.select("table.wikitable"):
        for tr in table.select("tr"):
            first = tr.find(["td", "th"])
            if not first:
                continue
            a = first.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            if not href.startswith("/wiki/"):
                continue
            title = href.replace("/wiki/", "")
            if ":" in title:
                continue
            name = clean(first.get_text(" ", strip=True))
            if len(name) < 6 or len(name) > 90:
                continue
            title = title.replace("_", " ")
            out.append((name, title))

    if len(out) < 40:
        for li in soup.select("li"):
            a = li.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            if not href.startswith("/wiki/"):
                continue
            title = href.replace("/wiki/", "")
            if ":" in title:
                continue
            name = clean(li.get_text(" ", strip=True))
            if len(name) < 6 or len(name) > 90 or len(name.split()) > 14:
                continue
            title = title.replace("_", " ")
            out.append((name, title))

    seen = set()
    dedup = []
    for name, title in out:
        if title not in seen:
            seen.add(title)
            dedup.append((name, title))
    return dedup


def wikipedia_title_to_wikidata_qid(title: str) -> Optional[str]:
    api = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageprops",
        "titles": title,
        "redirects": 1
    }
    try:
        r = requests.get(api, params=params, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for _, page in pages.items():
            qid = page.get("pageprops", {}).get("wikibase_item")
            if qid:
                return qid
        return None
    except Exception:
        return None


def wikidata_official_website(qid: str) -> Optional[str]:
    api = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbgetentities",
        "format": "json",
        "ids": qid,
        "props": "claims"
    }
    try:
        r = requests.get(api, params=params, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        data = r.json()
        ent = data.get("entities", {}).get(qid, {})
        claims = ent.get("claims", {})
        p856 = claims.get("P856")
        if not p856:
            return None
        mainsnak = p856[0].get("mainsnak", {})
        dv = mainsnak.get("datavalue", {})
        url = dv.get("value")
        if isinstance(url, str) and url.startswith("http") and not is_bad_domain(url):
            return url
        return None
    except Exception:
        return None


# --------- FALLBACK SEARCH (only when P856 missing) ---------

def plausible_school_domain(url: str) -> bool:
    if not url or is_bad_domain(url):
        return False
    h = host(url)
    u = url.lower()
    # Hard requirements: this blocks nearly all junk
    if ".k12." in u:
        return True
    if any(k in h for k in ["k12", "schools", "school", "district", "usd", "isd", "csd", "ps"]):
        return True
    # allow .edu/.org but only if it includes school-ish tokens
    if (h.endswith(".edu") or h.endswith(".org")) and ("school" in u or "district" in u or "k12" in u):
        return True
    return False


def page_mentions_district(url: str, district_name: str) -> bool:
    html = fetch(url)
    if not html:
        return False
    text = clean(BeautifulSoup(html, "html.parser").get_text(" ", strip=True)).lower()
    dn = district_name.lower()

    # tokens: remove generic words
    toks = [t for t in re.split(r"[^a-z0-9]+", dn) if t and t not in {
        "school", "schools", "district", "public", "area", "unified", "city", "county"
    }]
    toks = [t for t in toks if len(t) >= 4][:4]

    hit = sum(1 for t in toks if t in text)
    return ("school" in text) and (hit >= 2)


def search_fallback_homepage(district_name: str, state_abbr: str) -> Optional[str]:
    q = f"\"{district_name}\" {state_abbr} school district official website"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(q, max_results=SEARCH_RESULTS_PER_QUERY))
    except Exception:
        return None

    for res in results:
        url = res.get("href") or res.get("url")
        if not url:
            continue
        if not plausible_school_domain(url):
            continue
        if page_mentions_district(url, district_name):
            return url

    return None


def write_state_csv(state: str, rows: List[Tuple[str, str, str]]) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"districts_{state}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["district", "state", "homepage"])
        for d, st, hp in rows:
            w.writerow([d, st, hp])
    print(f"Wrote {path} ({len(rows)} districts)")


def main() -> None:
    states = [s for s in sorted(WIKI_URLS.keys()) if s not in EXCLUDE]

    for st in states:
        list_url = WIKI_URLS[st]
        print(f"\n=== {st} {list_url} ===")

        pairs = extract_article_titles(list_url)
        if not pairs:
            print("No district article titles extracted.")
            write_state_csv(st, [])
            continue

        random.shuffle(pairs)

        rows_out: List[Tuple[str, str, str]] = []
        seen_domains = set()

        for district_name, title in pairs:
            if len(rows_out) >= DISTRICTS_PER_STATE:
                break

            district_name = clean(district_name)
            url = None

            # 1) Wikidata official website
            qid = wikipedia_title_to_wikidata_qid(title)
            time.sleep(SLEEP_API)
            if qid:
                url = wikidata_official_website(qid)
                time.sleep(SLEEP_API)

            # 2) Fallback search only if missing
            if not url:
                url = search_fallback_homepage(district_name, st)
                time.sleep(SLEEP_SEARCH)

            if not url:
                continue
            if is_bad_domain(url):
                continue

            dom = host(url)
            if not dom or dom in seen_domains:
                continue
            seen_domains.add(dom)

            rows_out.append((district_name, st, url))

        write_state_csv(st, rows_out)


if __name__ == "__main__":
    main()