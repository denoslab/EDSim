import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_ROOT = REPO_ROOT / 'environment' / 'frontend_server'
REVERIE_ROOT = REPO_ROOT / 'reverie'

OUTPUT_PATIENT = REPO_ROOT / 'analysis' / 'patient_time_metrics.csv'
OUTPUT_CTAS = REPO_ROOT / 'analysis' / 'ctas_daily_metrics.csv'

PATIENT_COLUMNS = [
    'patient',
    'ctas_level',
    'arrival_step',
    'arrival_time',
    'pia_step',
    'pia_time',
    'disposition_step',
    'disposition_time',
    'leave_step',
    'leave_time',
    'wait_minutes',
    'treatment_minutes',
    'total_ed_minutes'
]

def resolve_sim_code(raw_value: str) -> str:
    """Resolve which simulation folder to load."""
    if raw_value.lower() not in {'auto', 'latest'}:
        return raw_value

    curr_sim_path = FRONTEND_ROOT / 'temp_storage' / 'curr_sim_code.json'
    if curr_sim_path.exists():
        with curr_sim_path.open('r', encoding='utf-8') as fh:
            sim_code = json.load(fh).get('sim_code')
        if sim_code:
            return sim_code
    return '12hrs'


def ensure_compressed(sim_code: str) -> None:
    """Make sure the compressed snapshot exists for the requested simulation."""
    compressed_root = FRONTEND_ROOT / 'compressed_storage' / sim_code
    master_file = compressed_root / 'master_movement.json'
    if master_file.exists():
        return

    storage_root = FRONTEND_ROOT / 'storage' / sim_code
    if not storage_root.exists():
        raise FileNotFoundError(f'No stored simulation named {sim_code!r} at {storage_root}')

    command = [sys.executable, 'compress_sim_storage.py', '--compress', sim_code]
    result = subprocess.run(
        command,
        cwd=REVERIE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        details = stderr or stdout or 'unknown error'
        raise RuntimeError(f'Failed to compress simulation {sim_code!r}: {details}')

    if not master_file.exists():
        raise FileNotFoundError(f'Compression for {sim_code!r} completed but {master_file} is missing')


def load_inputs(sim_code: str):
    """Load raw movement, patient metadata, and sim meta for a given simulation folder."""
    data_root = FRONTEND_ROOT / 'compressed_storage' / sim_code
    master_movement = data_root / 'master_movement.json'
    data_collection = data_root / 'data_collection.json'
    meta_file = data_root / 'meta.json'
    if not master_movement.exists():
        raise FileNotFoundError(f"Missing master_movement.json under {data_root}")
    if not data_collection.exists():
        raise FileNotFoundError(f"Missing data_collection.json under {data_root}")
    if not meta_file.exists():
        raise FileNotFoundError(f"Missing meta.json under {data_root}")
    with master_movement.open() as f:
        raw = json.load(f)
    with data_collection.open() as f:
        patient_data = json.load(f)["Patient"]
    with meta_file.open() as f:
        meta = json.load(f)
    return raw, patient_data, meta


def parse_args():
    parser = argparse.ArgumentParser(description='Compute per-patient and CTAS metrics from a compressed simulation export.')
    parser.add_argument('--sim', default='auto', help='Simulation folder name or "auto" for the most recent run (default: auto).')
    return parser.parse_args()


args = parse_args()
sim_code = resolve_sim_code(args.sim)
ensure_compressed(sim_code)
raw_movement, patient_collection, meta = load_inputs(sim_code)

sec_per_step = meta.get('sec_per_step', 30)
minutes_per_step = sec_per_step / 60.0
start_time = datetime.strptime(meta['curr_time'], "%B %d, %Y, %H:%M:%S")

# Build step data per patient
patient_steps: dict[str, list[tuple[int, dict]]] = defaultdict(list)
for step_str, snapshot in raw_movement.items():
    step = int(step_str)
    for name, payload in snapshot.items():
        if not name.lower().startswith('patient'):
            continue
        patient_steps[name].append((step, payload))

# Sort steps for each patient
for name in patient_steps:
    patient_steps[name].sort(key=lambda item: item[0])

def find_pia_step(entries):
    for step, payload in entries:
        chat = payload.get('chat')
        if not chat:
            continue
        if any('doctor' in speaker.lower() for speaker, _ in chat):
            return step
    return None

def find_disposition_step(entries):
    for step, payload in entries:
        desc = (payload.get('description') or '').lower()
        if 'exit' in desc or 'leaving' in desc:
            return step
    return None

def step_to_time(step_index: int) -> datetime:
    return start_time + timedelta(seconds=sec_per_step * step_index)

records = []
for name, series in patient_steps.items():
    info = patient_collection.get(name)
    if not info:
        continue
    ctas = info.get('CTAS_score')
    if ctas in (None, 0):
        continue
    if info.get('exempt_from_data_collection'):
        continue

    arrival_step = series[0][0]
    last_step = series[-1][0]
    pia_step = find_pia_step(series)
    dispo_step = find_disposition_step(series)

    # compute derived steps for leaving
    leave_step = last_step + 1

    arrival_time = step_to_time(arrival_step)
    leave_time = step_to_time(leave_step)
    pia_time = step_to_time(pia_step) if pia_step is not None else None
    dispo_time = step_to_time(dispo_step) if dispo_step is not None else None

    # Timeline checks to print statements in the case of unusual data.
    if pia_time and pia_time < arrival_time:
        print(f"[Data Check] {name} skipped: PIA recorded before arrival")
        continue
    if dispo_time and pia_time and dispo_time < pia_time:
        print(f"[Data Check] {name} skipped: disposition recorded before PIA")
        continue
    if leave_time < arrival_time:
        print(f"[Data Check] {name} skipped: patient left before arrival")
        continue

    wait_minutes = None
    treatment_minutes = None
    total_minutes = (leave_step - arrival_step) * minutes_per_step

    if total_minutes < 0:
        print(f"[Warning] {name} skipped: negative total time")
        continue

    if pia_step is not None:
        wait_minutes = (pia_step - arrival_step) * minutes_per_step
        if wait_minutes < 0:
            print(f"[Warning] {name} skipped: negative wait time")
            continue

        if dispo_step is not None and dispo_step >= pia_step:
            treatment_minutes = (dispo_step - pia_step) * minutes_per_step
            if treatment_minutes < 0:
                print(f"[Warning] {name} skipped: negative treatment time")
                continue

    # Only add record if no validation failed
    records.append({
        'patient': name,
        'ctas_level': ctas,
        'arrival_step': arrival_step,
        'arrival_time': arrival_time.isoformat(sep=' '),
        'pia_step': pia_step,
        'pia_time': pia_time.isoformat(sep=' ') if pia_time else None,
        'disposition_step': dispo_step,
        'disposition_time': dispo_time.isoformat(sep=' ') if dispo_time else None,
        'leave_step': leave_step,
        'leave_time': leave_time.isoformat(sep=' '),
        'wait_minutes': wait_minutes,
        'treatment_minutes': treatment_minutes,
        'total_ed_minutes': total_minutes
    })

patient_df = pd.DataFrame(records, columns=PATIENT_COLUMNS)
if not patient_df.empty:
    patient_df.sort_values(['ctas_level', 'arrival_step', 'patient'], inplace=True)
patient_df.to_csv(OUTPUT_PATIENT, index=False)

if not patient_df.empty:
    patient_df['date'] = pd.to_datetime(patient_df['arrival_time']).dt.date
    agg_frames = []
    for (date, ctas), group in patient_df.groupby(['date', 'ctas_level']):
        # Pre-drop NA values once per column to avoid repeated scans
        valid_wait = group['wait_minutes'].dropna()
        valid_treat = group['treatment_minutes'].dropna()
        valid_total = group['total_ed_minutes'].dropna()

        metrics = {
            'date': date.isoformat(),
            'ctas_level': ctas,
            'patients': int(group.shape[0]),
            'avg_wait_minutes': float(valid_wait.mean()) if not valid_wait.empty else None,
            'median_wait_minutes': float(valid_wait.median()) if not valid_wait.empty else None,
            'avg_treatment_minutes': float(valid_treat.mean()) if not valid_treat.empty else None,
            'median_treatment_minutes': float(valid_treat.median()) if not valid_treat.empty else None,
            'avg_total_ed_minutes': float(valid_total.mean()) if not valid_total.empty else None,
            'median_total_ed_minutes': float(valid_total.median()) if not valid_total.empty else None
        }
        agg_frames.append(metrics)


    ctas_df = pd.DataFrame(agg_frames)
    ctas_df.sort_values(['date', 'ctas_level'], inplace=True)
    ctas_df.to_csv(OUTPUT_CTAS, index=False)
else:
    OUTPUT_CTAS.write_text('')

print(f'Using simulation data from "{sim_code}"')
print(f'Wrote per-patient metrics to {OUTPUT_PATIENT}')
print(f'Wrote CTAS aggregates to {OUTPUT_CTAS}')
