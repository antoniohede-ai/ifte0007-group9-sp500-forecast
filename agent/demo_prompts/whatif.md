Context: this is a classroom demonstration for UCL module IFTE0007 group coursework. The agent checks an academic forecast of the S&P 500 index built from frozen historical data. Nothing is traded and nothing here is investment advice.

Live what-if on the forecast, chosen by the presenter: $ARGUMENTS
$BOUNDARY Never change the forecast record. Run each command exactly as written, from the current folder (do not cd).
This is a sensitivity check, not a refit.

1. One line starting "Expect:": what you expect to happen to the forecast and why, with a rough size in points. Do this before running anything.
2. Run `python code/demo_tools.py $MODE fetch` for fresh data, then `python code/demo_tools.py $MODE whatif $ARGUMENTS`.
3. One line "Found:" (the change in points), one "Expectation:" (right or wrong, and why), one "Decision:" (does this change the recommendation?). Each under 25 words. No tables, no headings, no bold.
