#!/usr/bin/env python3
from lxml import etree
import pandas as pd
import urllib.request
from tabulate import tabulate
import datetime
import os
import sys
import logging
import re
import hashlib
import argparse
from tqdm import tqdm
from collections import defaultdict

# ------------------------------
# Colors for terminal output
# ------------------------------
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

# ------------------------------------------------------------
# Argument parsing
# ------------------------------------------------------------
parser = argparse.ArgumentParser(
    description="Aggregate A/A* publication counts for faculty list using CORE2023 database."
)
parser.add_argument("faculty_csv", help="Path to faculty_list.csv")
parser.add_argument("--since", type=int, default=2015, help="Consider publications from this year onwards")
args = parser.parse_args()

input_file = args.faculty_csv
since_year = args.since

# ------------------------------------------------------------
# File and directory setup
# ------------------------------------------------------------
if not os.path.isfile(input_file):
    print(f"❌ File '{input_file}' does not exist.")
    sys.exit(1)

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
base_name = os.path.splitext(os.path.basename(input_file))[0]

os.makedirs("data", exist_ok=True)
os.makedirs("temp", exist_ok=True)
os.makedirs(".cache", exist_ok=True)
os.makedirs("log", exist_ok=True)

log_file = f"log/{base_name}_{timestamp}.log"
agg_file = f"log/{base_name}_agg_{timestamp}.csv"

logging.basicConfig(filename=log_file, level=logging.INFO, filemode="w", format="%(message)s")

# ------------------------------------------------------------
# Normalization function
# ------------------------------------------------------------
def normalize_title(title):
    """Normalize conference names for reliable matching."""
    if not title:
        return ""

    title = title.strip().lower()
    title = title.replace("-", "/").replace("_", "/")

    # Remove commas, parentheses, and years
    title = re.sub(r"[,\s]+", " ", title)
    title = re.sub(r"\s*\(.*?\)", "", title)
    title = re.sub(r"\b(19|20)\d{2}\b", "", title)

    # Normalize spacing and multiple slashes
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"/+", "/", title)
    return title.strip()

# ------------------------------------------------------------
# Load CORE database
# ------------------------------------------------------------
core_path = "data/core_onlyA.csv"
if not os.path.isfile(core_path):
    print(f"❌ CORE database file '{core_path}' not found in ./data/")
    sys.exit(1)

core_df = pd.read_csv(core_path, header=None, names=["fullname", "shortname", "rating"])
core_df["shortname"] = core_df["shortname"].astype(str).str.strip()
core_df["rating"] = core_df["rating"].astype(str).str.strip()
core_df["normalized_shortname"] = core_df["shortname"].apply(normalize_title)
normalized_shortnames = dict(zip(core_df["normalized_shortname"], core_df["rating"]))

# ------------------------------------------------------------
# Load faculty list
# ------------------------------------------------------------
persons_df = pd.read_csv(input_file, header=None, names=["name", "url"])

overall_A = 0
overall_A_star = 0
person_summary = []

# ------------------------------------------------------------
# Institute-level distinct count tracking
# ------------------------------------------------------------
institute_papers_set = set()         # store (normalized_title, rating) for distinct counting
institute_venue_counter = defaultdict(int)  # venue -> count

# ------------------------------------------------------------
# Function to colorize tables
# ------------------------------------------------------------
def colorize_table(person_summary):
    colored_rows = []
    for row in person_summary:
        colored_row = {
            "person": f"{CYAN}{row['person']}{RESET}",
            "A*": f"{GREEN}{row['A*']}{RESET}" if row['A*'] > 0 else f"{RED}0{RESET}",
            "A": f"{YELLOW}{row['A']}{RESET}" if row['A'] > 0 else f"{RED}0{RESET}"
        }
        colored_rows.append(colored_row)
    return colored_rows

# ------------------------------------------------------------
# Process each faculty entry
# ------------------------------------------------------------
tqdm.write(f"{CYAN}🔍 Processing {len(persons_df)} faculty profiles (since {since_year})...{RESET}\n")

with tqdm(total=len(persons_df), desc="Overall Progress", ncols=100, colour="blue") as pbar:
    downloaded_count = 0
    cached_count = 0

    for _, row in persons_df.iterrows():
        name = row["name"].strip()
        url = row["url"].strip()
        xml_url = url.replace(".html", ".xml")

        hash_key = hashlib.sha1(xml_url.encode("utf-8")).hexdigest()
        xml_filename = f".cache/{hash_key}.xml"

        count_A = 0
        count_A_star = 0

        try:
            if not os.path.exists(xml_filename):
                tqdm.write(f"{YELLOW}[{name}] Downloading XML...{RESET}")
                with urllib.request.urlopen(xml_url) as response:
                    xml_content = response.read()
                with open(xml_filename, "wb") as f:
                    f.write(xml_content)
                downloaded_count += 1
            else:
                cached_count += 1

            parser = etree.XMLParser(recover=True)
            tree = etree.parse(xml_filename, parser)
            root = tree.getroot()

            # Count A / A* papers per person & track institute-level distinct papers
            for r in root.findall("r"):
                inproc = r.find("inproceedings")
                if inproc is not None:
                    year_tag = inproc.find("year")
                    booktitle_tag = inproc.find("booktitle")
                    if year_tag is None or booktitle_tag is None:
                        continue

                    try:
                        year = int(year_tag.text)
                    except (ValueError, TypeError):
                        continue

                    if year >= since_year:
                        booktitle = booktitle_tag.text.strip()
                        normalized_booktitle = normalize_title(booktitle)

                        if normalized_booktitle in normalized_shortnames:
                            rating = normalized_shortnames[normalized_booktitle]
                            logging.info(f"{name}\t{year}\t{booktitle}\t{rating}")

                            # per person counts
                            if rating == "A":
                                count_A += 1
                                overall_A += 1
                            elif rating == "A*":
                                count_A_star += 1
                                overall_A_star += 1

                            # institute-level distinct count
                            institute_papers_set.add((normalized_booktitle, rating))
                            # venue count for top-3
                            institute_venue_counter[normalized_booktitle] += 1

            person_summary.append({"person": name, "A*": count_A_star, "A": count_A})

        except Exception as e:
            tqdm.write(f"{RED}[{name}] Failed: {e}{RESET}")
            person_summary.append({"person": name, "A*": 0, "A": 0})

        pbar.update(1)

# ------------------------------------------------------------
# Download vs Cached summary
# ------------------------------------------------------------
print(f"\n💾 Downloaded XMLs: {downloaded_count} | Cached XMLs used: {cached_count}")

# ------------------------------------------------------------
# Institute-level distinct counts
# ------------------------------------------------------------
distinct_A_star = sum(1 for (_, rating) in institute_papers_set if rating == "A*")
distinct_A = sum(1 for (_, rating) in institute_papers_set if rating == "A")

# Top-3 venues with counts
top_3_confs = sorted(institute_venue_counter.items(), key=lambda x: x[1], reverse=True)[:3]
top_3_confs_str = [f"{c[0]} ({c[1]})" for c in top_3_confs]
while len(top_3_confs_str) < 3:
    top_3_confs_str.append("-")

# ------------------------------------------------------------
# Print colored summaries
# ------------------------------------------------------------
print("\n📊 Per-person summary:\n")
colored_summary = colorize_table(person_summary)
print(tabulate(colored_summary, headers="keys", tablefmt="grid"))

print("\n🔢 Overall counts:\n")
overall_table = [
    {
        "A*": f"{GREEN}{overall_A_star}{RESET}" if overall_A_star > 0 else f"{RED}0{RESET}",
        "A": f"{YELLOW}{overall_A}{RESET}" if overall_A > 0 else f"{RED}0{RESET}"
    }
]
print(tabulate(overall_table, headers="keys", tablefmt="grid"))

print("\n🏫 Institute-level distinct counts:\n")
institute_table = [
    {
        "Distinct A*": f"{GREEN}{distinct_A_star}{RESET}",
        "Distinct A": f"{YELLOW}{distinct_A}{RESET}",
        "Top 3 Venues": ", ".join(top_3_confs_str)
    }
]
print(tabulate(institute_table, headers="keys", tablefmt="grid"))

# ------------------------------------------------------------
# Save results
# ------------------------------------------------------------
summary_df = pd.DataFrame(person_summary)
summary_df.to_csv(agg_file, index=False)

print(f"\n✅ Detailed log saved to: {log_file}")
print(f"✅ Per-person aggregate summary saved to: {agg_file}\n")

