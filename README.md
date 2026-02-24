# EDsim: An LLM-Powered Emergency Department Simulation Using Generative Agents

EDsim is a multi-agent simulation of emergency department (ED) workflows driven by large language model (LLM)-powered autonomous agents. Each agent (doctors, nurses, patients) perceives its environment, makes decisions through cognitive modules, and interacts with other agents in real time, producing realistic ED dynamics suitable for operational analysis and research.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Agent Roles](#agent-roles)
3. [Prerequisites & Installation](#prerequisites--installation)
4. [Running the Simulation](#running-the-simulation)
5. [Configuration](#configuration)
6. [Data Collection](#data-collection)
7. [Acknowledgments](#acknowledgments)
8. [Citation](#citation)
9. [License](#license)

## Architecture Overview

EDsim consists of three main components:

### Backend Simulation Engine (`reverie/`)

The core engine that drives agent behavior. Each agent is equipped with cognitive modules that mirror the generative agents architecture:

- **Plan** — generates and revises daily and immediate action plans
- **Perceive** — observes nearby agents, objects, and events in the ED environment
- **Reflect** — synthesizes observations into higher-level insights stored in memory
- **Converse** — initiates and participates in natural-language conversations with other agents
- **Execute** — translates planned actions into simulation state changes (movement, tests, discharge)

Agent personas, memory streams, and spatial awareness are managed within the `persona/` sub-package.

### Frontend Visualization Server (`environment/`)

A Django-based web application that renders the ED floor plan and provides a browser-based interface for replaying and inspecting simulation runs. Agents and patients are visualized on a tile-based map that reflects the physical layout of the ED.

### Analysis Pipeline (`analysis/`)

Post-simulation scripts that compute operational metrics from the simulation output, including patient throughput, time-in-state distributions, and CTAS-stratified performance summaries.

## Agent Roles

- **Doctor** — Assesses patients, orders diagnostic tests, and discharges patients. Spawns in the major injuries zone.
- **Bedside Nurse** — Transfers patients between rooms and performs tests. Spawns in the minor injuries zone.
- **Triage Nurse** — Assigns a CTAS score and injury zone to incoming patients. Spawns in the triage zone.
- **Patient** — Arrives with symptoms, interacts with staff, and follows the simulation flow. Spawns at the ED entrance.

## Prerequisites & Installation

1. Install [Conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html).

2. Clone this repository:

   ```bash
   git clone <repo-url> EDsim
   cd EDsim
   ```

3. Create and activate the Conda environment:

   ```bash
   conda create --name simulacra python=3.9.12
   conda activate simulacra
   ```

4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Create `openai_config.json` in the repository root with your API credentials. The file supports both OpenAI and Azure OpenAI backends.

   **OpenAI example:**

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

   **Azure OpenAI example:**

   ```json
   {
     "client": "azure",
     "model": "gpt-35-turbo-0125",
     "model-key": "your-azure-key",
     "model-endpoint": "https://your-resource.openai.azure.com/",
     "model-api-version": "2024-02-01",
     "embeddings-client": "azure",
     "embeddings-model": "text-embedding-ada-002",
     "embeddings-key": "your-azure-embeddings-key",
     "embeddings-endpoint": "https://your-resource.openai.azure.com/",
     "embeddings-api-version": "2024-02-01"
   }
   ```

   This file is listed in `.gitignore` and will not be committed.

## Running the Simulation

There are two ways to run EDsim: **interactive mode** (with the frontend visualization) and **batch mode** (headless, using `run_simulation.py`).

---

### Option A: Interactive Mode (Frontend + Backend)

This mode lets you watch the simulation in real time through a browser-based visualization.

#### Step 1 — Start the Frontend Server

Open a terminal and run:

```bash
cd environment/frontend_server
python manage.py runserver 8000
```

Open [http://localhost:8000/](http://localhost:8000/) in your browser. You should see the message "Your environment server is up and running."

#### Step 2 — Start the Backend Server

In a **separate** terminal:

```bash
conda activate simulacra
cd reverie/backend_server
python reverie.py
```

This will launch the simulation and automatically open a Firefox browser tab. The virtual map is available at [http://localhost:8000/simulator_home](http://localhost:8000/simulator_home).

Once the server starts you will see an interactive prompt. Type `run <steps>` to advance the simulation by a number of steps (e.g., `run 1000`), and type `fin` to save and exit.

#### Command-Line Arguments for `reverie.py`

| Argument           | Description                                                              | Default           |
| ------------------ | ------------------------------------------------------------------------ | ----------------- |
| `--origin`         | Source folder from which the simulation is initialized.                  | `ed_sim_n5`       |
| `--target`         | Folder where the simulation output is saved.                             | `test-simulation` |
| `--browser`        | Automatically open a Firefox browser tab (`yes` or `no`).               | `yes`             |
| `--frontend_ui`    | Use the frontend UI for simulation control (`yes` or `no`).             | `no`              |
| `--headless`       | Run in headless mode, skipping frontend file I/O for faster runs (`yes` or `no`). | `no`     |
| `--write_movement` | Write `movement/{step}.json` each step for replay (`yes` or `no`).      | `yes`             |

Example:

```bash
python reverie.py --target=final-test --origin=ed_sim_n5 --browser=no
```

---

### Option B: Batch / Headless Mode (`run_simulation.py`)

For long unattended runs (e.g., 48 simulated hours) use the automated runner. This script repeatedly launches `reverie.py` in headless mode, auto-saves progress, and retries on failure with exponential backoff.

**No frontend server is needed for this mode.**

#### Step 1 — Prepare the starting simulation

Make sure a valid simulation folder exists at `environment/frontend_server/storage/curr_sim/`. This is the seed the runner will fork from on each chunk. The default origin (`ed_sim_n5`) can be copied:

```bash
cp -r environment/frontend_server/storage/ed_sim_n5 environment/frontend_server/storage/curr_sim
```

#### Step 2 — Run the batch script

```bash
conda activate simulacra
cd reverie/backend_server
python run_simulation.py
```

#### How it works

1. Reads `sec_per_step` from `curr_sim/reverie/meta.json` and computes the total number of steps needed for the configured hours.
2. Runs the simulation in chunks (default 1000 steps per chunk). After each successful chunk it saves the result to `curr_sim/`.
3. If a chunk fails, the partial output is discarded and the chunk is retried with exponential backoff (1 min, 2 min, 5 min). After 5 consecutive failures the script stops.
4. Errors are logged to `error_log_run_simulation_safe-mode.txt`.

#### Configurable variables (edit at the top of `run_simulation.py`)

| Variable          | Description                                                                 | Default    |
| ----------------- | --------------------------------------------------------------------------- | ---------- |
| `hours_to_run`    | How many simulated hours to run.                                            | `48`       |
| `steps_per_save`  | Number of steps per chunk before saving.                                    | `1000`     |
| `write_movement`  | Write movement files each step (`True`/`False`). Disable for faster runs.   | `True`     |

---

### Troubleshooting

- **OpenAI library version** — Make sure the OpenAI package is up to date:

  ```bash
  pip install --upgrade openai
  ```

- **`cost_logger.py` JSON error** — Locate `openai_cost_logger.py` in your Conda environment's `site-packages/` and change the time format from `xx:xx:xx` to `xx-xx-xx`.

## Configuration

### meta.json

Before launching `reverie.py`, adjust simulation parameters by editing `<origin_folder>/meta/meta.json`:

| Key                                         | Description                                                                      |
| ------------------------------------------- | -------------------------------------------------------------------------------- |
| `start_date`                                | Date the simulation starts.                                                      |
| `curr_time`                                 | Start datetime of the simulation.                                                |
| `sec_per_step`                              | Seconds of simulation time per step.                                             |
| `maze_name`                                 | Name of the map layout used.                                                     |
| `persona_names`                             | List of personas available at simulation start.                                  |
| `{role}_starting_amount`                    | Number of agents of a given role at start (e.g., `doctor_starting_amount`).      |
| `patient_rate_modifier`                     | Adjusts patient arrival rate (e.g., `0.5` = half the default rate).              |
| `priority_factor`                           | Factor for prioritizing patients by CTAS score.                                  |
| `testing_time`                              | Duration of diagnostic tests (minutes).                                          |
| `testing_result_time`                       | Time for diagnostic results to return (minutes).                                 |
| `patient_walkout_probability`               | Probability (0--1) that a waiting patient leaves the ED.                         |
| `patient_walkout_check_minutes`             | Minutes between walk-out evaluations for a patient in the same state.            |
| `patient_post_discharge_linger_probability` | Probability (0--1) that a discharged patient remains in their bed space.         |
| `patient_post_discharge_linger_minutes`     | Minutes a lingering patient stays before heading to the exit (0 = indefinitely). |

Walk-out and post-discharge lingering events are logged per patient in `data_collection.json` under the keys `left_department_by_choice` and `lingered_after_discharge`.

### maze_status.json

| Field               | Description                                                                   |
| ------------------- | ----------------------------------------------------------------------------- |
| `change_bed_amount` | Areas that will have their bed counts changed in the next simulation.         |
| `remove_beds`       | Number of beds to remove from the injuries area.                              |

### Adjusting the Map Layout

You can modify or create maps using the [Tiled](https://www.mapeditor.org/) map editor:

1. Open the existing map file in Tiled (from the simulation folder or `static_dirs/assets/visuals`).
2. Edit or create a new layout, keeping the same tile conventions for spawning locations, sectors, arenas, and object interaction layers.
3. Save the map file in `static_dirs/assets/visuals`.
4. Update `maze_name` in `meta/meta.json` to match the new filename.
5. Start a new simulation from the source folder to apply changes.

## Data Collection

### Patient Fields

| Field                         | Description                                                                   |
| ----------------------------- | ----------------------------------------------------------------------------- |
| `ICD-10-CA_code`              | Diagnosis assigned at patient creation.                                       |
| `CTAS_score`                  | Score assigned by the Triage Nurse (0 = unassigned).                          |
| `Injuries_zone`               | Zone assigned by the Triage Nurse.                                            |
| `Time_spent_state`            | Time spent in each state (minutes).                                           |
| `Time_spent_area`             | Time spent in each area (minutes).                                            |
| `Exempt_from_data_collection` | Whether the patient is excluded from final data (e.g., added via unseen actions). |

### Summarized by CTAS Score

Each CTAS category contains:

| Field                                                     | Description                                            |
| --------------------------------------------------------- | ------------------------------------------------------ |
| `Num_of_patients`                                         | Total patients with this score.                        |
| `Percentage_of_total`                                     | Percentage of all patients with this score.            |
| `Total`                                                   | Total time spent (all patients) in states and areas.   |
| `Normalized`                                              | Average time per patient in states and areas.          |
| `Standard Deviation`                                      | Standard deviation for time in states and areas.       |
| `Minor injuries zone / Major injuries zone / Trauma room` | Counts of patients in each zone or room.               |

Patient times in both area and state are also exported as separate CSV files alongside CTAS scores for easy visualization.

## Acknowledgments

EDsim builds on the **Generative Agents** framework by Park et al. (Stanford/Google):

> Joon Sung Park, Joseph C. O'Brien, Carrie J. Cai, Meredith Ringel Morris, Percy Liang, and Michael S. Bernstein. 2023. *Generative Agents: Interactive Simulacra of Human Behavior.* In Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology (UIST '23). ACM.
> 

## Citation

If you use EDsim in your research, please cite:

```bibtex
@article{edsim2025,
  title   = {EDSim: An Agentic Simulator for Emergency Department Operations},
  author  = {TODO},
  journal = {TODO},
  year    = {TODO}
}
```

## License

This project is released under the [MIT License](LICENSE).
