from datetime import date
from aynse import nse
from aynse.nse import expiry_dates

expiries = expiry_dates(date(2024, 4, 16), "RELIANCE")
print(expiries)


# Dump the entire bhavcopy to a CSV file
# bhavcopy_raw.to_csv("bhavcopy_2023_03_01.csv", index=False)
