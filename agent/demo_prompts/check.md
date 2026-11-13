Context: this is a classroom demonstration for UCL module IFTE0007 group coursework. The agent checks an academic forecast of the S&P 500 index built from frozen historical data. Nothing is traded and nothing here is investment advice.

$GOAL
The brief's rules: every input must be available by the information cutoff, 12:00 UTC (07:00 New York) on the cutoff day; the calculation must be reproducible from the saved inputs; the forecast in the record is the one that is marked.
$BOUNDARY Never change the forecast record. Run each command exactly as written, from the current folder (do not cd).

Your tools (each takes a few seconds):
$FETCHLINES
- `python code/demo_tools.py $MODE record`: which record and data, what the cutoff removed, the brief's cutoff rule
- `python code/demo_tools.py $MODE recompute`: a separate recalculation, MATCH or DIFFERS for each number
$CHECKLINE
- `python code/demo_tools.py $MODE data spx` or `data es`: the raw observations either side of the cutoff
- `python code/demo_tools.py $MODE explain <drift|futures|overnight|cutoff|forecast|check>`: how a number is defined and where in the code
- `python code/demo_tools.py $MODE whatif <change> [<change> ...]` with changes such as drift=mean, drift=median:2010, drift=0.3%, drift=none, futures=none, futures=06:30, overnight=07:00, close=7560.25
- reading files in this folder.

A good check establishes three things: which record and data are being checked and that nothing after the cutoff was used (or, in Full mode, exactly what came after it); that the forecast can be reproduced independently; and whether anything looks wrong, and what it would mean. You decide how to establish them.
Start with one line "Plan:" naming the tools you will use, in order, and why. Begin with `fetch` so the data is fresh. Use at most five tool calls. Change your plan if a result surprises you, and say so.
Narrate for an audience. Before each tool call write one line starting "Checking:" (what and why). If you expect a particular result, first write "Expect:" with a rough number. After each call write "Found:" (the key number), then "Expectation:" if you made one (right or wrong), then "Decision:" (what you will do next and why). If anything does not match, say what it could mean before you decide. Each line under 25 words. No tables, no headings, no bold.
$FINISH
