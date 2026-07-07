# Negative Findings Log
Run: full_2018_2025

All hypotheses that were tested and did NOT produce actionable findings.
Prevents re-testing known dead ends.

---

## D07 — NEGATIVE
**Hypothesis:** M15 range breakouts sustain (no close back below breakout level within 5 bars) with probability P that is materially context-dependent.
**Sample:** 29,213  **Stability:** 0.83

- M15 breakout sustainability (Asian): effect=-0.3%  CI=[38.8%, 41.1%]  p=0.486  → **Ignore**
- M15 breakout sustainability (London): effect=+1.8%  CI=[41.0%, 43.2%]  p=0.000  → **Ignore**
- M15 breakout sustainability (NY): effect=-3.4%  CI=[35.9%, 38.7%]  p=0.000  → **Ignore**

## D08 — NEGATIVE
**Hypothesis:** The daily high and low form at non-uniform UTC hours. P(daily extreme not yet formed | current hour) gives a session-based reversal probability surface that is actionable for timing entries.
**Sample:** 2,489  **Stability:** 0.74

- Day high forms in London session: effect=+7.4%  CI=[26.4%, 30.0%]  p=1.000  → **Ignore**
- Day low forms in London session: effect=+9.1%  CI=[28.1%, 31.6%]  p=1.000  → **Ignore**
- Day high forms in NY session: effect=-9.0%  CI=[10.6%, 13.2%]  p=1.000  → **Ignore**

## D10 — NEGATIVE
**Hypothesis:** Day-of-week has measurable and stable effects on XAUUSD range, directional persistence, and session continuation rates.
**Sample:** 2,488  **Stability:** 0.51

- Mon daily range: effect=+122.9%  CI=[2443.0%, 2888.7%]  p=0.002  → **Monitor**
- Tue daily range: effect=+234.8%  CI=[2567.7%, 3071.8%]  p=0.002  → **Monitor**
- Wed daily range: effect=+270.4%  CI=[2623.3%, 3014.9%]  p=0.002  → **Monitor**
- Thu daily range: effect=+278.6%  CI=[2632.3%, 3012.4%]  p=0.002  → **Monitor**
- Fri daily range: effect=+137.4%  CI=[2493.3%, 2897.6%]  p=0.002  → **Monitor**
