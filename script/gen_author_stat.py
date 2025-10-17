import xml.etree.ElementTree as ET
import pandas as pd

# Load CSV
core_df = pd.read_csv("core_onlyA.csv", header=None, names=["fullname", "shortname", "rating"])
core_df["shortname"] = core_df["shortname"].str.strip()
core_df["rating"] = core_df["rating"].str.strip()

# Build a mapping: shortname -> rating
shortname_to_rating = dict(zip(core_df["shortname"], core_df["rating"]))

# Load XML
tree = ET.parse("dblp.xml")  # replace with your XML file path
root = tree.getroot()

# Initialize counters
count_A = 0
count_A_star = 0
matches = []

# Iterate over <r> elements
for r in root.findall("r"):
    inproc = r.find("inproceedings")
    if inproc is not None:
        year_tag = inproc.find("year")
        booktitle_tag = inproc.find("booktitle")
        if year_tag is not None and booktitle_tag is not None:
            year = int(year_tag.text)
            if year >= 2015:
                booktitle = booktitle_tag.text.strip()
                if booktitle in shortname_to_rating:
                    rating = shortname_to_rating[booktitle]
                    matches.append({
                        "booktitle": booktitle,
                        "year": year,
                        "rating": rating
                    })
                    # Count based on rating
                    if rating == "A":
                        count_A += 1
                    elif rating == "A*":
                        count_A_star += 1

# Convert matches to DataFrame for inspection
matches_df = pd.DataFrame(matches)
print("Matched entries:")
print(matches_df)

# Output aggregate counts
print("\nAggregate counts:")
print(f"A*: {count_A_star}")
print(f"A: {count_A}")
print(f"Total matched: {len(matches_df)}")

