"""The deterministic models (PROJECT_BRIEF.md §7): the cost model
(`cost_model.py`) and the guardrail simulator (`guardrail_sim.py`).

Plain arithmetic over parameters on a slider — no fitted predictive model, no
random draw, no clock, no key. The layer is handed the DAMIR fit (it reads no
file) and computes; the caller writes the results to the Beat 3 and Beat 4
marts."""
