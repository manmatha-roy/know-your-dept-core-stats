#!/usr/bin/env python3
import os
import subprocess
from glob import glob

# Directory containing faculty CSV files
faculty_dir = "facultydb"
csv_files = glob(os.path.join(faculty_dir, "*.csv"))

# Path to the aggregation script
agg_script = "script/gen_agg_auth_stat.py"

if not os.path.isfile(agg_script):
    print(f"❌ Aggregation script '{agg_script}' not found.")
    exit(1)

# Run the aggregation script for each CSV file
for csv_file in csv_files:
    print(f"➡ Processing {csv_file}")
    subprocess.run(
        ["python3", agg_script, csv_file, "--since", "2015"],
        check=True
    )

print("\n✅ All faculty CSV files processed successfully.")

