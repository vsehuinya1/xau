# H16: Two enhancements to dollar-shock momentum

**Status:** PRE-REGISTERED 2026-10-09. The user said "work with the dollar".
Nothing had been run before this file was committed. In particular, the
gold-confirmation split had never been looked at on 2009–2017.

**Baseline:** the live strategy (H11): EURUSD and USDJPY both ≥ 3 ATR in 5
minutes in the dollar direction, then gold against the dollar for 30 minutes.

## T1: a broad six-currency dollar shock

- **Pairs:** EURUSD, GBPUSD and AUDUSD (dollar-z = −z) and USDJPY, USDCAD and
  USDCHF (dollar-z = +z). Each z is the 5-minute move divided by M5 ATR(14),
  using the same code as the baseline.
- **Dollar-up shock:** at an M1 close where all six pairs have bars, at least
  4 of the 6 have dollar-z ≥ 3 and none has dollar-z ≤ −1. Dollar-down is the
  mirror.
- **Reason:** a genuine US-dollar shock moves the dollar against most
  currencies at once. Two pairs can be fooled by single-currency news, such as
  a yen-only move.

## T2: the baseline, only when gold has already followed

- **Filter:** take a baseline trade only if gold's 5-minute move at the shock
  minute is at least 1 ATR(M5) in the implied direction.
- **Reason:** H08's 2018–25 diagnostics showed much larger continuation when
  gold had already followed (news momentum). That was found in-sample, so it
  is judged on **2009–2017 only**, where the split has never been examined.

## Shared rules and costs

- **Trading rules:** gold against the dollar, entering at the next M1 open
  within 5 minutes and exiting 30 minutes later. A 30-minute cooldown, and one
  position at a time.
- **Costs:** the base cost plus H11's news-heavy add-on (+$0.80 for entries
  08:30–08:45 New York, +$0.10 otherwise). The base cost is $0.51 flat on
  histdata and the entry spread plus $0.11 on Pepperstone.

## Pass criteria

- **T1:** in **both** histdata 2009–2017 and Pepperstone 2018 to Sep 2025,
  mean net > 0 with t ≥ 2 (clustered by day). Its mean net per trade must also
  be at least the baseline's on the same sample.
- **T2:** on histdata 2009–2017, mean net > 0 with t ≥ 2, and at least the
  baseline's mean net per trade on 2009–2017. 2018–25 is reported but not
  judged, because the idea came from it.

## Trial count

2, so the running total becomes 45.
