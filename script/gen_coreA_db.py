import pandas as pd

# Load CSV safely, forcing comma as separator and trimming spaces
df = pd.read_csv("core_fulldb.csv", sep=",", skipinitialspace=True, engine="python")

def matches_a_or_a_star(value):
    if pd.isna(value):
        return False
    s = str(value).strip()
    return s == "A" or s == "A*"

# Filter where 5th column (index 4) is exactly "a" or "a*"
filtered_df = df[df.iloc[:, 4].apply(matches_a_or_a_star)]

# Select only columns 2, 3, and 5 (indices 1, 2, 4)
output_df = filtered_df.iloc[:, [1, 2, 4]]

# Save filtered results
output_df.to_csv("core_onlyA.csv", index=False)

print(f"Filtered {len(output_df)} rows and saved to core_onlyA.csv")

