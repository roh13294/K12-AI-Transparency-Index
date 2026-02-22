#!/usr/bin/env python3
import csv
import glob
import os
from collections import defaultdict

WEIGHTS = {
    "public_ai_policy_exists": 30,
    "ai_use_publicly_disclosed": 25,
    "oversight_named": 20,
    "board_policy_mentions_ai": 15,
    "public_contact_available": 10,
}

TIERS = [
    (80, "Leading Transparency"),
    (60, "Emerging Governance"),
    (40, "Limited Disclosure"),
    (20, "Minimal Transparency"),
    (0,  "No Public AI Governance Signals"),
]

OUT_DIR = "out"

def tier_for(score: int) -> str:
    for cutoff, name in TIERS:
        if score >= cutoff:
            return name
    return TIERS[-1][1]

def to_int(x) -> int:
    try:
        return int(str(x).strip())
    except Exception:
        return 0

def index_score(row: dict) -> int:
    # expects 0/1 columns for each criterion
    s = 0
    for k, w in WEIGHTS.items():
        s += to_int(row.get(k, 0)) * w
    return int(s)

def main():
    paths = sorted(glob.glob(os.path.join(OUT_DIR, "audit_results_*.csv")))
    if not paths:
        raise SystemExit("No files found: out/audit_results_*.csv")

    all_rows = []
    by_state = defaultdict(list)

    for p in paths:
        with open(p, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                st = (row.get("state") or "").strip()
                dist = (row.get("district") or "").strip()
                homepage = (row.get("homepage") or "").strip()

                score100 = index_score(row)
                tier = tier_for(score100)

                out_row = {
                    "district": dist,
                    "state": st,
                    "homepage": homepage,
                    "index_score": str(score100),
                    "tier": tier,
                    "found_policy_url": (row.get("found_policy_url") or "").strip(),
                    "found_tech_url": (row.get("found_tech_url") or "").strip(),
                    "found_contact_url": (row.get("found_contact_url") or "").strip(),
                    "notes": (row.get("notes") or "").strip(),
                    "score_0_to_5": (row.get("score_0_to_5") or "").strip(),
                }

                # keep the raw flags + evidence as receipts
                for k in WEIGHTS.keys():
                    out_row[k] = str(to_int(row.get(k, 0)))
                    out_row[f"evidence_{k}"] = (row.get(f"evidence_{k}") or "").strip()

                all_rows.append(out_row)
                if st:
                    by_state[st].append(out_row)

    # Write district_scores.csv
    district_out = os.path.join(OUT_DIR, "district_scores.csv")
    district_fields = list(all_rows[0].keys()) if all_rows else []
    with open(district_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=district_fields)
        w.writeheader()
        w.writerows(all_rows)

    # Write state_summary.csv
    state_rows = []
    for st, rows in sorted(by_state.items()):
        n = len(rows)
        scores = [to_int(x["index_score"]) for x in rows]
        avg = sum(scores) / max(n, 1)

        tier_counts = defaultdict(int)
        for s in scores:
            tier_counts[tier_for(s)] += 1

        rates = {}
        for k in WEIGHTS.keys():
            rates[k] = sum(to_int(x[k]) for x in rows) / max(n, 1)

        state_rows.append({
            "state": st,
            "districts": str(n),
            "avg_index_score": f"{avg:.1f}",
            "leading_transparency": str(tier_counts["Leading Transparency"]),
            "emerging_governance": str(tier_counts["Emerging Governance"]),
            "limited_disclosure": str(tier_counts["Limited Disclosure"]),
            "minimal_transparency": str(tier_counts["Minimal Transparency"]),
            "no_public_signals": str(tier_counts["No Public AI Governance Signals"]),
            "rate_public_ai_policy_exists": f"{rates['public_ai_policy_exists']:.3f}",
            "rate_ai_use_publicly_disclosed": f"{rates['ai_use_publicly_disclosed']:.3f}",
            "rate_oversight_named": f"{rates['oversight_named']:.3f}",
            "rate_board_policy_mentions_ai": f"{rates['board_policy_mentions_ai']:.3f}",
            "rate_public_contact_available": f"{rates['public_contact_available']:.3f}",
        })

    state_out = os.path.join(OUT_DIR, "state_summary.csv")
    if state_rows:
        with open(state_out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(state_rows[0].keys()))
            w.writeheader()
            w.writerows(state_rows)

    print(f"Wrote: {district_out}")
    print(f"Wrote: {state_out}")

if __name__ == "__main__":
    main()

