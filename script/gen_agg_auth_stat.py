import xml.etree.ElementTree as ET
import pandas as pd
import urllib.request
from tabulate import tabulate
import datetime
import os
import sys
import logging
import re

if len(sys.argv) < 2:
    print("Usage: python gen_agg_auth_stat.py <path-to-faculty_list.csv>")
    sys.exit(1)

input_file = sys.argv[1]

# Check if the file exists
if not os.path.isfile(input_file):
    print(f"File '{input_file}' does not exist.")
    sys.exit(1)

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
base_name = os.path.splitext(os.path.basename(input_file))[0]

try:
    temp_df = pd.read_csv(input_file, header=None)
    if len(temp_df) == 1:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
except Exception:
    pass

log_file = f"log/{base_name}_{timestamp}.log"
agg_file = f"log/{base_name}_agg_{timestamp}.csv"

# --- Setup logging ---
logging.basicConfig(filename=log_file, level=logging.INFO, filemode='w', format='%(message)s')

# --- Normalization function ---
def normalize_title(title):
    if not title:
        return ""
    title = re.sub(r"\s*\(.*?\)", "", title)
    title = title.replace("-", "/").replace("_", "/")
    title = re.sub(r"\s+", " ", title)  # collapse any whitespace
    return title.strip().lower()

# Load core CSV
core_df = pd.read_csv("data/core_onlyA.csv", header=None, names=["fullname", "shortname", "rating"])
core_df["shortname"] = core_df["shortname"].str.strip()
core_df["rating"] = core_df["rating"].str.strip()
# Normalize shortnames
core_df["normalized_shortname"] = core_df["shortname"].apply(normalize_title)
normalized_shortnames = dict(zip(core_df["normalized_shortname"], core_df["rating"]))

# Load person list (CSV with Name, DBLP HTML URL)
persons_df = pd.read_csv(input_file, header=None, names=["name", "url"])

# Initialize overall counts
overall_A = 0
overall_A_star = 0
person_summary = []

for idx, row in persons_df.iterrows():
    name = row["name"].strip()
    url = row["url"].strip()
    xml_url = url.replace(".html", ".xml")  # convert to XML

    count_A = 0
    count_A_star = 0

    try:
        with urllib.request.urlopen(xml_url) as response:
            xml_content = response.read()
        root = ET.fromstring(xml_content)

        # Iterate over <r>
        for r in root.findall("r"):
            inproc = r.find("inproceedings")
            if inproc is not None:
                year_tag = inproc.find("year")
                booktitle_tag = inproc.find("booktitle")
                if year_tag is not None and booktitle_tag is not None:
                    year = int(year_tag.text)
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

        # Append per-person summary
        person_summary.append({"person": name, "A*": count_A_star, "A": count_A})

    except Exception as e:
        print(f"Failed to fetch or parse XML for {name}: {e}")
        person_summary.append({"person": name, "A*": 0, "A": 0})

# Print per-person summary using tabulate
print("\nPer-person summary:\n")
print(tabulate(person_summary, headers="keys", tablefmt="grid"))

# Print overall counts
print("\nOverall counts:\n")
print(tabulate([{"A*": overall_A_star, "A": overall_A}], headers="keys", tablefmt="grid"))

# Save per-person summary to CSV
summary_df = pd.DataFrame(person_summary)
summary_df.to_csv(agg_file, index=False)

print(f"\nTranscript has been logged to '{log_file}'.")
print(f"Aggregate summary saved to '{agg_file}'.")

