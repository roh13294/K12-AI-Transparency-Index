#!/usr/bin/env python3
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

import index_config as cfg

AUDITOR = os.path.join("audits", "audit_from_homepage.py")


@dataclass
class DistrictRow:
    district: str
    state: str
    homepage: str
    found_policy_url: str
    found_tech_url: str
    found_contact_url: str
    notes: str
    score_0_to_5: int
    flags: Dict[str, int]
    evidence: Dict[str, str]


def ensure_dirs():
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    os.makedirs(cfg.INPUT_DIR, exist_ok=True)


def tier_for(score_0_100: int) -> str:
    for cutoff, name in cfg.TIERS:
        if score_0_100 >= cutoff:
            return name
    return cfg.TIERS[-1][1]


def safe_read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def run_audit_for_state(input_csv: str, out_csv: str) -> None:
    # Run auditor
    cmd = [sys.executable, AUDITOR, input_csv]
    print(f"\nRunning audit: {input_csv}")
    subprocess.run(cmd, check=True)

    # Move output to state-named file
    if os.path.exists(out_csv):
        os.remove(out_csv)
    shutil.move("audit_results.csv", out_csv)
    print(f"Wrote: {out_csv}")


def parse_audit_csv(path: str) -> List[DistrictRow]:
    rows = safe_read_csv(path)
    out: List[DistrictRow] = []

    flag_cols = list(cfg.WEIGHTS.keys())
    evidence_cols = [f"evidence_{k}" for k in flag_cols]

    for r in rows:
        flags = {k: int((r.get(k) or "0").strip() or "0") for k in flag_cols}
        evidence = {k: (r.get(f"evidence_{k}") or "").strip() for k in flag_cols}

        out.append(
            DistrictRow(
                district=(r.get("district") or "").strip(),
                state=(r.get("state") or "").strip(),
                homepage=(r.get("homepage") or "").strip(),
                found_policy_url=(r.get("found_policy_url") or "").strip(),
                found_tech_url=(r.get("found_tech_url") or "").strip(),
                found_contact_url=(r.get("found_contact_url") or "").strip(),
                notes=(r.get("notes") or "").strip(),
                score_0_to_5=int((r.get("score_0_to_5") or "0").strip() or "0"),
                flags=flags,
                evidence=evidence,
            )
        )
    return out


def compute_index_score(flags: Dict[str, int]) -> int:
    score = 0
    for k, w in cfg.WEIGHTS.items():
        score += int(flags.get(k, 0)) * int(w)
    # score is already 0–100 given the weights sum to 100
    return int(score)


def summarize_state(districts: List[DistrictRow]) -> Dict[str, str]:
    n = len(districts)
    if n == 0:
        return {}

    scores = [compute_index_score(d.flags) for d in districts]
    avg = sum(scores) / max(n, 1)

    tier_counts = defaultdict(int)
    for s in scores:
        tier_counts[tier_for(s)] += 1

    # Flag rates
    rates = {}
    for k in cfg.WEIGHTS.keys():
        rates[k] = sum(d.flags.get(k, 0) for d in districts) / max(n, 1)

    # Pack summary
    return {
        "state": districts[0].state,
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
    }


def build_report(all_rows: List[Dict[str, str]], state_rows: List[Dict[str, str]], out_path: str) -> None:
    # Pick top/bottom examples
    sorted_rows = sorted(all_rows, key=lambda r: int(r["index_score"]), reverse=True)
    top10 = sorted_rows[:10]
    bottom10 = sorted_rows[-10:] if len(sorted_rows) >= 10 else sorted_rows

    # State ranking
    states_sorted = sorted(state_rows, key=lambda r: float(r["avg_index_score"]), reverse=True)

    lines: List[str] = []
    lines.append("# 2026 National K–12 AI Transparency Index (K12-AITI)")
    lines.append("")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## What this is")
    lines.append("A public-signal index measuring whether school districts publish AI governance and transparency information on their websites. This index scores districts based on publicly accessible evidence only.")
    lines.append("")
    lines.append("## Scoring")
    lines.append("Each district is scored 0–100 using binary criteria with fixed weights:")
    for k, w in cfg.WEIGHTS.items():
        lines.append(f"- {k}: {w}")
    lines.append("")
    lines.append("Tier bands:")
    for cutoff, name in cfg.TIERS:
        lines.append(f"- {cutoff}+: {name}")
    lines.append("")
    lines.append("## State summary")
    lines.append("")
    for s in states_sorted:
        lines.append(f"- {s['state']}: avg {s['avg_index_score']} (n={s['districts']}) | No Public Signals={s['no_public_signals']}")
    lines.append("")
    lines.append("## Top 10 districts by score")
    lines.append("")
    for r in top10:
        lines.append(f"- {r['district']} ({r['state']}): {r['index_score']} | {r['tier']} | policy={r['found_policy_url']}")
    lines.append("")
    lines.append("## Bottom 10 districts by score")
    lines.append("")
    for r in bottom10:
        lines.append(f"- {r['district']} ({r['state']}): {r['index_score']} | {r['tier']} | notes={r['notes']}")
    lines.append("")
    lines.append("## Method notes")
    lines.append("- This is a public-signal index. It does not claim districts are or are not using AI internally.")
    lines.append("- Districts can request re-evaluation by publishing links or clarifications.")
    lines.append("- Crawling is time-budgeted per district to avoid slow or broken sites.")
    lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    ensure_dirs()

    # Run audits per state and store results safely
    audit_outputs: List[str] = []
    for fname in cfg.STATE_FILES:
        in_csv = os.path.join(cfg.INPUT_DIR, fname)
        if not os.path.exists(in_csv):
            print(f"Missing input: {in_csv}")
            sys.exit(1)

        state_code = fname.split("_")[-1].split(".")[0]  # districts_MI.csv -> MI
        out_csv = os.path.join(cfg.OUTPUT_DIR, f"audit_results_{state_code}.csv")
        run_audit_for_state(in_csv, out_csv)
        audit_outputs.append(out_csv)

    # Parse + compute index for all
    all_districts: List[DistrictRow] = []
    for p in audit_outputs:
        all_districts.extend(parse_audit_csv(p))

    # Write district_scores.csv
    district_rows: List[Dict[str, str]] = []
    for d in all_districts:
        idx = compute_index_score(d.flags)
        row = {
            "district": d.district,
            "state": d.state,
            "homepage": d.homepage,
            "index_score": str(idx),
            "tier": tier_for(idx),
            "found_policy_url": d.found_policy_url,
            "found_tech_url": d.found_tech_url,
            "found_contact_url": d.found_contact_url,
            "notes": d.notes,
        }
        for k in cfg.WEIGHTS.keys():
            row[k] = str(d.flags.get(k, 0))
            row[f"evidence_{k}"] = d.evidence.get(k, "")
        district_rows.append(row)

    district_path = os.path.join(cfg.OUTPUT_DIR, "district_scores.csv")
    district_fields = list(district_rows[0].keys()) if district_rows else []
    write_csv(district_path, district_fields, district_rows)
    print(f"\nWrote: {district_path}")

    # State summary
    by_state: Dict[str, List[DistrictRow]] = defaultdict(list)
    for d in all_districts:
        if d.state:
            by_state[d.state].append(d)

    state_rows: List[Dict[str, str]] = []
    for st, ds in sorted(by_state.items()):
        state_rows.append(summarize_state(ds))

    state_path = os.path.join(cfg.OUTPUT_DIR, "state_summary.csv")
    state_fields = list(state_rows[0].keys()) if state_rows else []
    write_csv(state_path, state_fields, state_rows)
    print(f"Wrote: {state_path}")

    # index.json for website use
    json_path = os.path.join(cfg.OUTPUT_DIR, "index.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "weights": cfg.WEIGHTS,
                "tiers": cfg.TIERS,
                "districts": district_rows,
                "states": state_rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Wrote: {json_path}")

    # Draft report markdown
    report_path = os.path.join(cfg.OUTPUT_DIR, "REPORT.md")
    build_report(district_rows, state_rows, report_path)
    print(f"Wrote: {report_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()