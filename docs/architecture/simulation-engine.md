# Simulation Engine

The simulation engine lives under `reverie/backend_server/` and drives the agent-based ED simulation.

## Per-step cognitive loop

Each step in `ReverieServer`:

1. **Perceive** — agents observe nearby agents, objects, and events within `vision_r` tiles.
2. **Retrieve** — relevant memories are fetched from associative memory using embedding similarity + recency weighting.
3. **Plan** — the LLM generates or revises the agent's schedule and immediate next action.
4. **Execute** — the planned action updates tile position and object state.
5. **Converse** — agents in proximity may initiate LLM-driven conversations.
6. **Reflect** — periodically synthesises memories into higher-level insights.

## Agent types

| Role | Behaviour | Spawn zone |
|---|---|---|
| **Doctor** | Assesses patients, orders diagnostic tests, discharges | Major injuries |
| **Bedside Nurse** | Transfers patients between rooms, performs tests | Minor injuries |
| **Triage Nurse** | Assigns CTAS score and injury zone to incoming patients | Triage |
| **Patient** | Arrives with symptoms, interacts with staff | ED entrance |

## LLM integration

`gpt_structure.py` reads `openai_config.json` at import time and constructs the OpenAI/Azure client. All LLM calls go through `run_gpt_prompt.py`, which selects the appropriate prompt template from `persona/prompt_template/ED/`. Transient API errors (429, 500–503) are retried with exponential backoff.

## Configuration (`meta.json`)

Key parameters in `<sim_folder>/reverie/meta.json`:

| Key | Description |
|---|---|
| `sec_per_step` | Simulation seconds per step |
| `patient_rate_modifier` | Scales patient arrival rate |
| `{role}_starting_amount` | Number of agents per role at start |
| `patient_walkout_probability` | Probability a waiting patient leaves |
| `testing_time` / `testing_result_time` | Diagnostic test durations (minutes) |
| `priority_factor` | CTAS score prioritisation weight |
