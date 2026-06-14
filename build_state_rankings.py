#!/usr/bin/env python3
import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

DATA_DIR = Path("data")
DISTRICT_JSON_PATH = DATA_DIR / "district_scores.json"
DISTRICT_CSV_PATH = DATA_DIR / "district_scores.csv"
STATE_SUMMARY_CSV_PATH = DATA_DIR / "state_summary.csv"
STATE_RANKINGS_JSON_PATH = DATA_DIR / "state_rankings.json"

STATE_NAMES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}

CRITERIA_LABELS = {
    "public_ai_policy_exists": "Public AI policy located",
    "ai_use_publicly_disclosed": "Public AI use disclosure located",
    "oversight_named": "Named oversight located",
    "board_policy_mentions_ai": "Board policy mention located",
    "public_contact_available": "Public contact pathway located",
}

TIER_KEYS = [
    ("Leading Transparency", "leading_transparency"),
    ("Emerging Governance", "emerging_governance"),
    ("Limited Disclosure", "limited_disclosure"),
    ("Minimal Transparency", "minimal_transparency"),
    ("No Public AI Governance Signals", "no_public_signals"),
]


def to_int(value):
    try:
        return int(str(value).strip())
    except Exception:
        return 0


def compare_previous_summary(existing_rows, expected_rows):
    existing = {row["state"]: row for row in existing_rows}
    mismatch_count = 0

    for row in expected_rows:
        previous = existing.get(row["state"])
        if previous != row:
            mismatch_count += 1

    if len(existing_rows) != len(expected_rows):
        print(
            f"Previous {STATE_SUMMARY_CSV_PATH} had {len(existing_rows)} rows; "
            f"computed summary has {len(expected_rows)} rows."
        )
    else:
        print(
            f"Previous {STATE_SUMMARY_CSV_PATH} had matching row count but "
            f"{mismatch_count} rows differed from the live JSON-derived summary."
        )


def summarize_state(state_code, rows):
    scores = [to_int(row["index_score"]) for row in rows]
    districts_audited = len(rows)
    average_score = sum(scores) / districts_audited
    median_score = statistics.median(scores)

    highest = max(rows, key=lambda row: (to_int(row["index_score"]), row["district"].lower()))
    lowest = min(rows, key=lambda row: (to_int(row["index_score"]), row["district"].lower()))

    tier_counts = Counter(row.get("tier", "") for row in rows)

    criteria_counts = {}
    criteria_rates = {}
    for key in CRITERIA_LABELS:
        count = sum(to_int(row.get(key, 0)) for row in rows)
        criteria_counts[key] = count
        criteria_rates[key] = round(count / districts_audited, 4)

    tier_distribution = {
        "leading_transparency": tier_counts.get("Leading Transparency", 0),
        "emerging_governance": tier_counts.get("Emerging Governance", 0),
        "limited_disclosure": tier_counts.get("Limited Disclosure", 0),
        "minimal_transparency": tier_counts.get("Minimal Transparency", 0),
        "no_public_signals": tier_counts.get("No Public AI Governance Signals", 0),
    }

    return {
        "state_code": state_code,
        "state_name": STATE_NAMES[state_code],
        "districts_audited": districts_audited,
        "average_score": round(average_score, 2),
        "median_score": round(float(median_score), 2),
        "highest_scoring_district": highest["district"],
        "highest_score": to_int(highest["index_score"]),
        "lowest_scoring_district": lowest["district"],
        "lowest_score": to_int(lowest["index_score"]),
        "tier_distribution": tier_distribution,
        "criteria_counts": criteria_counts,
        "criteria_rates": criteria_rates,
    }


def build_state_summary_rows(state_records):
    rows = []
    for record in sorted(state_records, key=lambda item: item["state_code"]):
        row = {
            "state": record["state_code"],
            "districts": str(record["districts_audited"]),
            "avg_index_score": f"{record['average_score']:.1f}",
        }

        for _, key in TIER_KEYS:
            row[key] = str(record["tier_distribution"][key])

        for key in CRITERIA_LABELS:
            row[f"rate_{key}"] = f"{record['criteria_rates'][key]:.3f}"

        rows.append(row)

    return rows


def main():
    district_rows = json.loads(DISTRICT_JSON_PATH.read_text(encoding="utf-8"))
    if not isinstance(district_rows, list) or not district_rows:
        raise SystemExit("data/district_scores.json is missing rows.")

    grouped = defaultdict(list)
    for row in district_rows:
        grouped[row["state"]].append(row)

    state_records = [summarize_state(state_code, rows) for state_code, rows in grouped.items()]
    ranked_states = sorted(
        state_records,
        key=lambda item: (-item["average_score"], -item["districts_audited"], item["state_name"]),
    )

    for index, record in enumerate(ranked_states, start=1):
        record["rank"] = index

    scores = [to_int(row["index_score"]) for row in district_rows]
    state_average_scores = [record["average_score"] for record in state_records]
    zero_score_districts = sum(1 for score in scores if score == 0)

    national_criteria_counts = {
        key: sum(to_int(row.get(key, 0)) for row in district_rows)
        for key in CRITERIA_LABELS
    }

    national_criteria_rates = {
        key: round(value / len(district_rows), 4)
        for key, value in national_criteria_counts.items()
    }

    national_tier_distribution = Counter(row.get("tier", "") for row in district_rows)
    national_payload = {
        "generated_at": date.today().isoformat(),
        "source_path": str(DISTRICT_JSON_PATH),
        "districts_audited": len(district_rows),
        "states_covered": len(grouped),
        "national_average_score": round(sum(scores) / len(scores), 2),
        "national_median_score": round(float(statistics.median(scores)), 2),
        "zero_score_districts": zero_score_districts,
        "zero_score_rate": round(zero_score_districts / len(district_rows), 4),
        "median_state_average": round(float(statistics.median(state_average_scores)), 2),
        "highest_average_state": {
            "state_code": ranked_states[0]["state_code"],
            "state_name": ranked_states[0]["state_name"],
            "average_score": ranked_states[0]["average_score"],
            "districts_audited": ranked_states[0]["districts_audited"],
        },
        "lowest_average_state": {
            "state_code": ranked_states[-1]["state_code"],
            "state_name": ranked_states[-1]["state_name"],
            "average_score": ranked_states[-1]["average_score"],
            "districts_audited": ranked_states[-1]["districts_audited"],
        },
        "national_tier_distribution": {
            "leading_transparency": national_tier_distribution.get("Leading Transparency", 0),
            "emerging_governance": national_tier_distribution.get("Emerging Governance", 0),
            "limited_disclosure": national_tier_distribution.get("Limited Disclosure", 0),
            "minimal_transparency": national_tier_distribution.get("Minimal Transparency", 0),
            "no_public_signals": national_tier_distribution.get("No Public AI Governance Signals", 0),
        },
        "criteria_labels": CRITERIA_LABELS,
        "national_criteria_counts": national_criteria_counts,
        "national_criteria_rates": national_criteria_rates,
    }

    payload = {
        "national_summary": national_payload,
        "states": ranked_states,
    }

    existing_summary_rows = []
    if STATE_SUMMARY_CSV_PATH.exists():
        with STATE_SUMMARY_CSV_PATH.open(newline="", encoding="utf-8") as handle:
            existing_summary_rows = list(csv.DictReader(handle))

    summary_rows = build_state_summary_rows(state_records)
    compare_previous_summary(existing_summary_rows, summary_rows)

    district_fields = list(district_rows[0].keys())
    with DISTRICT_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=district_fields)
        writer.writeheader()
        writer.writerows(district_rows)

    with STATE_SUMMARY_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    STATE_RANKINGS_JSON_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {DISTRICT_CSV_PATH}")
    print(f"Wrote {STATE_SUMMARY_CSV_PATH}")
    print(f"Wrote {STATE_RANKINGS_JSON_PATH}")


if __name__ == "__main__":
    main()
