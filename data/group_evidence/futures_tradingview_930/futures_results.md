ES1! hourly bars 2023-01-02 18:00 to 2026-11-10 11:00 ET, 22786 bars. S&P closes to 2026-10-30.
Origins with a usable gap g: 930 weekdays (188 Fridays), 2023-01-04 to 2026-10-22. Dropped: {'no futures price': 10, 'roll window': 15}. Roll Tuesdays excluded: ['2023-03-14', '2023-06-13', '2023-09-12', '2023-12-12', '2024-03-12', '2024-06-18', '2024-09-17', '2024-12-17', '2025-03-18', '2025-06-17', '2025-09-16', '2025-12-16', '2026-03-17', '2026-06-16', '2026-09-15']

== PRIMARY: Friday origins: n=188, unseen part from 2025-08-15 (n=57) ==
forecast                                              MAE all MAE unseen score all t vs A1 all t vs A1 unseen
A0 S&P(p), no change                                   1.6071     1.4715    42.023       -1.80          -0.37
A1 S&P(p) x exp(drift)  [current model w/o Asia]       1.5579     1.4546    42.280         nan            nan
B0 S&P(p) x exp(g)                                     1.5974     1.3805    42.069       -1.17           1.34
B1 S&P(p) x exp(g + drift)                             1.5358     1.3584    42.388        0.88           2.35
B2 S&P(p) x exp(g + 5/6 drift)                         1.5423     1.3549    42.354        0.63           2.49
B3 S&P(p) x exp(0.5 g + drift)                         1.5338     1.3997    42.400        1.94           2.67
B4 S&P(p) x exp(0.75 g + drift)                        1.5314     1.3761    42.411        1.42           2.53

== SECONDARY: every weekday origin: n=930, unseen part from 2025-09-03 (n=279) ==
forecast                                              MAE all MAE unseen score all t vs A1 all t vs A1 unseen
A0 S&P(p), no change                                   1.6174     1.4403    41.940       -2.62          -0.61
A1 S&P(p) x exp(drift)  [current model w/o Asia]       1.5700     1.4195    42.184         nan            nan
B0 S&P(p) x exp(g)                                     1.5858     1.3845    42.094       -0.75           0.90
B1 S&P(p) x exp(g + drift)                             1.5399     1.3722    42.329        2.04           1.78
B2 S&P(p) x exp(g + 5/6 drift)                         1.5436     1.3689    42.310        1.81           1.93
B3 S&P(p) x exp(0.5 g + drift)                         1.5462     1.3868    42.299        3.12           2.45
B4 S&P(p) x exp(0.75 g + drift)                        1.5407     1.3761    42.325        2.60           2.16

Gap g (ES 16:00 to next 07:00 New York, log):
  std 0.0050, mean |g| 0.0033 (all weekdays); Fridays std 0.0043, mean |g| 0.0031
  6-day return minus drift regressed on g, all weekdays: slope 0.92 (NW se 0.16), R2 0.047
  same, Fridays only: slope 0.71 (se 0.29), R2 0.022
  correlation of g with asia_overnight (Friday origins) +0.35; all weekdays +0.34

Marks per 0.1 pp of error = 0.5 (brief): A1 -> B1 difference in mean error (Friday origins): +0.0221 pp = +0.110 marks.