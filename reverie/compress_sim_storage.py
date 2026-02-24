from __future__ import annotations

import argparse
import datetime as _dt
import json
import shutil
from pathlib import Path
from typing import Dict, Tuple


def _get_frontend_root() -> Path:
    return Path(__file__).resolve().parent.parent / 'environment' / 'frontend_server'


def _load_movements(move_folder: Path) -> Tuple[Dict[str, Dict[str, dict]], int]:
    step_files = sorted(move_folder.glob('*.json'), key=lambda p: int(p.stem))
    if not step_files:
        raise FileNotFoundError(f'No movement steps found under {move_folder}')

    master_move: Dict[str, Dict[str, dict]] = {}
    persona_last_move: Dict[str, dict] = {}

    for move_path in step_files:
        step = int(move_path.stem)
        with move_path.open('r', encoding='utf-8') as fh:
            step_payload = json.load(fh)["persona"]

        step_out: Dict[str, dict] = {}
        for persona, payload in step_payload.items():
            cached = persona_last_move.get(persona)
            if cached != payload:
                step_out[persona] = json.loads(json.dumps(payload))
                persona_last_move[persona] = step_out[persona]

        master_move[str(step)] = step_out

    last_step = int(step_files[-1].stem)
    return master_move, last_step


def _normalise_meta(meta_path: Path, last_step: int) -> dict:
    with meta_path.open('r', encoding='utf-8') as fh:
        meta = json.load(fh)

    sec_per_step = meta.get('sec_per_step', 30)
    step_count = meta.get('step')
    if not step_count:
        step_count = last_step
    curr_time = _dt.datetime.strptime(meta['curr_time'], "%B %d, %Y, %H:%M:%S")
    fixed_time = curr_time - _dt.timedelta(seconds=sec_per_step * step_count)
    meta['step'] = step_count
    meta['curr_time'] = fixed_time.strftime("%B %d, %Y, %H:%M:%S")
    return meta


def _safe_copy(src: Path, dest: Path, *, optional: bool = False) -> None:
    if not src.exists():
        if optional:
            return
        raise FileNotFoundError(f'Missing required file: {src}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)


def compress(sim_code: str) -> None:
    frontend_root = _get_frontend_root()
    sim_storage = frontend_root / 'storage' / sim_code
    if not sim_storage.exists():
        raise FileNotFoundError(f'Simulation storage not found for {sim_code!r} at {sim_storage}')

    compressed_storage = frontend_root / 'compressed_storage' / sim_code
    if compressed_storage.exists():
        shutil.rmtree(compressed_storage)
    compressed_storage.mkdir(parents=True, exist_ok=True)

    move_folder = sim_storage / 'movement'
    master_move, last_step = _load_movements(move_folder)

    with (compressed_storage / 'master_movement.json').open('w', encoding='utf-8') as fh:
        json.dump(master_move, fh, indent=2)

    meta = _normalise_meta(sim_storage / 'reverie' / 'meta.json', last_step)
    with (compressed_storage / 'meta.json').open('w', encoding='utf-8') as fh:
        json.dump(meta, fh, indent=2)

    persona_folder = sim_storage / 'personas'
    if persona_folder.exists():
        shutil.copytree(persona_folder, compressed_storage / 'personas', dirs_exist_ok=True)

    _safe_copy(sim_storage / 'environment' / '0.json', compressed_storage / 'starting_pos.json')
    _safe_copy(sim_storage / 'reverie' / 'data_collection.json', compressed_storage / 'data_collection.json')
    _safe_copy(sim_storage / 'reverie' / 'maze_visuals.json', compressed_storage / 'maze_visuals.json')
    _safe_copy(sim_storage / 'reverie' / 'state_times.csv', compressed_storage / 'state_times.csv', optional=True)
    _safe_copy(sim_storage / 'reverie' / 'area_times.csv', compressed_storage / 'area_times.csv', optional=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reverie Server')
    parser.add_argument('--compress', type=str, default='test-simulation', help='The name of the simulation you want compressed')
    args = parser.parse_args()
    compress(args.compress)
    print('Compress Done.')
