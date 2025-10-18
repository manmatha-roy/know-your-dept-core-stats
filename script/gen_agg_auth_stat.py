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
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

# ------------------------------
# Colors for terminal output
# ------------------------------
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

# ------------------------------
# Argument parsing
# ------------------------------
parser = argparse.ArgumentParser(
    description="Aggregate A/A* publication counts for faculty list using CORE2023 database."
)
parser.add_argument("faculty_csv", help="Path to faculty_list.csv")
parser.add_argument("--since", type=int, default=2015, help="Consider publications from this year onwards")
parser.add_argument("--quiet", action="store_true", help="Suppress per-person processing lines")
args = parser.parse_args()

input_file = args.faculty_csv
since_year = args.since
quiet_mode = args.quiet

# ------------------------------
# File and directory setup
# ------------------------------
if not os.path.isfile(input_file):
    print(f"{RED}❌ File '{input_file}' does not exist.{RESET}")
    sys.exit(1)

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
base_name = os.path.splitext(os.path.basename(input_file))[0]

os.makedirs("data", exist_ok=True)
os.makedirs(".cache", exist_ok=True)
os.makedirs("log", exist_ok=True)

log_file = f"log/{base_name}_{timestamp}.log"
agg_file = f"log/{base_name}_agg_{timestamp}.csv"

logging.basicConfig(filename=log_file, level=logging.INFO, filemode="w", format="%(message)s")

# ------------------------------
# Helper functions
# ------------------------------
def normalize_title(title):
    """Normalize conference names for reliable matching."""
    if not title:
        return ""
    title = title.strip().lower()
    title = title.replace("-", "/").replace("_", "/")
    title = re.sub(r"[,\s]+", " ", title)
    title = re.sub(r"\s*\(.*?\)", "", title)
    title = re.sub(r"\b(19|20)\d{2}\b", "", title)
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"/+", "/", title)
    return title.strip()

def print_status(msg, color=CYAN, force=False):
    if not quiet_mode or force:
        print(f"{color}{msg}{RESET}")

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

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False

# ------------------------------
# Load CORE database
# ------------------------------
core_path = "data/core_onlyA_exclude_NLP.csv"
if not os.path.isfile(core_path):
    print(f"{RED}❌ CORE database file '{core_path}' not found in ./data/{RESET}")
    sys.exit(1)

core_df = pd.read_csv(core_path, header=None, names=["fullname", "shortname", "rating"])
core_df["shortname"] = core_df["shortname"].astype(str).str.strip()
core_df["rating"] = core_df["rating"].astype(str).str.strip()
core_df["normalized_shortname"] = core_df["shortname"].apply(normalize_title)
normalized_shortnames = dict(zip(core_df["normalized_shortname"], core_df["rating"]))

# ------------------------------
# Load faculty list
# ------------------------------
persons_df = pd.read_csv(input_file, header=None, names=["name", "url"])

overall_A = 0
overall_A_star = 0
person_summary = []

print_status(f"➡ Processing {input_file} \n\n", force=True)

# ------------------------------
# Process each faculty entry
# ------------------------------
downloaded_count = 0
cached_count = 0

for _, row in persons_df.iterrows():
    name = row["name"].strip()
    url = row["url"].strip()
    
    if not is_valid_url(url) or not url.endswith(".html"):
        print_status(f"[{name}] ❌ Invalid URL: {url}", color=RED, force=True)
        person_summary.append({"person": name, "A*": 0, "A": 0})
        continue

    xml_url = url.replace(".html", ".xml")
    hash_key = hashlib.sha1(xml_url.encode("utf-8")).hexdigest()
    xml_filename = f".cache/{hash_key}.xml"

    count_A = 0
    count_A_star = 0

    if not quiet_mode:
        print_status(f"[{name}] Processing URL: {url}", force=True)

    try:
        # Fetch XML (cache or download)
        if not os.path.exists(xml_filename):
            try:
                with urllib.request.urlopen(xml_url) as response:
                    if response.status != 200:
                        raise HTTPError(xml_url, response.status, "HTTP Error", hdrs=None, fp=None)
                    xml_content = response.read()
                with open(xml_filename, "wb") as f:
                    f.write(xml_content)
                if not quiet_mode:
                    print_status(f"[{name}] Downloaded and cached XML", force=True)
                downloaded_count += 1
            except (HTTPError, URLError) as e:
                print_status(f"[{name}] ❌ Invalid URL or not reachable", color=RED, force=True)
                person_summary.append({"person": name, "A*": 0, "A": 0})
                continue
        else:
            if not quiet_mode:
                print_status(f"[{name}] Using cached XML", force=True)
            cached_count += 1

        # Parse XML safely
        parser = etree.XMLParser(recover=True)
        tree = etree.parse(xml_filename, parser)
        root = tree.getroot()

        # Count A / A* papers
        for r in root.findall("r"):
            try:
                inproc = r.find("inproceedings")
                if inproc is None:
                    continue
                year_tag = inproc.find("year")
                booktitle_tag = inproc.find("booktitle")
                if year_tag is None or booktitle_tag is None:
                    continue
                year = int(year_tag.text)
                if year < since_year:
                    continue
                booktitle = booktitle_tag.text.strip()
                normalized_booktitle = normalize_title(booktitle)
                if normalized_booktitle in normalized_shortnames:
                    rating = normalized_shortnames[normalized_booktitle]
                    logging.info(f"{name}\t{year}\t{booktitle}\t{rating}")
                    if rating == "A":
                        count_A += 1
                        overall_A += 1
                    elif rating == "A*":
                        count_A_star += 1
                        overall_A_star += 1
            except Exception:
                continue

        if not quiet_mode:
            print_status(f"[{name}] Done. A*: {count_A_star}, A: {count_A}", force=True)

    except Exception:
        print_status(f"[{name}] ❌ Invalid URL or not reachable", color=RED, force=True)
        count_A = 0
        count_A_star = 0

    person_summary.append({"person": name, "A*": count_A_star, "A": count_A})

# ------------------------------
# Download vs Cached summary
# ------------------------------
print(f"\n💾 Downloaded XMLs: {downloaded_count} | Cached XMLs used: {cached_count}\n")

# ------------------------------
# Print colored summaries
# ------------------------------
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

# ------------------------------
# Save results
# ------------------------------
summary_df = pd.DataFrame(person_summary)
summary_df.to_csv(agg_file, index=False)

print(f"\n✅ Detailed log saved to: {log_file}")
print(f"✅ Per-person aggregate summary saved to: {agg_file}\n")

