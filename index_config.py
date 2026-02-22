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

INPUT_DIR = "inputs"
OUTPUT_DIR = "out"

STATE_FILES = [
    "districts_MI.csv",
    "districts_CA.csv",
    "districts_TX.csv",
    "districts_FL.csv",
    "districts_NY.csv",
    "districts_IL.csv",
]