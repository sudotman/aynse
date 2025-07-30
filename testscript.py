from datetime import date
from aynse import nse
from aynse.nse import expiry_dates

expiries = expiry_dates(date(2024, 7, 1), "RELIANCE")
print(expiries)

bhavcopy_raw = nse.bhavcopy_raw(date(2023, 3, 1), as_dataframe=True)
nse.bhavcopy_save(date(2023, 3, 1), dest=".", skip_if_present=False)

print(bhavcopy_raw.head(10))

# Dump the entire bhavcopy to a CSV file
# bhavcopy_raw.to_csv("bhavcopy_2023_03_01.csv", index=False)
