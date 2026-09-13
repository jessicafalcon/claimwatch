# Screenshots

The demonstration screenshot lives here, captured over `ROWS=synthetic` (the
compose file's environment) so every table the run built holds hand-written fake
reviews — **synthetic fixture data — not a study finding**. The Airflow grid shows
task names and states only; no review text, no address and no host path can
appear in it.

Capturing it is a developer step (it needs Docker and a running Airflow, which
CI does not have) — see [`../DEMONSTRATION.md`](../DEMONSTRATION.md) for the walk.
