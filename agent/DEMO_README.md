# Agent demo: how to run it

The demo shows the research agent (Claude Code) checking the frozen forecast in real time: its plan, the tools it chooses, what each tool returns, its reasoning, and its recommendation. A group member then signs off.

## Start

From an **unzipped copy** of this package (not the submission folder):

```
python code/demo_ui.py
```

Then open http://127.0.0.1:8765. It needs only the Python standard library plus the packages in the package README.

## What runs where

| Mode | Needs | What happens |
|---|---|---|
| **Replay** | Nothing (no internet, no AI account) | Plays a saved run from `agent/demo_runs/` with its original timing. Every card is tagged *Recorded* |
| **Live: /check** | Claude Code signed in (`claude`, then `/login`) | The agent writes its own plan, chooses up to four tools and recommends whether to submit |
| **Live: Fault drill** | Same | The page copies the package to a temporary folder and plants **one hidden error** in the copy's `forecast_record.json`. The error, chosen at random, is one of: the forecast shifted 12-40 points; the last close shifted 3-15 points; or the cutoff moved to 13:45 UTC. Nobody is told which until the agent finishes. The real record is never touched |
| **Live: Ask** | Same | Type any question. The agent chooses its own tools and what-if values (at most three calls) |
| **Live: What if** | Same | The presenter picks a change; the agent predicts the effect, tests it and explains |

The agent's tools are in `code/demo_tools.py`:
- `record`, `recompute`, `check`;
- `data spx|es`;
- `explain <drift|futures|overnight|cutoff|forecast|check>`;
- `whatif <change>`, with any drift, futures read time, overnight clock or close.

The prompts are in `agent/demo_prompts/`. Each live run is saved to `agent/demo_runs/`.

## Boundary (enforced by Claude Code's permission settings)

- **Allowed:** `python code/demo_tools.py ...`, reading files, and read-only commands such as `ls` and `cat`.
- **Refused:** writing or editing files, network commands, any other program. The web search and fetch tools are switched off.

The forecast record is never changed.

## Timing and models (measured 11 Nov 2026 on the preview snapshot)

- **Sonnet 5.5:** `/check` takes about 30 s; a fault drill 30-45 s.
- **Opus 5.5:** an Ask takes about 26-28 s; `/check` about 47 s.
- Each run costs a few cents on a Claude subscription.
- The model menu's **Auto** setting uses Sonnet for `/check`, drills and what-ifs, and Opus for Ask, because Sonnet's safety filter blocked two ordinary Ask questions. If any run is blocked, choose Opus and run it again.
