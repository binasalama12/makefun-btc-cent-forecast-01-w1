#!/usr/bin/env python3
"""btc-cent-forecast-01, wallet w1: EWMA-drift forecaster.

Forecasts BTC's price 240 minutes after the checkpoint from the 4,320
one-minute closes in the case.

Method
------
1. Log-returns r_t = ln(p_t / p_{t-1}) over the whole series.
2. EWMA of the log-returns with halflife 240 minutes
   (alpha = 1 - 0.5 ** (1 / 240)), seeded with the mean of the first
   240 returns, so recent drift weighs most.
3. Raw 240-minute drift = EWMA * 240, shrunk 0.5 toward 0
   (mean-reversion guard: a raw trend extrapolation is halved).
4. Clamp the total log-shift to +/-3 * (mean absolute 1-minute
   log-return over the last 60 minutes) -- the recent volatility
   caps how far the forecast may move from the checkpoint close.
5. forecast = last_close * exp(clamped drift), kept on the grid's
   5 decimals and inside (0, 10,000,000).

Fallback: fewer than 100 prices -> persistence (last close).

Python 3.13, standard library only, no network, fully deterministic.
Reads $MAKEFUN_INPUT_DIR (else /input/), writes $MAKEFUN_OUTPUT_DIR
(else /output/); one <id>.out per <id>.in, in name order.
"""

import json
import math
import os
from pathlib import Path

MIN_PRICE = 0.00001
MAX_PRICE = 9_999_999.99999
HORIZON_MINUTES = 240
HALFLIFE_MINUTES = 240
SHRINK = 0.5
CLAMP_MULT = 3.0
VOL_WINDOW = 60
MIN_PRICES = 100


def price5(x: float) -> float:
    """Keep x on the grid's 5 decimals and inside (0, 10,000,000)."""
    return round(min(MAX_PRICE, max(MIN_PRICE, x)) * 1e5) / 1e5


def forecast(prices) -> float:
    """EWMA-drift forecast from a list of closes (last = checkpoint)."""
    if not prices:
        raise ValueError("market has no prices")
    last = float(prices[-1])
    if not math.isfinite(last) or last <= 0:
        raise ValueError("last price is not a finite positive number")
    if len(prices) < MIN_PRICES:
        return price5(last)

    # Log-returns, skipping any non-positive / non-finite price defensively
    # (an invalid price never becomes the base of the next return).
    rets = []
    prev = None
    for p in prices:
        p = float(p)
        if math.isfinite(p) and p > 0:
            if prev is not None:
                rets.append(math.log(p / prev))
            prev = p
    if len(rets) < MIN_PRICES - 1:
        return price5(last)

    # EWMA of log-returns, halflife 240 minutes. Seed it with the mean of
    # the first 240 returns (one halflife of burn-in) instead of a single
    # return, so one noisy first minute cannot tilt the whole estimate.
    alpha = 1.0 - 0.5 ** (1.0 / HALFLIFE_MINUTES)
    seed_n = min(HALFLIFE_MINUTES, len(rets))
    ewma = sum(rets[:seed_n]) / seed_n
    for r in rets[seed_n:]:
        ewma += alpha * (r - ewma)

    # 240-minute drift, shrunk halfway toward zero.
    drift = ewma * HORIZON_MINUTES * SHRINK

    # Recent volatility: mean absolute 1-minute log-return, last 60 min.
    recent = rets[-VOL_WINDOW:]
    vol = sum(abs(r) for r in recent) / len(recent)
    cap = CLAMP_MULT * vol
    if drift > cap:
        drift = cap
    elif drift < -cap:
        drift = -cap

    return price5(last * math.exp(drift))


def main() -> None:
    input_dir = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
    output_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(os.listdir(input_dir)):
        if not name.endswith(".in"):
            continue
        case_id = name[: -len(".in")]
        with open(input_dir / name, "r", encoding="utf-8") as fh:
            case = json.load(fh)
        markets = case.get("markets")
        if not isinstance(markets, list) or len(markets) != 1:
            raise ValueError(f"{name} does not hold exactly one market")
        price = forecast(markets[0]["prices"])
        out = {"forecasts": [{"case": case_id, "price": price}]}
        with open(output_dir / f"{case_id}.out", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(out) + "\n")


if __name__ == "__main__":
    main()
