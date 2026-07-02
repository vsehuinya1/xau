# Negative Findings Log
Run: smoke_2022

All hypotheses that were tested and did NOT produce actionable findings.
Prevents re-testing known dead ends.

---

## D11 — NEGATIVE
**Hypothesis:** Forward return distributions at multiple horizons differ materially across regimes (session × weekday × ATR-pct tercile × prior direction). No thresholds. This is the universal prior for all future research.
**Sample:** 354,568  **Stability:** 0.50

- Asian 15m mean return: effect=-0.0%  CI=[-0.0%, 0.0%]  p=0.000  → **Ignore**
- Asian 60m mean return: effect=-0.0%  CI=[-0.0%, -0.0%]  p=0.000  → **Ignore**
- Asian 4h mean return: effect=-0.0%  CI=[-0.0%, -0.0%]  p=0.000  → **Ignore**
- London 15m mean return: effect=+0.0%  CI=[0.0%, 0.0%]  p=0.000  → **Ignore**
- London 60m mean return: effect=+0.0%  CI=[0.0%, 0.0%]  p=0.000  → **Ignore**
- London 4h mean return: effect=+0.0%  CI=[0.0%, 0.0%]  p=0.000  → **Ignore**
- NY 15m mean return: effect=+0.0%  CI=[-0.0%, 0.0%]  p=0.000  → **Ignore**
- NY 60m mean return: effect=+0.0%  CI=[0.0%, 0.0%]  p=0.000  → **Ignore**
- NY 4h mean return: effect=+0.0%  CI=[0.0%, 0.0%]  p=0.000  → **Ignore**

## D01 — NEGATIVE
**Hypothesis:** Sessions have materially different directional efficiency and continuation rates; this is the primary driver of WF instability.
**Sample:** 774  **Stability:** 0.50

- Asian→London continuation: effect=+2.3%  CI=[45.7%, 58.1%]  p=0.812  → **Ignore**
- Asian→London cont (high DE prior): effect=-4.3%  CI=[34.7%, 57.3%]  p=1.000  → **Ignore**
- London→NY continuation: effect=-3.5%  CI=[39.9%, 51.9%]  p=0.636  → **Ignore**
- London→NY cont (high DE prior): effect=+14.8%  CI=[46.8%, 72.6%]  p=1.000  → **Monitor**
- Asian→NY continuation: effect=+1.6%  CI=[45.0%, 57.0%]  p=0.613  → **Ignore**
- Asian→NY cont (high DE prior): effect=-4.9%  CI=[34.7%, 57.3%]  p=1.000  → **Ignore**
