import subprocess
import sys
import os
import shutil
import json
import math
import time
sys.path.append('../../')

storage_dir = "../../environment/frontend_server/storage"

# For the newly created sim
new_sim_name = "in_progress"
new_sim_dir = f"{storage_dir}/{new_sim_name}"

# For the successful previous sim
saved_sim_name = "curr_sim"
saved_sim_dir = f"{storage_dir}/{saved_sim_name}"

script_to_run = "reverie.py"
hours_to_run = 48
steps_per_save = 1000

# --- Headless mode options ---
# write_movement = True  → writes movement/{step}.json every step
#                          needed for compress_sim_storage / replay
# write_movement = False → skips movement files entirely (faster, pure logic run)
#                          use reconstruct_headless_replay.py afterward if replay needed
write_movement = True

meta = json.load(open(f"{storage_dir}/curr_sim/reverie/meta.json", 'r'))
 
sec_per_step = meta["sec_per_step"]
total_steps = int(math.ceil(hours_to_run * 3600 / sec_per_step))
# Number of run chunks based on desired steps per save; always at least one chunk
total_runs = max(1, math.ceil(total_steps / steps_per_save))

# 1. Fill Injuries zone
input_data_to_send = f"run {steps_per_save}\n" \
                    "fin \n"


def _validate_sim_dir(sim_dir):
    """Check that essential simulation files exist in the given directory."""
    required = [
        f"{sim_dir}/reverie/meta.json",
        f"{sim_dir}/reverie/maze_status.json",
    ]
    for f in required:
        if not os.path.exists(f):
            print(f"WARNING: Missing required file: {f}")
            return False
        # Verify JSON is valid
        try:
            with open(f, "r") as fh:
                json.load(fh)
        except (json.JSONDecodeError, IOError) as e:
            print(f"WARNING: Corrupt file {f}: {e}")
            return False
    # Check that at least one environment file exists
    env_dir = f"{sim_dir}/environment"
    if os.path.exists(env_dir):
        env_files = [x for x in os.listdir(env_dir) if x.endswith(".json")]
        if not env_files:
            print(f"WARNING: No environment files in {env_dir}")
            return False
    return True


if __name__ == '__main__':
    i = 0
    consecutive_failures = 0
    # Backoff delays (in seconds) for consecutive failures. If the number of
    # consecutive failures exceeds len(_BACKOFF_DELAYS), the backoff logic
    # reuses the last element (i.e., it keeps using the maximum delay).
    _BACKOFF_DELAYS = [60, 120, 300]  # 1 min, 2 min, 5 min
    _MAX_CONSECUTIVE_FAILURES = 5     # Stop after this many failures in a row

    while i < total_runs:
        print(f"Attempting to run '{script_to_run}' with automatic input (using Popen)...\n")

        # Use headless mode for fast batch runs (no browser/frontend needed)
        arugments = ["--target", new_sim_name, "--headless", "yes",
                     "--write_movement", "yes" if write_movement else "no"]

        if os.path.exists(saved_sim_dir):
            if not _validate_sim_dir(saved_sim_dir):
                print(f"ERROR: Saved sim dir '{saved_sim_dir}' failed validation, cannot fork.")
                break
            arugments += ["--origin", saved_sim_name]
        input_data_to_send = f"run {steps_per_save}\n" \
                    "\n" \
                    "fin\n"

        try:
            # Start the subprocess with pipes for stdin, stdout, and stderr
            process = subprocess.Popen(
                [sys.executable, script_to_run] + arugments,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True # This handles encoding/decoding as text strings
            )

            # Send the input data and wait for the process to complete
            stderr_output = process.communicate(input=input_data_to_send)
            if stderr_output[1] != '':
                print(f"\n--- Errors from '{script_to_run}' ---")
                with open(f"error_log_run_simulation_safe-mode.txt", 'a') as error_log_file:
                    error_log_file.write(f"\n--- Errors from run {i} of '{script_to_run}' ---\n")
                    error_log_file.write(stderr_output[1])

                if os.path.exists(new_sim_dir):
                    shutil.rmtree(new_sim_dir)

                # Exponential backoff between consecutive failures
                consecutive_failures += 1
                if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                    print(f"\n=== CIRCUIT BREAKER: {consecutive_failures} consecutive failures. "
                          f"Stopping safe-mode runner. ===")
                    print(f"Check error_log_run_simulation_safe-mode.txt for details.")
                    sys.exit(1)

                delay_idx = min(consecutive_failures - 1, len(_BACKOFF_DELAYS) - 1)
                delay = _BACKOFF_DELAYS[delay_idx]
                print(f"Waiting {delay}s before retry (failure #{consecutive_failures}/{_MAX_CONSECUTIVE_FAILURES})...")
                time.sleep(delay)
                continue

            # Success — reset failure counter
            consecutive_failures = 0

            # Only change folder name if the sim had no errors
            if os.path.exists(saved_sim_dir):
                shutil.rmtree(saved_sim_dir)

            os.rename(new_sim_dir, saved_sim_dir)


            print(f"'{script_to_run}' finished with return code: {process.returncode}")
            i += 1

        except FileNotFoundError:
            print(f"Error: Python interpreter ('{sys.executable}') or script '{script_to_run}' not found.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
