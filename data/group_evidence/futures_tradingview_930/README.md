# ES futures anchor test (branch `exp/es-futures`)

- `PREREG.md`: written and committed before the first result.
- `run_futures.py`: pre-registered test (07:00 New York ES level vs the previous S&P close). Output: `results/futures_results.md`, `results/origin_errors.csv`.
- `compare_asia.py`: POST-HOC follow-up against the group model (median drift + 0.5 x asia_overnight). Output: `results/compare_asia.md`.
- `data/ES1_60min_TradingView_20261110.csv`: NOT IN THE REPO (licensed CME data via TradingView). TradingView ES1! hourly export, 22,786 bars, 2 Jan 2023 to 10 Nov 2026, New York time, sha256 c71a874cffe1de9ed2dd9b4caa1f4b30f673e2a46b46a07f666ee87fb72a8696. Jayen holds it; to rerun, place it at that path.
  The bar count in PREREG.md (22,785) was a miscount made before the test; the file has 22,786 rows.

Licence note: the CME data is kept out of this repo (ignored by git). `results/origin_errors.csv` holds only derived per-day gaps and errors. Rerun: `python futures/run_futures.py` from `drift-asia/`.

Contract rolls: ES1! is not back-adjusted. The 18:00 Monday reopen of expiry week carries a 0.8-1.2% roll jump, so the 15 Tuesday origins whose
gap window contains it are excluded. No Friday origin is affected.
