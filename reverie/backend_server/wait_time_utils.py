"""
Utilities for CTAS-based wait times and assigning staged wait targets.

Extracted from reverie.py to keep the main simulation file smaller
and easier to maintain.
"""

import json
import math
import random
import datetime
import pathlib


def _load_ctas_wait_config():
    """
    Load CTAS wait-time configuration from data/ctas_wait_distributions.json.

    Returns a dict keyed by CTAS string -> stage_key -> config dict.
    """
    cfg_path = pathlib.Path(__file__).parent / "data" / "ctas_wait_distributions.json"
    if cfg_path.exists():
        try:
            with open(cfg_path) as f:
                return json.load(f)
        except Exception as e:
            print(f"(reverie): Failed to load CTAS wait config, defaulting to empty: {e}")
    return {}


def _sample_wait_minutes(ctas_wait_config, ctas_score, stage_key, surge_multiplier=1.0):
    """
    Return a sampled wait duration in minutes given a CTAS score and stage.

    Supports two distribution types based on the JSON config keys:

    1. Truncated lognormal (keys: mu, sigma, low, high)
       Used for Stage 1, Stage 2, and Stage 3 CTAS 1.

    2. Hurdle-lognormal (keys: p_zero, mu_pos, sigma_pos, high)
       Used for Stage 3 CTAS 2-5.  With probability p_zero the value is 0;
       otherwise it is drawn from LogNormal(mu_pos, sigma_pos) truncated at high.

    surge_multiplier shifts the log-mean by ln(surge_multiplier), effectively
    multiplying the median by that factor.  For Stages 1 & 2 this parameter
    defaults to 1.0 (surge is handled externally); for Stage 3 it is passed in.
    """
    stage_cfg = ctas_wait_config.get(str(ctas_score), {}).get(stage_key, {})
    if not stage_cfg:
        return 0

    # --- Hurdle-lognormal (Stage 3 for CTAS 2-5) ---
    p_zero = stage_cfg.get("p_zero")
    if p_zero is not None:
        if random.random() < p_zero:
            return 0.0
        mu_pos = float(stage_cfg["mu_pos"])
        sigma_pos = float(stage_cfg["sigma_pos"])
        mu_pos += math.log(max(surge_multiplier, 1.0))
        high = stage_cfg.get("high")
        for _ in range(1000):
            x = random.lognormvariate(mu_pos, sigma_pos)
            if high is None or x <= high:
                return round(x, 1)
        return round(min(x, high), 1) if high else round(x, 1)

    # --- Truncated lognormal (Stage 1, 2, and Stage 3 CTAS 1) ---
    mu = stage_cfg.get("mu")
    sigma = stage_cfg.get("sigma")
    if mu is not None and sigma is not None:
        mu = float(mu)
        sigma = float(sigma)
        mu += math.log(max(surge_multiplier, 1.0))
        low = float(stage_cfg.get("low", 0))
        high = float(stage_cfg.get("high", 1440))
        for _ in range(1000):
            x = random.lognormvariate(mu, sigma)
            if low <= x <= high:
                return round(x, 1)
        return round(max(low, min(x, high)), 1)

    return 0


def _assign_wait_targets(patient, ctas_wait_config, curr_time, surge_multiplier=1.0):
    """
    Populate per-patient staged wait durations/timestamps if missing.

    Stage 1 (arrival->initial assessment) sets a ready_at timestamp.
    Stage 2/3 are stored as durations that can later be turned into
    ready_at timestamps when those stages start.

    Parameters
    ----------
    patient : Persona-like object with .role and .scratch
    ctas_wait_config : dict
        Config from _load_ctas_wait_config().
    curr_time : datetime.datetime
        Current simulation time to anchor timestamps.
    surge_multiplier : float
        Scale factor applied to all sampled stage durations.
        1.0 = normal (baseline), >1.0 = longer waits (surge).
    """
    if getattr(patient, "role", None) != "Patient":
        return

    scratch = patient.scratch
    ctas = scratch.CTAS if scratch.CTAS else 3

    # Stage 1: arrival -> initial assessment.
    # Baseline is anchored at arrival (triage + nurse time eat into it
    # naturally).  The surge extra is stored separately and added when
    # the patient reaches their bed (WAITING_FOR_FIRST_ASSESSMENT) so
    # that surge slowdown is always experienced in-bed, never consumed
    # by triage queue time.
    if scratch.stage1_minutes is None:
        baseline = _sample_wait_minutes(
            ctas_wait_config,
            ctas,
            "arrival_to_initial_assessment",
        )
        scratch.stage1_minutes = baseline
        scratch.stage1_surge_extra = baseline * max(0.0, surge_multiplier - 1.0)

    if scratch.initial_assessment_ready_at is None:
        scratch.initial_assessment_ready_at = curr_time + datetime.timedelta(
            minutes=float(scratch.stage1_minutes or 0)
        )

    # Stage 2: initial assessment -> disposition.
    # Baseline gates disposition_ready_at (set in do_initial_assessment).
    # Surge extra is added when the patient enters WAITING_FOR_RESULT
    # (after testing) so the extra time is spent in-bed, not consumed
    # by WAITING_FOR_TEST capacity queuing.
    if scratch.stage2_minutes is None:
        baseline = _sample_wait_minutes(
            ctas_wait_config,
            ctas,
            "initial_assessment_to_disposition",
        )
        scratch.stage2_minutes = baseline
        scratch.stage2_surge_extra = baseline * max(0.0, surge_multiplier - 1.0)

    # Stage 3: disposition -> exit.
    # Surge applied via mode-shift inside _sample_wait_minutes.
    if scratch.stage3_minutes is None:
        scratch.stage3_minutes = _sample_wait_minutes(
            ctas_wait_config,
            ctas,
            "disposition_to_exit",
            surge_multiplier=surge_multiplier,
        )

    # Flags for whether those events have happened yet
    if scratch.initial_assessment_done is None:
        scratch.initial_assessment_done = False
    if scratch.disposition_done is None:
        scratch.disposition_done = False