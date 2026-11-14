# Falling-power baseline duel (2026-11-06)

Question: on the CORE cycling workbook, does a forecaster that sees heart rate, skin
temperature, environment and ergometer watts beat elapsed time alone, specifically on
periods where power fell but core temperature kept rising?

Script: `scripts/falling_power_duel.py` (run against the original Figshare workbook,
MD5 `01214bfc835215fe1a5d3f5da1e9ad52`). Leave-one-person-out over all 24 people.
Horizons +5/+10/+15 min. "Falling" = current power is >=10 W below the max power in
the previous 10 minutes. "Steady" = power varies <10 W over the prior 10 and next 15 min.

## Counts

| | value |
|---|---:|
| people | 24 |
| people with any power change | 16 |
| people with a qualifying falling episode | 14 |
| eligible cutoffs | 860 |
| falling episodes | 148 |
| steady control episodes | 513 |
| falling episodes where core rose over the next 15 min | 97% |
| mean core rise over 15 min after a power fall | +0.30 °C |

## MAE at +15 min (°C), direction accuracy in brackets

| model | all | falling | steady |
|---|---:|---:|---:|
| elapsed-time ridge | 0.247 (0.95) | 0.249 (0.92) | 0.253 (0.94) |
| wearable ridge | 0.328 (0.95) | 0.297 (0.92) | 0.353 (0.94) |
| wearable + watts ridge | 0.346 (0.95) | 0.304 (0.92) | 0.380 (0.94) |
| wearable GBM | 0.323 (0.90) | 0.339 (0.92) | 0.323 (0.88) |
| wearable + watts GBM | 0.327 (0.92) | 0.326 (0.91) | 0.349 (0.90) |

Direction = forecast at +15 higher than forecast at +5, compared with the measured pair.

## Reading

1. Elapsed time wins everywhere, including on falling-power episodes. With 24 people
   on one constant-load protocol, core temperature is close to a function of minutes
   elapsed; wearable channels add variance, not signal.
2. Adding watts neither helps nor hurts materially. No fitted model predicts a
   temperature drop after a power fall (bias at +15 is positive for all of them).
3. Therefore "falling power, rising temperature" is not a discriminating test for an
   AI-built *fitted* model on this dataset. Any model that uses time gets the
   direction right by construction. The shortcut was caught before spending on
   frontier runs.
4. Subject 1, cutoff 40 -> 55: measured 38.90 °C; elapsed 38.71; wearable models
   38.97 to 39.13. Nobody forecasts a fall.

The open experiment is whether a frontier model reasoning directly from the frozen
history (no fitting) forecasts a fall when told watts dropped. That requires API
calls and has not been run.
