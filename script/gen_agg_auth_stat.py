import xml.etree.ElementTree as ET
import pandas as pd
import urllib.request
from tabulate import tabulate
import datetime
import os
import sys
import logging
import re

# --------------------------
# Command-line argument check
# --------------------------
if len(sys.argv) < 2:
    print("Usage: python gen_agg_auth_stat.py <path-to-faculty_list.csv>")
    sys.exit(1)

input_file = sys.argv[1]

if not os.path.isfile(input_file):
    print(f"File '{input_file}' does not exist.")
    sys.exit(1)

# --------------------------
# Prepare directories and files
# --------------------------
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
base_name = os.path.splitext(os.path.basename(input_file))[0]

# Directory for logs, aggregates, and temp downloads
os.makedirs("data", exist_ok=True)
os.makedirs("temp", exist_ok=True)

log_file = f"log/{base_name}_{timestamp}.log"
agg_file = f"log/{base_name}_agg_{timestamp}.csv"

# Setup logging
logging.basicConfig(filename=log_file, level=logging.INFO, filemode='w', format='%(message)s')

# --------------------------
# Normalization function
# --------------------------
def normalize_title(title):
    if not title:
        return ""
    # Remove anything in parentheses, e.g. "ECIR (1)" → "ECIR"
    title = re.sub(r"\s*\(.*?\).*", "", title)
    # Replace '-', '_' with '/'
    title = title.replace("-", "/").replace("_", "/")
    title = re.sub(r"\s+", " ", title)
    return title.strip().lower()

# --------------------------
# Load CORE database and normalize
# --------------------------
core_df = pd.read_csv("data/core_onlyA.csv", header=None, names=["fullname", "shortname", "rating"])
core_df["shortname"] = core_df["shortname"].str.strip()
core_df["rating"] = core_df["rating"].str.strip()
core_df["normalized_shortname"] = core_df["shortname"].apply(normalize_title)
normalized_shortnames = dict(zip(core_df["normalized_shortname"], core_df["rating"]))

# --------------------------
# Load faculty list
# --------------------------
persons_df = pd.read_csv(input_file, header=None, names=["name", "url"])

overall_A = 0
overall_A_star = 0
person_summary = []

# --------------------------
# Process each person
# --------------------------
for idx, row in persons_df.iterrows():
    name = row["name"].strip()
    url = row["url"].strip()
    xml_url = url.replace(".html", ".xml")

    # Local temp XML filename (safe for filesystem)
    xml_filename = f"cache/{name.replace(' ', '_').replace('/', '_')}.xml"

    count_A = 0
    count_A_star = 0

    try:
        # Download only if not already cached
        if not os.path.exists(xml_filename):
            print(f"Downloading XML for {name}...")
            with urllib.request.urlopen(xml_url) as response:
                xml_content = response.read()
            with open(xml_filename, "wb") as f:
                f.write(xml_content)
        else:
            print(f"Using cached XML for {name}.")

        # Parse XML
        tree = ET.parse(xml_filename)
        root = tree.getroot()

        for r in root.findall("r"):
            inproc = r.find("inproceedings")
            if inproc is not None:
                year_tag = inproc.find("year")
                booktitle_tag = inproc.find("booktitle")
                if year_tag is not None and booktitle_tag is not None:
                    try:
                        year = int(year_tag.text)
                    except:
                        continue
                    if year >= 2015:
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

        person_summary.append({"person": name, "A*": count_A_star, "A": count_A})

    except Exception as e:
        print(f"Failed to process {name}: {e}")
        person_summary.append({"person": name, "A*": 0, "A": 0})

# --------------------------
# Print summaries
# --------------------------
print("\nPer-person summary:\n")
print(tabulate(person_summary, headers="keys", tablefmt="grid"))

print("\nOverall counts:\n")
print(tabulate([{"A*": overall_A_star, "A": overall_A}], headers="keys", tablefmt="grid"))

# --------------------------
# Save results
# --------------------------
summary_df = pd.DataFrame(person_summary)
summary_df.to_csv(agg_file, index=False)

print(f"\nAll matched conferences have been logged to '{log_file}'.")
print(f"Per-person aggregate summary saved to '{agg_file}'.")


