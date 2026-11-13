# Speaker script and Q&A (final build)

5 slides, 7 minutes talking and 3 minutes of questions. Every member presents their own part; timings are in brackets. Slide 6 is used at the start of the questions for the live agent demo (about 1 to 2 minutes); it adds to the recorded run on slide 4.

## Slide 1
[Layla Ahmed - 0:50] One number: the S&P 500 official close on Fri 20 Nov, scored against S&P Dow Jones Indices, from information available at Fri 13 Nov 12:00 UTC (07:00 New York). Forecast 7,637.84, 80% interval 7,406 to 7,817. Three clocks: the last official close (Thu 12 Nov, 7,592.40), the cutoff, where we read the overnight futures move (+0.25%), and the target 6 trading sessions later. Nothing after the cutoff can enter: a leak test corrupted 29 later values and the inputs did not change.  Hand over to Antonio Herrera Despradel.

## Slide 2
[Antonio Herrera Despradel - 1:40] What predicts a six-session S&P move? We tested 16 factors with economic signs fixed in advance: yields, the dollar, gold, semiconductors, surprises, inflation, trend, reversal and VIX. Each had to beat median drift out of sample, with a Diebold-Mariano t of at least 1.65 and support from 2000-2012 history. None passed: the best, 2Y yield 20-day change (t 1.53), is contradicted by history. The group's 30 pre-registered tests and the 1.72-million-combination search agree. Drift itself is only a weak edge over 'no change' (t 0.53). The one input that adds information is the overnight futures move: in my pre-registered test on Bloomberg 07:00 prices it cut six-day error from 1.389% to 1.307% (133 origins, t 2.50; Thursdays t 3.49), and Jayen's 930-origin test shows it carries through almost one for one (slope 0.92). Hand over to Jayen Rughani.

## Slide 3
[Jayen Rughani - 1:30] The calculation: 7,592.40 x exp(+0.40% + +0.20%) = 7,637.84. Drift: the median 6-session return since 1990, the equity risk premium; it fails in prolonged bear markets. Futures: E-mini futures trade nearly 24 hours, so they price overnight news; the move from 7,616.25 to 7,635.50 (+0.25%), less the average overnight drift, gives +0.20%. It fails on a contract roll, thin overnight trading or a reversal at the open. Sensitivity: the drift choice barely matters; dropping the nowcast moves the forecast to 7,623. The 80% interval scales the historical error distribution by today's VIX. No hand adjustment. Hand over to Layla Ahmed.

## Slide 4
[Layla Ahmed - 1:50] AGENT DEMO (about 90 seconds): in `python code/demo_ui.py` (unzipped copy of the package), Replay the agent's saved /check on the final record (agent/demo_runs/; run it live only if time allows). The agent writes its own plan, chooses its tools (record, recompute, check), reads each result and recommends: point at its Plan line, one tool call and its Found, Decision and Recommendation lines. Then the transcript on this slide is the pipeline it checked: `python code/run_all.py --final` on the frozen inputs. Walk the flow: the group set the goal and boundary; the agent fetched the data with fingerprints and applied the cutoff filter; it called Python to screen factors, fit the median regression and run the backtests; it applied rules fixed in advance and logged every decision; a second code path and a leak test checked it; we approve and sign. Point at the transcript: the command, the frozen-model line and PASS_ALL. Two logged corrections: three faulty Yahoo prices replaced after a three-source check, and the model frozen after group review. Hand over to Mohamed Derbala.

## Slide 5
[Mohamed Derbala - 1:10] What could invalidate it. Rehearsal (cutoff Fri 30 Oct, target Fri 6 Nov): forecast 7,663.45 against a realised 7,376.86, error 3.88% against 4.66% for unchanged, in a week with a 4.4% one-day fall: a tail event no factor anticipated. History: the worst test error was 14.6% on 20 Feb 2020, a shock that no change missed just as badly. Adverse scenario: a further chip rout (index -4%, VIX 30) puts the level at 7,324, 4.1% below the forecast; the interval's lower end is 3.0% below. Counterargument: 'an analyst would use the news'. We tested its measurable parts and none beat drift; the rest is already in the futures price. My momentum + RSI machine-learning model was also worse than drift over 22 years. Watch list: a failed independent check, a futures roll, the last close against S&P DJI, Nvidia on 17 Nov, FOMC minutes on 18 Nov. We claim a well-centred, reproducible forecast with honest evidence, not foresight. Questions: everyone answers on their own part (see the speaker script). At the start of the questions, Jayen Rughani opens slide 6 and runs the agent live (about 1 to 2 minutes).

## Slide 6 (Q&A: live agent demo)
[Jayen Rughani - Q&A, about 1 to 2 minutes] LIVE AGENT DEMO, in addition to the recorded run on slide 4. Start `python code/demo_ui.py` in an unzipped copy of the package before the talk and open http://127.0.0.1:8765. 1) Press Run /check: the agent writes its own plan, chooses its tools (typically a recalculation and the independent check), reads each result and recommends; point at its Plan line, a tool call and its Found and Decision lines (about 30 seconds). 2) Press Fault drill: the page plants one error in a temporary copy of the record (forecast, last close or cutoff, at random); nobody knows which. Ask the room to watch whether the agent catches it; the page reveals the error at the end (about 40 seconds). 3) If time allows, type a question from the audience into Ask: the agent picks its own tools and what-if values (about 30 seconds). Say what is live and what is fixed: the data, the tools' code and the rules are fixed; the plan, the tool choices, the numbers it computes, its words and its verdict happen live. In rehearsal on the frozen inputs it caught 3 of 3 planted errors (cutoff, forecast, last close). If the connection fails, switch to Replay and play a saved run: the brief allows a recorded walkthrough. The agent cannot write files or change the record; a member signs.

## Likely questions (who answers)
**You tested many factors. Why is none in the model? (Antonio)**
We fixed a rule before looking: a factor must beat median drift out of sample (t at least 1.65, supported by 2000-2012 history, or 2.33 without it). The best t was 1.53, and history contradicted it. With 16 tests, one false positive at 1.65 is expected by chance.

**What role did the group's supporting dataset play? (Antonio)**
A helper: it supplied extra macro candidates for the factor screen (2Y, 10Y, USD, gold, semiconductors, surprise index, CPI, PPI) and a tie-breaker when Yahoo and Cboe disagreed. It is not an input to the forecast, which uses public data only.

**How does the latest news affect the forecast? (Jayen)**
Through prices: the futures price at the cutoff already reflects everything known by then (CPI, Fed speakers, earnings). We add no hand adjustment because it could not be validated. Scheduled events after the cutoff widen the interval.

**Why median regression and median drift? (Jayen)**
The score is linear in absolute percentage error, and the optimal point forecast under absolute error is the median (Gneiting 2011).

**How do you know there is no future information? (Layla)**
A cutoff filter in code plus a test that corrupts every value published after the cutoff; the inputs did not change. Raw files are fingerprinted with SHA-256.

**What did the agent do versus you? (Layla)**
Agent: retrieve, filter, calculate, screen, validate, research news, draft, self-check, log. Humans: set the goal and boundary, review, check the S&P DJI close, approve the record.

**Why is the model frozen? (Layla)**
So the submitted method is exactly the one the group reviewed. A factor that passed the screen on submission day would enter untested; instead the screen is reported and cannot change the forecast.

**Did a machine-learning model do better? (Mohamed)**
Momentum + RSI was worse than drift over 1,096 Thursdays in 2002-24 (t -3.15) and only tied on recent data, so it is a robustness note, not the model.

**What would change the forecast? (Mohamed)**
A different last close or overnight futures move. Dropping the nowcast would move it to 7,622.86 (-15.0 points); dropping the drift to 7,607.31 (-30.5 points).

**Is the live agent just running a script? (Jayen)**
No. In /check it writes its own plan and chooses which tools to call and in what order; in Ask it also chooses the what-if values. Every number is computed by Python at that moment from the frozen files, and in the fault drill it is not told what was planted. What is fixed: the data, the tools' code, the goal and the brief's rules.

**What if the live demo fails? (Jayen)**
We switch to Replay and play a saved run of the same agent on the same frozen inputs; the brief allows a recorded walkthrough. Slide 4's recorded pipeline run also stands on its own.

**Can the agent change the forecast? (Jayen)**
No. It can read files and run code/demo_tools.py only; writing files, network commands and other programs are refused. It recommends; a member signs the record.
