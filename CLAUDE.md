# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EDsim is an LLM-powered multi-agent simulation of emergency department (ED) workflows. It builds on the [Generative Agents](https://arxiv.org/abs/2304.03442) framework (Park et al., 2023). Four agent types — Doctor, Bedside Nurse, Triage Nurse, and Patient — perceive their environment, plan actions, converse with each other, and execute behaviors driven by LLM calls.

## Environment Setup

```bash
conda create --name simulacra python=3.9.12
conda activate simulacra
pip install -r requirements.txt
```

Create `openai_config.json` at the repo root (gitignored). Supports OpenAI or Azure OpenAI:

```json
{
  "client": "openai",
  "model": "gpt-3.5-turbo",
  "model-key": "sk-...",
  "embeddings-client": "openai",
  "embeddings-model": "text-embedding-ada-002",
  "embeddings-key": "sk-..."
}
```

## Running the Simulation

### Interactive mode (frontend + backend)

Terminal 1 — frontend:
```bash
cd environment/frontend_server
python manage.py runserver 8000
```

Terminal 2 — backend:
```bash
conda activate simulacra
cd reverie/backend_server
python reverie.py --origin ed_sim_n5 --target my-run --browser no
```

At the interactive prompt: `run <steps>` to advance, `fin` to save and exit.

### Headless batch mode (no frontend needed)

```bash
cp -r environment/frontend_server/storage/ed_sim_n5 environment/frontend_server/storage/curr_sim
conda activate simulacra
cd reverie/backend_server
python run_simulation.py
```

Edit `hours_to_run`, `steps_per_save`, and `write_movement` at the top of [reverie/backend_server/run_simulation.py](reverie/backend_server/run_simulation.py).

### Automated execution (alternative headless runner)

```bash
cd reverie/backend_server
python automatic_execution.py --origin ed_sim_n5 --target my-run --steps 8640
```

## Key `reverie.py` Arguments

| Argument | Default | Description |
|---|---|---|
| `--origin` | `ed_sim_n5` | Simulation folder to fork from |
| `--target` | `test-simulation` | Output folder name |
| `--browser` | `yes` | Auto-open Firefox (`yes`/`no`) |
| `--headless` | `no` | Skip frontend file I/O for speed |
| `--write_movement` | `yes` | Write `movement/{step}.json` per step for replay |

## Post-Simulation Analysis

```bash
cd analysis
python compute_metrics.py --sim <sim_folder_name>
# or: python compute_metrics.py --sim auto   (uses latest run)
```

Outputs: `analysis/patient_time_metrics.csv` and `analysis/ctas_daily_metrics.csv`.

## Architecture

### Component Layout

```
reverie/backend_server/     # Simulation engine
  reverie.py                # ReverieServer class — main simulation loop
  run_simulation.py         # Batch runner with chunked saves and retry logic
  automatic_execution.py    # Alternative CLI runner
  maze.py                   # Tile-based map and spatial state
  utils.py                  # Path constants (fs_storage, fs_temp_storage, etc.)
  wait_time_utils.py        # CTAS-based patient wait time sampling
  persona/
    persona.py              # Base Persona class
    persona_types/          # Doctor, BedsideNurse, TriageNurse, Patient subclasses
    cognitive_modules/      # perceive, plan, reflect, converse, execute, retrieve
    memory_structures/
      scratch.py            # Short-term working memory (Scratch class)
      scratch_types/        # Role-specific scratch subclasses
      associative_memory.py # Long-term memory with embeddings + recency weighting
      spatial_memory.py     # Agent's knowledge of the map
    prompt_template/
      gpt_structure.py      # OpenAI/Azure client setup and LLM call wrappers
      run_gpt_prompt.py     # Prompt dispatchers for each cognitive module
      ED/v1/, v2/, v3_ChatGPT/   # Versioned prompt templates per role

environment/frontend_server/ # Django visualization server
  translator/views.py       # API endpoints consumed by the JS frontend
  storage/                  # Simulation state folders (created at runtime)
  static_dirs/assets/the_ed/ # Map matrix CSVs and Tiled JSON map files

analysis/
  compute_metrics.py        # Post-run metrics (patient throughput, wait times)

data/
  baseline/, surge/         # Pre-computed reference metrics CSVs
```

### Simulation State Storage

All simulation state lives under `environment/frontend_server/storage/<sim_name>/`. Each simulation folder contains:
- `reverie/meta.json` — simulation parameters (see Configuration section)
- `reverie/maze_status.json` — bed count overrides
- `environment/` — per-step movement and environment JSON files
- `personas/<name>/` — agent memory (scratch JSON, associative memory nodes/embeddings)

The seed simulation (`ed_sim_n5`) is included in the repo. Every run forks from an existing simulation folder.

### LLM Integration

`gpt_structure.py` reads `openai_config.json` at import time and constructs the OpenAI/Azure client. All LLM calls go through `run_gpt_prompt.py`, which selects the appropriate `.txt` prompt template from `persona/prompt_template/ED/`. Transient API errors (429, 500-503) are retried with exponential backoff (60s → 120s → 300s).

API call costs are tracked via `openai-cost-logger`. If you see a JSON parse error from `openai_cost_logger.py`, change the time format in its `site-packages` source from `xx:xx:xx` to `xx-xx-xx`.

### Per-Step Simulation Loop

Each step in `ReverieServer`:
1. **Perceive** — agents observe nearby agents, objects, and events within `vision_r` tiles
2. **Retrieve** — relevant memories are fetched from associative memory
3. **Plan** — LLM generates/revises schedule and immediate next action
4. **Execute** — planned action updates tile position and object state
5. **Converse** — agents in proximity may initiate LLM-driven conversations
6. **Reflect** — periodically synthesizes memories into higher-level insights

### Configuration (`meta.json`)

Key parameters in `<sim_folder>/reverie/meta.json`:

| Key | Description |
|---|---|
| `sec_per_step` | Simulation seconds per step (used to compute total steps) |
| `patient_rate_modifier` | Scales patient arrival rate (0.5 = half rate) |
| `{role}_starting_amount` | Number of agents per role at start |
| `patient_walkout_probability` | Probability a waiting patient leaves |
| `testing_time` / `testing_result_time` | Diagnostic test durations (minutes) |
| `priority_factor` | CTAS score prioritization weight |
