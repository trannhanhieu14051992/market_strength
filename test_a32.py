# test_a32.py - kiểm tra file data_hist/A32.csv
import pandas as pd
p = 'data_hist/A32.csv'
print("Checking file:", p)
try:
    df = pd.read_csv(p)
    print("Rows:", len(df))
    print("Columns:", df.columns.tolist())
    print("--- first 8 rows ---")
    print(df.head(8).to_string(index=False))
except Exception as e:
    print("Error reading file:", e)
