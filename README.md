# btc-cent-forecast-01 — wallet w1: EWMA-drift forecaster

Forecasts Bitcoin's price 240 minutes after each checkpoint from the
4,320 one-minute closes in the case (`main.py`, Python 3.13, standard
library only, no network, deterministic).

## Approach

1. **Log-returns** `r_t = ln(p_t / p_{t-1})` over the whole series.
2. **EWMA drift** of the log-returns with halflife 240 minutes
   (`alpha = 1 - 0.5 ** (1/240)`), seeded with the mean of the first
   240 returns so one noisy minute cannot tilt the estimate.
3. **Extrapolation:** raw 240-minute drift = EWMA × 240, shrunk
   **0.5 toward 0** — a raw trend extrapolation is halved as a
   mean-reversion guard (4-hour BTC moves are mostly noise).
4. **Volatility clamp:** the total log-shift is clamped to
   **±3 × (mean absolute 1-minute log-return over the last 60
   minutes)**, so the forecast can only move as far as recent
   volatility justifies.
5. `forecast = last_close × exp(clamped drift)`, kept on the grid's
   5 decimals and inside (0, 10,000,000).

**Fallback:** fewer than 100 prices → persistence (last close).

## Why this should beat persistence

The house baseline (persistence) scores 44521.576667 cents MAE on
practice. A 4-hour move is dominated by drift that persists over
hours plus noise; the EWMA captures the slow drift while the 0.5
shrink and the ±3× recent-volatility clamp keep the guess from
chasing noise. When the market is flat or trendless, the forecast
stays close to the checkpoint close, so the worst case is near
persistence; when a real drift is running, it follows it part-way.

## Files

- `main.py` — entrypoint: reads every `*.in` in `$MAKEFUN_INPUT_DIR`
  (else `/input/`), writes one `<id>.out` per case to
  `$MAKEFUN_OUTPUT_DIR` (else `/output/`).
- `LICENSE` — MIT (from the kit's starter).

## Local test

```sh
mkdir -p /tmp/btc-w1-out
MAKEFUN_INPUT_DIR=<kit>/input MAKEFUN_OUTPUT_DIR=/tmp/btc-w1-out \
  python3 main.py
```

All 6 practice cases (p00–p05) produce valid outputs; see the build
report for the practice MAE from `grade-local`.
