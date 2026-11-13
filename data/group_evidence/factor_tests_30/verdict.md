SELECTION WINDOW ONLY (origins before 2025-01-01); 2025-26 is excluded from every rule here.

Rules: sign matches registry; |t| vs drift >= 3.1; expected sign and positive gain in every available sub-period (>= 52 origins); placebo p < 0.05. Shrink 0.5, no cap.

                   candidate expected_sign      n   slope sign_ok  gain_vs_drift  t_vs_drift  t_ok sub_ok  placebo_p placebo_ok              verdict                                                                       note
                   vix_level     ambiguous 1163.0 -0.0001   False        -0.0052     -1.0766 False  False     0.9760      False                 FAIL first scored origin 2002-01-31; ambiguous sign: unstable, fails sign check
                     mom_20d             + 1159.0  0.0052    True        -0.0037     -2.3565 False  False     0.9281      False                 FAIL                                             first scored origin 2002-02-28
                      rev_5d             - 1162.0 -0.0393    True        -0.0068     -2.6202 False  False     0.9960      False                 FAIL                                             first scored origin 2002-02-07
                      d2y_5d             - 1162.0 -0.0056    True        -0.0010     -0.4323 False  False     0.4930      False                 FAIL                                             first scored origin 2002-02-07
                     d10y_5d             - 1162.0 -0.0137    True        -0.0001     -0.0234 False  False     0.2156      False                 FAIL                                             first scored origin 2002-02-07
                 slope_10y2y             + 1163.0 -0.0005   False        -0.0012     -0.5363 False  False     0.5090      False                 FAIL                                             first scored origin 2002-01-31
             vix_vix3m_ratio             +  671.0  0.0083    True        -0.0041     -1.7724 False  False     0.9242      False                 FAIL                                             first scored origin 2011-10-13
            hy_spread_chg_5d             -    NaN     NaN     NaN            NaN         NaN   NaN    NaN        NaN        NaN INSUFFICIENT HISTORY                                                   no selection-window data
fed_path_proxy_2y_dff_chg_5d             - 1162.0 -0.0089    True        -0.0004     -0.3121 False  False     0.2735      False                 FAIL                                             first scored origin 2002-02-07
   breadth_proxy_rsp_spy_20d             +  990.0  0.0327    True        -0.0030     -1.0967 False  False     0.9122      False                 FAIL                                             first scored origin 2005-07-07
           eps_revisions_fwd             +    NaN     NaN     NaN            NaN         NaN   NaN    NaN        NaN        NaN INSUFFICIENT HISTORY                                                 bloomberg-pending, no data
                true_breadth             +    NaN     NaN     NaN            NaN         NaN   NaN    NaN        NaN        NaN INSUFFICIENT HISTORY                                                 bloomberg-pending, no data
            implied_fed_path             -    NaN     NaN     NaN            NaN         NaN   NaN    NaN        NaN        NaN INSUFFICIENT HISTORY                                                 bloomberg-pending, no data
              futures_0700ny             +    NaN     NaN     NaN            NaN         NaN   NaN    NaN        NaN        NaN INSUFFICIENT HISTORY                                                 bloomberg-pending, no data
          risk_premium_score             +  620.0  0.0002    True        -0.0042     -1.7338 False  False     0.9381      False                 FAIL                                             first scored origin 2012-10-11
           rate_shock_regime             + 1151.0 -0.0578   False        -0.0007     -0.4506 False  False     0.3713      False                 FAIL                                             first scored origin 2002-04-25
               credit_spread             -    NaN     NaN     NaN            NaN         NaN   NaN    NaN        NaN        NaN INSUFFICIENT HISTORY                                                 bloomberg-pending, no data
        eps_revision_breadth             +    NaN     NaN     NaN            NaN         NaN   NaN    NaN        NaN        NaN INSUFFICIENT HISTORY                                                 bloomberg-pending, no data
              asia_overnight             + 1096.0  0.2178    True         0.0064      1.3231 False  False     0.0020       True                 FAIL                                             first scored origin 2003-05-29

Sub-periods:
  vix_level: 2003-09: slope -0.0032, gain -0.025; 2010-19: slope +0.0034, gain +0.003; 2020-24: slope +0.003, gain -0.001
  mom_20d: 2003-09: slope +0.011, gain -0.002; 2010-19: slope -0.017, gain -0.001; 2020-24: slope -0.00043, gain -0.001
  rev_5d: 2003-09: slope -0.054, gain -0.005; 2010-19: slope -0.072, gain -0.002; 2020-24: slope -0.027, gain -0.008
  d2y_5d: 2003-09: slope -0.02, gain +0.007; 2010-19: slope -0.0071, gain -0.003; 2020-24: slope +0.0075, gain -0.003
  d10y_5d: 2003-09: slope -0.031, gain +0.009; 2010-19: slope +0.0013, gain -0.006; 2020-24: slope -0.0067, gain +0.001
  slope_10y2y: 2003-09: slope +0.00041, gain +0.004; 2010-19: slope -0.0013, gain +0.000; 2020-24: slope +0.0017, gain -0.004
  vix_vix3m_ratio: 2010-19: slope +0.025, gain -0.004; 2020-24: slope -0.018, gain -0.004
  fed_path_proxy_2y_dff_chg_5d: 2003-09: slope -0.018, gain +0.003; 2010-19: slope +0.0019, gain -0.002; 2020-24: slope -7.8e-05, gain -0.002
  breadth_proxy_rsp_spy_20d: 2003-09: slope +0.18, gain -0.000; 2010-19: slope +0.049, gain -0.002; 2020-24: slope -0.066, gain -0.007
  risk_premium_score: 2010-19: slope +0.0029, gain -0.005; 2020-24: slope -0.0028, gain -0.004
  rate_shock_regime: 2003-09: slope +0.045, gain -0.004; 2010-19: slope -0.0037, gain +0.000; 2020-24: slope -0.26, gain +0.002
  asia_overnight: 2003-09: slope +0.19, gain +0.010; 2010-19: slope +0.36, gain +0.013; 2020-24: slope +0.085, gain -0.010

## Bloomberg factors (3 Nov 2026, budget 26-30 of 30, hurdle 3.14)
All 5 fail: europe_gap t 0.37, eps_rev_20d -0.03, hy_oas_5d -0.13, bill6m_5d -2.04 (worse than drift), breadth_50d 0.26. europe_gap correlates 0.45 with asia_overnight. Budget fully used; no further factor tests. See results/bbg_factors.txt.
