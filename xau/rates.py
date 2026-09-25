"""US interest rates, cached from FRED in data/fred/.

Refresh with:
  curl -s 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF' -o data/fred/DFF.csv
"""
from pathlib import Path

import pandas as pd

FRED_DIR = Path(__file__).resolve().parent.parent / "data" / "fred"


def fed_funds():
    """Daily effective Fed funds rate in percent (FRED series DFF)."""
    df = pd.read_csv(FRED_DIR / "DFF.csv", parse_dates=["observation_date"])
    return df.set_index("observation_date").DFF
