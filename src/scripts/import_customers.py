import json
from pathlib import Path

import pandas as pd


# Kořen projektu
BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = BASE_DIR / "data" / "customers.ods"
OUTPUT_FILE = BASE_DIR / "data" / "customers.json"


def clean(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def main():
    print(f"Načítám: {INPUT_FILE}")

    df = pd.read_excel(INPUT_FILE, engine="odf", header=None)

    customers = {}

    for _, row in df.iterrows():
        server = clean(row.iloc[0])      # Sloupec A
        company = clean(row.iloc[1])     # Sloupec B
        address = clean(row.iloc[21])    # Sloupec V

        if not company:
            continue

        key = company.lower()

        # duplicity ignorujeme
        if key in customers:
            continue

        customers[key] = {
            "server": server,
            "company": company,
            "address": address,
        }

    result = sorted(
        customers.values(),
        key=lambda x: x["company"].lower()
    )

    OUTPUT_FILE.parent.mkdir(exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print()
    print("=" * 50)
    print(f"Import dokončen.")
    print(f"Zákazníků: {len(result)}")
    print(f"Výstup: {OUTPUT_FILE}")
    print("=" * 50)


if __name__ == "__main__":
    main()