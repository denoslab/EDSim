import json
import copy
import numpy
import datetime
import pickle
import time
import math
import os
import shutil
import traceback
import argparse
import random
import pandas as pd
import bisect
from selenium import webdriver
from global_methods import *
import utils
from maze import *
from persona.persona import *
from persona.persona_types.patient import *
from persona.persona_types.bedside_nurse import *
from persona.persona_types.triage_nurse import *
from persona.persona_types.doctor import *
import pathlib
import uuid
from pathlib import Path


from wait_time_utils import (
    _load_ctas_wait_config,
    _sample_wait_minutes,
    _assign_wait_targets,
)


current_file = os.path.abspath(__file__)

def trace_calls_and_lines(frame, event, arg):
    if event == 'call':
        code = frame.f_code
        filename = code.co_filename
        short_filename = os.path.relpath(filename)
        if os.path.abspath(filename).startswith(os.getcwd()):
        # # if os.path.abspath(filename).startswith():
        # # if filename == current_file:
            print(f"Calling function: {code.co_name} in {short_filename}:{code.co_firstlineno}")

##############################################################################
#                           UTILITY FUNCTIONS                                #
##############################################################################

import tempfile

def _atomic_write_json(path, data, indent=2):
  """Write JSON to *path* atomically: write to a temp file first, then
  replace the target. This prevents partial/corrupt files if the process
  crashes mid-write."""
  dir_name = os.path.dirname(path)
  os.makedirs(dir_name, exist_ok=True)
  fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
  try:
    with os.fdopen(fd, "w") as f:
      json.dump(data, f, indent=indent)
    os.replace(tmp_path, path)
  except BaseException:
    try:
      os.unlink(tmp_path)
    except OSError:
      pass
    raise

##############################################################################
#                                  REVERIE                                   #
##############################################################################

class ReverieServer: 
  def __init__(self, 
               fork_sim_code,
               sim_code):
    self.driver = None
    print ("(reverie): Temp storage: ", fs_temp_storage)
    
    utils.static_sim_code = sim_code
    # FORKING FROM A PRIOR SIMULATION:
    # <fork_sim_code> indicates the simulation we are forking from. 
    # Interestingly, all simulations must be forked from some initial 
    # simulation, where the first simulation is "hand-crafted".
    self.fork_sim_code = fork_sim_code
    fork_folder = f"{fs_storage}/{self.fork_sim_code}"

    # <sim_code> indicates our current simulation. The first step here is to 
    # copy everything that's in <fork_sim_code>, but edit its 
    # reverie/meta/json's fork variable. 
    self.sim_code = sim_code
    sim_folder = f"{fs_storage}/{self.sim_code}"
    copyanything(fork_folder, sim_folder)

    with open(f"{sim_folder}/reverie/meta.json") as json_file:  
      reverie_meta = json.load(json_file)
    
    with open(f"{sim_folder}/reverie/meta.json", "w") as outfile: 
      reverie_meta["fork_sim_code"] = fork_sim_code
      outfile.write(json.dumps(reverie_meta, indent=2))

    with open(f"{sim_folder}/reverie/data_collection.json") as json_file:  
      self.data_collection = json.load(json_file)

    self.seed = 0
    if(reverie_meta["seed"] != None):
      self.seed = reverie_meta["seed"]
    else:
      self.seed = random.randint(0, 1000000)

    random.seed(self.seed)

    # LOADING REVERIE'S GLOBAL VARIABLES
    # The start datetime of the Reverie: 
    # <start_datetime> is the datetime instance for the start datetime of 
    # the Reverie instance. Once it is set, this is not really meant to 
    # change. It takes a string date in the following example form: 
    # "June 25, 2022"
    # e.g., ...strptime(June 25, 2022, "%B %d, %Y")
    self.start_time = datetime.datetime.strptime(
                        f"{reverie_meta['start_date']}, 06:00:00",  
                        "%B %d, %Y, %H:%M:%S")
    # <curr_time> is the datetime instance that indicates the game's current
    # time. This gets incremented by <sec_per_step> amount everytime the world
    # progresses (that is, everytime curr_env_file is recieved). 
    self.curr_time = datetime.datetime.strptime(reverie_meta['curr_time'], 
                                                "%B %d, %Y, %H:%M:%S")
    print ("(reverie): Current time: ", self.curr_time)
    # <sec_per_step> denotes the number of seconds in game time that each 
    # step moves foward. 
    self.sec_per_step = reverie_meta['sec_per_step']

    travel_speed_mps = reverie_meta.get("travel_speed_mps")
    travel_seconds_per_tile = reverie_meta.get("travel_seconds_per_tile")
    travel_minutes_per_tile = reverie_meta.get("travel_minutes_per_tile")
    meters_per_tile = reverie_meta.get("meters_per_tile", 1)
    self.travel_minutes_per_tile = 0.0
    if travel_minutes_per_tile is not None:
      try:
        self.travel_minutes_per_tile = float(travel_minutes_per_tile)
      except (TypeError, ValueError):
        self.travel_minutes_per_tile = 0.0
    elif travel_seconds_per_tile is not None:
      try:
        self.travel_minutes_per_tile = float(travel_seconds_per_tile) / 60.0
      except (TypeError, ValueError):
        self.travel_minutes_per_tile = 0.0
    elif travel_speed_mps is not None:
      try:
        speed = float(travel_speed_mps)
        tile_meters = float(meters_per_tile) if meters_per_tile is not None else 1.0
        if speed > 0:
          self.travel_minutes_per_tile = (tile_meters / speed) / 60.0
      except (TypeError, ValueError):
        self.travel_minutes_per_tile = 0.0
    
    # <maze> is the main Maze instance. Note that we pass in the maze_name
    # (e.g., "double_studio") to instantiate Maze. 
    # e.g., Maze("double_studio")
    self.maze = Maze(reverie_meta['maze_name'], fork_folder, sim_folder, self.seed)

    # Compute tiles_per_step from walking speed for adaptive multi-tile movement
    if self.travel_minutes_per_tile > 0:
      secs_per_tile = self.travel_minutes_per_tile * 60
      self.maze.tiles_per_step = max(1, int(self.sec_per_step / secs_per_tile))
    else:
      self.maze.tiles_per_step = max(1, int(self.sec_per_step))
    print(f"[Reverie] tiles_per_step = {self.maze.tiles_per_step} "
          f"(sec_per_step={self.sec_per_step}, "
          f"travel_min_per_tile={self.travel_minutes_per_tile:.4f})")

    # Override diagnostic room capacity if configured in meta.json
    self.diagnostic_room_capacity = reverie_meta.get("diagnostic_room_capacity")
    if self.diagnostic_room_capacity is not None and int(self.diagnostic_room_capacity) > 0:
        self.maze.injuries_zones["diagnostic room"]["capacity"] = int(self.diagnostic_room_capacity)

    # <step> denotes the number of steps that our game has taken. A step here
    # literally translates to the number of moves our personas made in terms
    # of the number of tiles. 
    self.step = reverie_meta['step']

    # Rate to control how many Patients are coming in each hour
    self.patient_rate = reverie_meta['patient_rate_modifier']

    # Surge slowdown: scale all stage wait times up when patient_rate is above
    # the baseline.  At baseline (default 0.5) multiplier = 1.0 (no change).
    # At 1.0 with scale=0.5: multiplier = 1.5 (50% longer waits across all stages).
    # Formula: 1.0 + max(0, (rate - baseline) / baseline) * scale
    # Both values are tunable in meta.json.
    _surge_baseline = float(reverie_meta.get("surge_baseline_rate", 0.5))
    _surge_scale    = float(reverie_meta.get("surge_slowdown_scale", 0.5))
    self.surge_multiplier = 1.0 + max(0.0, (self.patient_rate - _surge_baseline) / _surge_baseline) * _surge_scale
    print(f"(reverie): surge_multiplier = {self.surge_multiplier:.3f} "
          f"(patient_rate={self.patient_rate}, baseline={_surge_baseline}, scale={_surge_scale})")

    # fill_injuries: fraction of bed capacity to fill at startup (0 to 1.0)
    # Legacy support: "yes" -> 1.0, "no" -> 0
    raw_fill = reverie_meta["fill_injuries"]
    if isinstance(raw_fill, str):
      self.fill_injuries = 1.0 if 'y' in raw_fill else 0
    else:
      self.fill_injuries = float(raw_fill)

    # Number of real patients to preload into the waiting room at simulation start
    self.preload_waiting_room_patients = reverie_meta.get("preload_waiting_room_patients", 0)

    # SETTING UP PERSONAS IN REVERIE
    # <personas> is a dictionary that takes the persona's full name as its 
    # keys, and the actual persona instance as its values.
    # This dictionary is meant to keep track of all personas who are part of
    # the Reverie instance. 
    # e.g., ["Isabella Rodriguez"] = Persona("Isabella Rodriguezs")
    self.personas = dict()
    # <personas_tile> is a dictionary that contains the tile location of
    # the personas (!-> NOT px tile, but the actual tile coordinate).
    # The tile take the form of a set, (row, col). 
    # e.g., ["Isabella Rodriguez"] = (58, 39)
    self.personas_tile = dict()
    
    # Patient time increment for data collection is set according to steps
    Patient.time_increment = reverie_meta["sec_per_step"] / 60 # In minutes
    Patient.priority_factor = reverie_meta["priority_factor"]
    Patient.testing_result_time = reverie_meta["testing_result_time"] * self.surge_multiplier
    Patient.testing_time        = reverie_meta["testing_time"]        * self.surge_multiplier
    Patient.testing_probability_by_ctas = reverie_meta.get("testing_probability_by_ctas",
        {"1": 1.0, "2": 0.8, "3": 0.5, "4": 0.3, "5": 0.0})
    self.patient_walkout_probability = reverie_meta.get("patient_walkout_probability", 0.0)
    self.patient_walkout_check_minutes = reverie_meta.get("patient_walkout_check_minutes", 20)
    self.patient_post_discharge_linger_probability = reverie_meta.get("patient_post_discharge_linger_probability", 0.0)
    self.patient_post_discharge_linger_minutes = reverie_meta.get("patient_post_discharge_linger_minutes", 30)
    Patient.walkout_probability = self.patient_walkout_probability
    Patient.walkout_check_minutes = self.patient_walkout_check_minutes
    Patient.post_discharge_linger_probability = self.patient_post_discharge_linger_probability
    Patient.post_discharge_linger_minutes = self.patient_post_discharge_linger_minutes

    # Hospital admission/boarding config
    self.simulate_hospital_admission = reverie_meta.get("simulate_hospital_admission", False)
    self.admission_probability_by_ctas = reverie_meta.get("admission_probability_by_ctas", {})
    self.admission_boarding_minutes_min = reverie_meta.get("admission_boarding_minutes_min", 60)
    self.admission_boarding_minutes_max = reverie_meta.get("admission_boarding_minutes_max", 480)
    Patient.simulate_hospital_admission = self.simulate_hospital_admission
    Patient.admission_probability_by_ctas = self.admission_probability_by_ctas
    Patient.admission_boarding_minutes_min = self.admission_boarding_minutes_min
    Patient.admission_boarding_minutes_max = self.admission_boarding_minutes_max

    # Headless mode: skip file-based frontend sync for faster batch runs
    self.headless = False
    # Write movement/{step}.json each step (disable for pure logic/data runs)
    self.write_movement = True

    Triage_Nurse.priority_factor = reverie_meta["priority_factor"]

    Bedside_Nurse.testing_time    = reverie_meta["testing_time"] * self.surge_multiplier
    Bedside_Nurse.resting_time    = Bedside_Nurse.resting_time  * self.surge_multiplier
    Bedside_Nurse.priority_factor = reverie_meta["priority_factor"]
    Doctor.doctor_resting_time    = Doctor.doctor_resting_time  * self.surge_multiplier


    Doctor.priority_factor = reverie_meta["priority_factor"]
    Doctor.max_patients = reverie_meta.get("max_patients_assigned_doctor", 5)
    # Load supporting data before personas are instantiated
    self.symptoms = read_csv_to_dict('data/diagnosis.csv')
    self.ed_visits = read_csv_to_dict('data/ed_visits_per_hour.csv')
    self.ctas_wait_config = _load_ctas_wait_config()

    # Priority boosting and global queue aging config (soft-deadline mechanism)
    self._boost_interval_minutes = reverie_meta.get("priority_boost_interval_minutes", 5)
    self._global_queue_aging_interval = reverie_meta.get("global_queue_aging_interval_minutes", 15)
    self._last_boost_time = None
    self._last_global_queue_aging_time = None

    # Preloaded (filler) patient departure window
    self._preload_departure_window_hours = reverie_meta.get("preload_departure_window_hours", 6)

    # # <persona_convo_match> is a dictionary that describes which of the two
    # # personas are talking to each other. It takes a key of a persona's full
    # # name, and value of another persona's full name who is talking to the 
    # # original persona. 
    # # e.g., dict["Isabella Rodriguez"] = ["Maria Lopez"]
    # self.persona_convo_match = dict()
    # # <persona_convo> contains the actual content of the conversations. It
    # # takes as keys, a pair of persona names, and val of a string convo. 
    # # Note that the key pairs are *ordered alphabetically*. 
    # # e.g., dict[("Adam Abraham", "Zane Xu")] = "Adam: baba \n Zane:..."
    # self.persona_convo = dict()
    
    self.doctor_starting_amount = reverie_meta["doctor_starting_amount"]
    self.triage_starting_amount = reverie_meta["triage_starting_amount"]
    self.bedside_starting_amount = reverie_meta["bedside_starting_amount"]

    self.persona_classes = {
        "Patient": Patient,
        "BedsideNurse": Bedside_Nurse,
        "TriageNurse": Triage_Nurse,
        "Doctor": Doctor
        # Add other roles and their classes here as needed
    }

    #Tracks number of patients in the simulator
    self.num_roles = {
      "Patient": 0,
      "Doctor": 0,
      "BedsideNurse": 0,
      "TriageNurse": 0
    }

    # To hold the increment for adding a Patient
    self.add_patient_threshold = reverie_meta["add_patient_threshold"]
    
    # Loading in all personas.
    init_env_file = f"{sim_folder}/environment/{str(self.step)}.json"
    init_env = None

    # Try loading the environment file with fallback to previous steps
    if os.path.exists(init_env_file):
      try:
        with open(init_env_file, "r") as f:
          init_env = json.load(f)
      except (json.JSONDecodeError, IOError) as e:
        print(f"(reverie): WARNING — corrupt env file {init_env_file}: {e}")

    if init_env is None:
      # Fallback: scan backwards for the most recent valid environment file
      env_dir = f"{sim_folder}/environment"
      fallback_step = self.step - 1
      while fallback_step >= 0 and init_env is None:
        fallback_file = f"{env_dir}/{fallback_step}.json"
        if os.path.exists(fallback_file):
          try:
            with open(fallback_file, "r") as f:
              init_env = json.load(f)
            print(f"(reverie): Recovered env from step {fallback_step} (target was {self.step})")
          except (json.JSONDecodeError, IOError):
            pass
        fallback_step -= 1

      if init_env is None:
        # Last resort: create minimal env so personas can spawn at defaults
        print(f"(reverie): WARNING — no valid env file found, using empty init_env")
        init_env = {}
    for persona_name in reverie_meta['persona_names']: 
      persona_folder = f"{sim_folder}/personas/{persona_name[0]}"

      # Use .get() to retrieve the class, defaulting to Persona if not found
      PersonaClass = self.persona_classes.get(persona_name[1], Persona)

      # Create an instance of the determined class
      curr_persona = PersonaClass(persona_name[0], persona_folder, role=persona_name[1], seed=self.seed)
      _assign_wait_targets(curr_persona, self.ctas_wait_config, self.curr_time, self.surge_multiplier)


      # Ensure persona has an entry in init_env (may be missing after recovery)
      if persona_name[0] not in init_env:
        init_env[persona_name[0]] = {"maze": "Emergency Department", "x": 0, "y": 0}

      if(not curr_persona.scratch.curr_tile):
        spawn_loc = curr_persona.get_spawn_loc(self.maze)
        p_x = init_env[persona_name[0]]["x"] = spawn_loc[0]
        p_y = init_env[persona_name[0]]["y"] = spawn_loc[1] - 1

        curr_persona.scratch.curr_tile = [p_x, p_y]
      else:
        p_x = init_env[persona_name[0]]["x"]
        p_y = init_env[persona_name[0]]["y"] 
 

      curr_persona.scratch.tile = [p_x, p_y]

      self.num_roles[curr_persona.role] += 1

      # If the new persona is a Patient them to the queue for the Triage Room
      if(curr_persona.role == "Patient"):
        if(curr_persona.name not in self.maze.triage_queue and curr_persona.scratch.state == "WAITING_FOR_TRIAGE"):
          self.maze.triage_queue.append(curr_persona.name)

      # Add persona to data_collection if they not been added yet
      if(curr_persona.name not in self.data_collection[curr_persona.role].keys()):
        temp_dict = curr_persona.data_collection_dict()
    
        self.data_collection[curr_persona.role][curr_persona.name] = temp_dict

      self.personas[persona_name[0]] = curr_persona
      self.personas_tile[persona_name[0]] = (p_x, p_y)
      self.maze.tiles[p_y][p_x]["events"].add(curr_persona.scratch
                                              .get_curr_event_and_desc())
      
    with open(init_env_file, "w") as outfile: 
          outfile.write(json.dumps(init_env, indent=2))

    # Grab total amount of Patients from data_collection as this also tracks Patients who left.
    self.num_roles["Patient"] = len(self.data_collection["Patient"])
    self.maze.triage_capacity = self.num_roles["TriageNurse"]

    # self.maze.doctors_taking_more_patients = [p.name for p in self.personas.values() if p.role == "Doctor" and len(p.scratch.assigned_patients) < p.max_patients]

    print(self.maze.doctors_taking_more_patients)

    # REVERIE SETTINGS PARAMETERS:  
    # <server_sleep> denotes the amount of time that our while loop rests each
    # cycle; this is to not kill our machine. 
    self.server_sleep = 0.01


    # SIGNALING THE FRONTEND SERVER: 
    # curr_sim_code.json contains the current simulation code, and
    # curr_step.json contains the current step of the simulation. These are 
    # used to communicate the code and step information to the frontend. 
    # Note that step file is removed as soon as the frontend opens up the 
    # simulation. 
    curr_sim_code = dict()
    curr_sim_code["sim_code"] = self.sim_code
    with open(f"{fs_temp_storage}/curr_sim_code.json", "w") as outfile: 
      outfile.write(json.dumps(curr_sim_code, indent=2))
    
    curr_step = dict()
    curr_step["step"] = self.step
    with open(f"{fs_temp_storage}/curr_step.json", "w") as outfile: 
      outfile.write(json.dumps(curr_step, indent=2))

  def _is_in_assessment_queue(self, patient_name):
    return any(entry[1] == patient_name for entry in self.maze.injuries_zones["assessment_queue"])

  @staticmethod
  def _try_load_json_file(file_path):
    """
    Read a JSON file safely.
    Returns (True, payload) on success, (False, None) on parse/read failure.
    """
    try:
      with open(file_path) as json_file:
        return True, json.load(json_file)
    except Exception:
      return False, None

  def _enqueue_ready_initial_assessments(self):
    """
    Move WAITING_FOR_FIRST_ASSESSMENT patients to the assessment queue once their staged wait is satisfied.
    """
    for persona in self.personas.values():
      if persona.role != "Patient":
        continue
      if persona.scratch.initial_assessment_done:
        continue
      if persona.scratch.state != "WAITING_FOR_FIRST_ASSESSMENT":
        continue
      ready_at = persona.scratch.initial_assessment_ready_at
      if ready_at and self.curr_time < ready_at:
        continue
      if self._is_in_assessment_queue(persona.name):
        continue
      bisect.insort_right(self.maze.injuries_zones["assessment_queue"],
                          [persona.scratch.CTAS * Patient.priority_factor, persona.name])

  def _rescue_orphaned_patients(self):
    """
    Scan all patients each step. If a patient is stuck with no assigned
    doctor and not already queued, re-insert them into the appropriate
    queue so they can be picked up.

    Bug fixes:
    - WAITING_FOR_NURSE patients are only inserted into the nurse queue
      (not the doctor queue — they haven't been transported yet).
    - Patients already claimed by a nurse's `occupied` field are skipped
      to prevent every nurse chasing the same patient.
    """
    rescuable_states = {"WAITING_FOR_NURSE", "WAITING_FOR_FIRST_ASSESSMENT", "WAITING_FOR_TEST", "WAITING_FOR_RESULT", "WAITING_FOR_DOCTOR"}
    # Only patients past nurse escort belong in the doctor queue
    doctor_queue_states = {"WAITING_FOR_FIRST_ASSESSMENT", "WAITING_FOR_TEST", "WAITING_FOR_RESULT", "WAITING_FOR_DOCTOR"}
    queued_names = set(entry[1] for entry in self.maze.patients_waiting_for_doctor)

    # Pre-compute patients already claimed by a bedside nurse
    nurse_occupied_patients = set()
    for p in self.personas.values():
      if getattr(p, "role", None) == "Bedside Nurse" and p.scratch.occupied:
        nurse_occupied_patients.add(str(p.scratch.occupied).split("|")[-1])

    for persona in self.personas.values():
      if persona.role != "Patient":
        continue
      if persona.scratch.state not in rescuable_states:
        continue
      if persona.scratch.left_without_being_seen:
        continue
      assigned_doctor = persona.scratch.assigned_doctor
      if assigned_doctor is not None:
        doctor_obj = self.personas.get(str(assigned_doctor))
        if doctor_obj is not None and getattr(doctor_obj, "role", None) == "Doctor":
          continue
        # Recover from stale/corrupt doctor references so intake can proceed.
        persona.scratch.assigned_doctor = None

      # Doctor queue: only for patients past nurse escort
      if persona.scratch.state in doctor_queue_states and persona.name not in queued_names:
        priority = persona.scratch.CTAS * Patient.priority_factor if persona.scratch.CTAS else 3 * Patient.priority_factor
        bisect.insort_right(self.maze.patients_waiting_for_doctor, [priority, persona.name])
        queued_names.add(persona.name)
        print(f"(reverie): Rescued orphaned patient {persona.name} (state={persona.scratch.state}, CTAS {persona.scratch.CTAS}) into patients_waiting_for_doctor")

      # Nurse queue: only for WAITING_FOR_NURSE patients not already claimed
      if persona.scratch.state == "WAITING_FOR_NURSE":
        if persona.name in nurse_occupied_patients:
          continue
        nurse_queued = set(entry[1] for entry in self.maze.injuries_zones.get("bedside_nurse_waiting", []))
        if persona.name not in nurse_queued:
          ctas = persona.scratch.CTAS if persona.scratch.CTAS else 3
          bisect.insort_right(
            self.maze.injuries_zones["bedside_nurse_waiting"],
            [ctas * Patient.priority_factor, persona.name]
          )
          print(f"(reverie): Re-inserted {persona.name} into bedside_nurse_waiting")

  def _age_global_doctor_queue(self):
    """
    Every _global_queue_aging_interval sim minutes, decrement all priority
    values in maze.patients_waiting_for_doctor by 2 (min 1), then re-sort.
    Mirrors the per-doctor queue aging in doctor.py:66-74 but for the global
    queue, which otherwise has NO aging mechanism.
    """
    if not self.maze.patients_waiting_for_doctor:
      return
    if self._last_global_queue_aging_time and (self.curr_time - self._last_global_queue_aging_time) < datetime.timedelta(minutes=self._global_queue_aging_interval):
      return
    self._last_global_queue_aging_time = self.curr_time
    for entry in self.maze.patients_waiting_for_doctor:
      entry[0] = max(1, entry[0] - 2)
    self.maze.patients_waiting_for_doctor.sort(key=lambda e: e[0])

  def _boost_overdue_patients(self):
    """
    Every _boost_interval_minutes sim minutes, scan all patients and compute
    actual stage time vs target. If overdue, proportionally reduce the
    patient's priority in whichever queue they sit in.

    Stage 1 actual = WAITING_FOR_TRIAGE + TRIAGE + WAITING_FOR_NURSE + WAITING_FOR_FIRST_ASSESSMENT
    Stage 2 actual = WAITING_FOR_TEST + GOING_FOR_TEST + WAITING_FOR_RESULT + WAITING_FOR_DOCTOR
    """
    if self._last_boost_time and (self.curr_time - self._last_boost_time) < datetime.timedelta(minutes=self._boost_interval_minutes):
      return
    self._last_boost_time = self.curr_time

    stage1_states = {"WAITING_FOR_TRIAGE", "TRIAGE", "WAITING_FOR_NURSE", "WAITING_FOR_FIRST_ASSESSMENT"}
    stage2_states = {"WAITING_FOR_TEST", "GOING_FOR_TEST", "WAITING_FOR_RESULT", "WAITING_FOR_DOCTOR"}

    modified_queues = set()

    for persona in self.personas.values():
      if persona.role != "Patient":
        continue
      if persona.scratch.left_without_being_seen:
        continue

      p_data = self.data_collection.get("Patient", {}).get(persona.name)
      if not p_data:
        continue
      time_spent = p_data.get("time_spent_state", {})

      # Determine which stage the patient is currently in and compute actual time
      current_state = persona.scratch.state
      actual = 0
      target = 0

      if current_state in stage1_states:
        actual = sum(time_spent.get(s, 0) for s in stage1_states)
        target = float(persona.scratch.stage1_minutes or 0) + float(persona.scratch.stage1_surge_extra or 0)
      elif current_state in stage2_states:
        actual = sum(time_spent.get(s, 0) for s in stage2_states)
        target = float(persona.scratch.stage2_minutes or 0) + float(persona.scratch.stage2_surge_extra or 0)

      if target <= 0 or actual <= target:
        continue

      overdue_factor = actual / target
      if overdue_factor <= 1.0:
        continue

      # Find patient in a queue and boost their priority
      boosted = False

      # Search patients_waiting_for_doctor
      for entry in self.maze.patients_waiting_for_doctor:
        if entry[1] == persona.name:
          entry[0] = max(1, int(entry[0] / overdue_factor))
          modified_queues.add("patients_waiting_for_doctor")
          boosted = True
          break

      # Search doctor's assigned_patients_waitlist
      if not boosted and persona.scratch.assigned_doctor:
        doctor = self.personas.get(persona.scratch.assigned_doctor)
        if doctor:
          for entry in doctor.scratch.assigned_patients_waitlist:
            if entry[1] == persona.name:
              entry[0] = max(1, int(entry[0] / overdue_factor))
              modified_queues.add(f"doctor_{doctor.name}")
              boosted = True
              break

      # Search bedside_nurse_waiting
      if not boosted:
        for entry in self.maze.injuries_zones.get("bedside_nurse_waiting", []):
          if entry[1] == persona.name:
            entry[0] = max(1, int(entry[0] / overdue_factor))
            modified_queues.add("bedside_nurse_waiting")
            boosted = True
            break

    # Re-sort all modified queues
    if "patients_waiting_for_doctor" in modified_queues:
      self.maze.patients_waiting_for_doctor.sort(key=lambda e: e[0])
    if "bedside_nurse_waiting" in modified_queues:
      self.maze.injuries_zones["bedside_nurse_waiting"].sort(key=lambda e: e[0])
    for key in modified_queues:
      if key.startswith("doctor_"):
        doctor_name = key[len("doctor_"):]
        doctor = self.personas.get(doctor_name)
        if doctor:
          doctor.scratch.assigned_patients_waitlist.sort(key=lambda e: e[0])

  def _process_preloaded_departures(self):
    """
    Check each preloaded (filler) patient for its scheduled departure time.
    When the deadline arrives, cleanly remove the patient from all queues,
    free its bed, and transition it to LEAVING so it walks to the exit.
    """
    for persona in list(self.personas.values()):
      if persona.role != "Patient":
        continue
      if not persona.scratch.exempt_from_data_collection:
        continue
      if persona.scratch.preload_departure_at is None:
        continue
      if self.curr_time < persona.scratch.preload_departure_at:
        continue
      if persona.scratch.state == "LEAVING":
        continue

      # --- Queue cleanup ---
      # 1. Triage queue (list of names)
      if persona.name in self.maze.triage_queue:
        self.maze.triage_queue.remove(persona.name)

      # 2. Bedside nurse waiting queue ([priority, name] pairs)
      for entry in self.maze.injuries_zones["bedside_nurse_waiting"][:]:
        if entry[1] == persona.name:
          self.maze.injuries_zones["bedside_nurse_waiting"].remove(entry)
          break

      # 3. Pager queue ([priority, name] pairs)
      for entry in self.maze.injuries_zones.get("pager", [])[:]:
        if entry[1] == persona.name:
          self.maze.injuries_zones["pager"].remove(entry)
          break

      # 4. Global doctor queue ([priority, name] pairs)
      for entry in self.maze.patients_waiting_for_doctor[:]:
        if entry[1] == persona.name:
          self.maze.patients_waiting_for_doctor.remove(entry)
          break

      # 5. Assessment queue ([priority, name] pairs)
      for entry in self.maze.injuries_zones["assessment_queue"][:]:
        if entry[1] == persona.name:
          self.maze.injuries_zones["assessment_queue"].remove(entry)
          break

      # 6. Release bed and clean all zone current_patients lists
      if hasattr(persona, "_release_bed"):
        persona._release_bed(self.maze)
      for zone_name, zone_info in self.maze.injuries_zones.items():
        if isinstance(zone_info, dict):
          cp = zone_info.get("current_patients", [])
          if persona.name in cp:
            cp.remove(persona.name)

      # 7. Clean up doctor assignment
      assigned_doctor_name = persona.scratch.assigned_doctor
      if assigned_doctor_name:
        doctor_obj = self.personas.get(str(assigned_doctor_name))
        if doctor_obj and getattr(doctor_obj, "role", None) == "Doctor":
          doctor_obj.remove_patient(persona, self.maze)
          queue = getattr(doctor_obj.scratch, "assigned_patients_waitlist", None)
          if isinstance(queue, list):
            queue[:] = [
              entry for entry in queue
              if not (isinstance(entry, (list, tuple))
                      and len(entry) >= 2
                      and str(entry[1]).strip() == persona.name)
            ]

      # 8. Clear doctor reference
      persona.scratch.assigned_doctor = None

      # 9. Clear chatting state so the other persona isn't stuck
      chat_partner_name = persona.scratch.chatting_with
      if chat_partner_name:
        partner = self.personas.get(chat_partner_name)
        if partner:
          if partner.scratch.chatting_with == persona.name:
            partner.scratch.chatting_with = None
            partner.scratch.chat = None
            partner.scratch.chatting_end_time = None
          # If a bedside nurse had this patient as occupied, release them
          if getattr(partner.scratch, "occupied", None) and persona.name in str(partner.scratch.occupied):
            partner.scratch.occupied = None
            partner.scratch.next_step = None
        persona.scratch.chatting_with = None
        persona.scratch.chat = None
        persona.scratch.chatting_end_time = None

      # 10. Release any bedside nurse whose occupied references this patient
      for other in self.personas.values():
        if getattr(other, "role", None) != "Patient" and getattr(other.scratch, "occupied", None):
          if persona.name in str(other.scratch.occupied):
            other.scratch.occupied = None
            other.scratch.next_step = None

      # --- Set departure state ---
      persona.scratch.state = "LEAVING"
      persona.scratch.next_step = "ed map:emergency department:exit"
      persona.scratch.act_path_set = False
      persona.scratch.preload_departure_at = None  # prevent re-processing

      print(f"(reverie): Preloaded patient {persona.name} departing (scheduled departure reached)")

  # ------------------------------------------------------------------
  # Triage timeout safety net
  # ------------------------------------------------------------------
  _TRIAGE_TIMEOUT_MINUTES = 3  # normal triage takes 0.3-0.5 min

  def _check_triage_timeouts(self):
    """
    Force-complete any patient stuck in TRIAGE for longer than
    _TRIAGE_TIMEOUT_MINUTES.  This prevents a triage nurse's missed
    conversation from orphaning a patient and blocking the slot
    indefinitely.
    """
    for persona in list(self.personas.values()):
      if persona.role != "Patient":
        continue
      if persona.scratch.state != "TRIAGE":
        continue

      # Use tracked time_spent_state to detect timeout
      p_data = self.data_collection.get("Patient", {}).get(persona.name)
      if not p_data:
        continue
      triage_minutes = float(p_data.get("time_spent_state", {}).get("TRIAGE", 0) or 0)
      if triage_minutes < self._TRIAGE_TIMEOUT_MINUTES:
        continue

      print(f"(reverie): Triage timeout for {persona.name} "
            f"({triage_minutes:.1f} min in TRIAGE) — force-completing")

      # 1. Transition: TRIAGE → WAITING_FOR_NURSE
      persona.scratch.state = "WAITING_FOR_NURSE"
      persona.scratch.next_room = persona.scratch.injuries_zone
      persona.scratch.next_step = (
          "ed map:emergency department:waiting room:waiting room chair"
      )
      persona.scratch.act_path_set = False

      # 2. Free triage slot
      if self.maze.triage_patients > 0:
        self.maze.triage_patients -= 1

      # 3. Add to bedside nurse queue (pager if CTAS 1)
      ctas = persona.scratch.CTAS if persona.scratch.CTAS is not None else 3
      prio = ctas * Patient.priority_factor
      if ctas != 1:
        bisect.insort_right(
            self.maze.injuries_zones["bedside_nurse_waiting"],
            [prio, persona.name],
        )
      else:
        bisect.insort_right(
            self.maze.injuries_zones["pager"],
            [prio, persona.name],
        )

      # 4. Add to doctor waiting queue
      if not any(e[1] == persona.name for e in self.maze.patients_waiting_for_doctor):
        bisect.insort_right(
            self.maze.patients_waiting_for_doctor,
            [prio, persona.name],
        )

      # 5. Clear stale chatting state on any triage nurse referencing
      #    this patient
      for other in self.personas.values():
        if getattr(other, "role", None) == "TriageNurse":
          if getattr(other.scratch, "chatting_with", None) == persona.name:
            other.scratch.chatting_with = None
            other.scratch.chat = None
            other.scratch.chatting_end_time = None
          if getattr(other.scratch, "chatting_patient", None) == persona.name:
            other.scratch.chatting_patient = None

  # ------------------------------------------------------------------
  # Live simulation status dashboard
  # ------------------------------------------------------------------
  _STATUS_INTERVAL = 30  # write every N steps (~5 min sim time at 10s/step)

  def _write_sim_status(self, sim_folder):
    """Write a human-readable status snapshot so operators can monitor a
    headless run.  Output goes to  <sim_folder>/sim_status.txt ."""
    if self.step % self._STATUS_INTERVAL != 0:
      return

    # --- Gather patient states ---
    state_counts = {}
    total_patients = 0
    completed = 0
    left_ed = 0
    for p in self.personas.values():
      if p.role != "Patient":
        continue
      total_patients += 1
      st = p.scratch.state or "UNKNOWN"
      state_counts[st] = state_counts.get(st, 0) + 1
      if getattr(p.scratch, "left_ED", False):
        left_ed += 1

    # --- Zone occupancy ---
    zone_lines = []
    for zone_name in ["trauma room", "major injuries zone",
                       "minor injuries zone", "diagnostic room"]:
      info = self.maze.injuries_zones.get(zone_name, {})
      if not isinstance(info, dict):
        continue
      cur = len(info.get("current_patients", []))
      cap = info.get("capacity", "?")
      zone_lines.append(f"  {zone_name:<25s}  {cur} / {cap}")

    # --- Queue sizes ---
    nurse_q = len(self.maze.injuries_zones.get("bedside_nurse_waiting", []))
    pager_q = len(self.maze.injuries_zones.get("pager", []))
    triage_q = len(self.maze.triage_queue)
    doctor_global_q = len(self.maze.patients_waiting_for_doctor)

    # --- Doctor utilisation ---
    doctors_free = len(self.maze.doctors_taking_more_patients)
    doctor_assigned = {}
    for p in self.personas.values():
      if getattr(p, "role", None) == "Doctor":
        n = len(getattr(p.scratch, "assigned_patients", []))
        doctor_assigned[p.name] = n

    # --- Nurse utilisation ---
    nurse_status = {"Monitoring": 0, "Transferring": 0,
                    "Resting": 0, "Available": 0, "Other": 0}
    for p in self.personas.values():
      if getattr(p, "role", None) != "BedsideNurse":
        continue
      occ = getattr(p.scratch, "occupied", None)
      desc = getattr(p.scratch, "act_description", "") or ""
      if occ and "Transfer" in str(occ):
        nurse_status["Transferring"] += 1
      elif occ and "Resting" in str(occ):
        nurse_status["Resting"] += 1
      elif "Monitoring" in desc or "Patient" in str(occ):
        nurse_status["Monitoring"] += 1
      elif occ is None and (p.scratch.planned_path or "Standing by" in desc):
        nurse_status["Available"] += 1
      elif occ is None:
        nurse_status["Available"] += 1
      else:
        nurse_status["Other"] += 1

    # --- Completed patients count ---
    completed_csv = f"{sim_folder}/reverie/completed_patient_stage_times.csv"
    try:
      with open(completed_csv, "r") as f:
        completed = max(0, sum(1 for _ in f) - 1)  # minus header
    except FileNotFoundError:
      completed = 0

    # --- Build output ---
    elapsed = self.step * self.sec_per_step
    hours = elapsed // 3600
    mins  = (elapsed % 3600) // 60

    lines = []
    lines.append("=" * 60)
    lines.append(f"  ED SIMULATION STATUS  —  Step {self.step}")
    lines.append("=" * 60)
    lines.append(f"  Sim time : {self.curr_time.strftime('%b %d %Y  %H:%M')}"
                 f"   (elapsed {hours}h {mins}m)")
    lines.append(f"  Patients : {total_patients} in ED  |  "
                 f"{completed} completed  |  {left_ed} left ED")
    lines.append("")
    lines.append("  PATIENT STATES")
    lines.append("  " + "-" * 40)
    for st in ["WAITING_FOR_TRIAGE", "TRIAGE", "WAITING_FOR_NURSE",
               "WAITING_FOR_FIRST_ASSESSMENT", "WAITING_FOR_TEST",
               "GOING_FOR_TEST", "WAITING_FOR_RESULT",
               "WAITING_FOR_DOCTOR", "WAITING_FOR_EXIT",
               "ADMITTED_BOARDING", "DISCHARGED_WAITING",
               "LEAVING", "UNKNOWN"]:
      cnt = state_counts.get(st, 0)
      if cnt > 0:
        lines.append(f"    {st:<35s} {cnt:>4}")
    lines.append("")
    lines.append("  ZONE OCCUPANCY  (current / capacity)")
    lines.append("  " + "-" * 40)
    lines.extend(zone_lines)
    lines.append("")
    lines.append("  QUEUES")
    lines.append("  " + "-" * 40)
    lines.append(f"    Triage queue              {triage_q:>4}")
    lines.append(f"    Bedside nurse waiting     {nurse_q:>4}")
    lines.append(f"    Pager (CTAS 1)            {pager_q:>4}")
    lines.append(f"    Doctor global queue        {doctor_global_q:>4}")
    lines.append("")
    lines.append(f"  NURSES  (20 total)")
    lines.append("  " + "-" * 40)
    for label, cnt in nurse_status.items():
      if cnt > 0:
        lines.append(f"    {label:<25s} {cnt:>4}")
    lines.append("")
    lines.append(f"  DOCTORS  ({len(doctor_assigned)} total, "
                 f"{doctors_free} accepting patients)")
    lines.append("  " + "-" * 40)
    for dname, n in sorted(doctor_assigned.items(),
                            key=lambda x: int(x[0].split()[-1])):
      lines.append(f"    {dname:<20s}  {n} / {Doctor.max_patients} assigned")
    lines.append("")
    lines.append("=" * 60)
    lines.append("")

    status_path = f"{sim_folder}/sim_status.txt"
    with open(status_path, "w") as f:
      f.write("\n".join(lines))

    # --- Write machine-readable JSON for the live dashboard ---
    # Total patients ever processed (including those who already left)
    total_processed = len(self.data_collection.get("Patient", {}))

    status_json = {
      "step": self.step,
      "sim_time": self.curr_time.strftime('%b %d %Y  %H:%M'),
      "elapsed_hours": int(hours),
      "elapsed_mins": int(mins),
      "current_patients": total_patients,
      "total_patients": total_processed,
      "completed": completed,
      "left_ed": left_ed,
      "patient_states": state_counts,
      "zone_occupancy": {},
      "queues": {
        "triage": triage_q,
        "bedside_nurse_waiting": nurse_q,
        "pager": pager_q,
        "doctor_global": doctor_global_q,
      },
      "nurse_status": nurse_status,
      "doctor_assigned": doctor_assigned,
      "doctors_total": len(doctor_assigned),
      "doctors_accepting": doctors_free,
      "doctor_max_patients": Doctor.max_patients,
    }
    for zone_name in ["trauma room", "major injuries zone",
                       "minor injuries zone", "diagnostic room"]:
      info = self.maze.injuries_zones.get(zone_name, {})
      if isinstance(info, dict):
        status_json["zone_occupancy"][zone_name] = {
          "current": len(info.get("current_patients", [])),
          "capacity": info.get("capacity", 0),
        }

    json_path = f"{sim_folder}/sim_status.json"
    tmp_path = json_path + ".tmp"
    with open(tmp_path, "w") as f:
      json.dump(status_json, f)
    os.replace(tmp_path, json_path)

  # States where time IS travel (walking to exit) — don't subtract travel.
  _TRAVEL_EXEMPT_STATES = {"LEAVING"}

  def _apply_travel_time_adjustments(self, data_collection):
    """
    Subtract tracked travel time from patient time_spent_state/time_spent_area.
    Intended for use on a snapshot of data_collection during save.
    States in _TRAVEL_EXEMPT_STATES are skipped because their entire
    duration is purposeful movement (e.g. walking to the exit).
    """
    patients = data_collection.get("Patient", {})
    for persona_data in patients.values():
      if not isinstance(persona_data, dict):
        continue

      travel_state = persona_data.get("travel_time_state", {})
      if isinstance(travel_state, dict) and travel_state:
        time_state = persona_data.get("time_spent_state", {})
        for state, travel_minutes in travel_state.items():
          if travel_minutes is None:
            continue
          if state in self._TRAVEL_EXEMPT_STATES:
            continue
          current = time_state.get(state, 0)
          adjusted = current - travel_minutes
          time_state[state] = adjusted if adjusted > 0 else 0
        persona_data["time_spent_state"] = time_state

      travel_area = persona_data.get("travel_time_area", {})
      if isinstance(travel_area, dict) and travel_area:
        time_area = persona_data.get("time_spent_area", {})
        for area, travel_minutes in travel_area.items():
          if travel_minutes is None:
            continue
          current = time_area.get(area, 0)
          adjusted = current - travel_minutes
          time_area[area] = adjusted if adjusted > 0 else 0
        persona_data["time_spent_area"] = time_area

  @staticmethod
  def _patient_should_export_completed_stage(persona_data):
    """
    Return True for non-preloaded patients that completed care and left the ED.
    Excludes walk-outs by choice.
    """
    if persona_data.get("exempt_from_data_collection", False):
      return False

    walkout = persona_data.get("left_department_by_choice", {})
    if isinstance(walkout, dict) and walkout.get("occurred", False):
      return False

    time_state = persona_data.get("time_spent_state", {}) or {}
    s1, s2, s3 = ReverieServer._compute_real_stage_minutes(time_state)
    return s1 > 0 and s2 > 0 and s3 > 0

  @staticmethod
  def _compute_real_stage_minutes(time_spent_state):
    stage1_states = [
      "WAITING_FOR_TRIAGE",
      "TRIAGE",
      "WAITING_FOR_NURSE",
      "WAITING_FOR_FIRST_ASSESSMENT",
    ]
    stage2_states = [
      "WAITING_FOR_TEST",
      "GOING_FOR_TEST",
      "WAITING_FOR_RESULT",
      "WAITING_FOR_DOCTOR",
    ]
    stage3_states = ["WAITING_FOR_EXIT", "LEAVING"]

    def _sum_states(states):
      return float(sum(float(time_spent_state.get(state, 0) or 0) for state in states))

    return _sum_states(stage1_states), _sum_states(stage2_states), _sum_states(stage3_states)

  @staticmethod
  def _extract_original_stage_targets(persona_name, persona_data, sim_folder):
    def _coerce_minutes(value):
      if value is None:
        return None
      try:
        return float(value)
      except (TypeError, ValueError):
        return None

    stage1 = _coerce_minutes(persona_data.get("stage1_minutes"))
    stage2 = _coerce_minutes(persona_data.get("stage2_minutes"))
    stage3 = _coerce_minutes(persona_data.get("stage3_minutes"))

    if stage1 is not None and stage2 is not None and stage3 is not None:
      return stage1, stage2, stage3

    scratch_file = f"{sim_folder}/personas/{persona_name}/bootstrap_memory/scratch.json"
    if os.path.exists(scratch_file):
      loaded, scratch_payload = ReverieServer._try_load_json_file(scratch_file)
      if loaded and isinstance(scratch_payload, dict):
        if stage1 is None:
          base = _coerce_minutes(scratch_payload.get("stage1_minutes")) or 0.0
          extra = _coerce_minutes(scratch_payload.get("stage1_surge_extra")) or 0.0
          stage1 = base + extra
        if stage2 is None:
          base = _coerce_minutes(scratch_payload.get("stage2_minutes")) or 0.0
          extra = _coerce_minutes(scratch_payload.get("stage2_surge_extra")) or 0.0
          stage2 = base + extra
        if stage3 is None:
          stage3 = _coerce_minutes(scratch_payload.get("stage3_minutes"))

    return (
      stage1 if stage1 is not None else 0.0,
      stage2 if stage2 is not None else 0.0,
      stage3 if stage3 is not None else 0.0,
    )

  def save(self): 
    """
    Save all Reverie progress -- this includes Reverie's global state as well
    as all the personas.  

    INPUT
      None
    OUTPUT 
      None
      * Saves all relevant data to the designated memory directory
    """
    # <sim_folder> points to the current simulation folder.
    sim_folder = f"{fs_storage}/{self.sim_code}"
    reverie_meta_f = f"{sim_folder}/reverie/meta.json"
    reverie_maze_f = f"{sim_folder}/reverie/maze_status.json"

    # Save Reverie meta information.
    reverie_meta = json.load(open(reverie_meta_f))
    reverie_meta["fork_sim_code"] = self.fork_sim_code
    reverie_meta["start_date"] = self.start_time.strftime("%B %d, %Y")
    reverie_meta["curr_time"] = self.curr_time.strftime("%B %d, %Y, %H:%M:%S")
    reverie_meta["sec_per_step"] = self.sec_per_step
    reverie_meta["maze_name"] = self.maze.maze_name
    reverie_meta["patient_walkout_probability"] = self.patient_walkout_probability
    reverie_meta["patient_walkout_check_minutes"] = self.patient_walkout_check_minutes
    reverie_meta["patient_post_discharge_linger_probability"] = self.patient_post_discharge_linger_probability
    reverie_meta["patient_post_discharge_linger_minutes"] = self.patient_post_discharge_linger_minutes
    reverie_meta["patient_rate_modifier"] = self.patient_rate
    reverie_meta["add_patient_threshold"] = self.add_patient_threshold
    reverie_meta["doctor_starting_amount"] = self.doctor_starting_amount
    reverie_meta["triage_starting_amount"] = self.triage_starting_amount
    reverie_meta["bedside_starting_amount"] = self.bedside_starting_amount
    reverie_meta["fill_injuries"] = self.fill_injuries
    reverie_meta["seed"] = self.seed
    reverie_meta["priority_boost_interval_minutes"] = self._boost_interval_minutes
    reverie_meta["global_queue_aging_interval_minutes"] = self._global_queue_aging_interval
    reverie_meta["preload_departure_window_hours"] = self._preload_departure_window_hours
    reverie_meta["diagnostic_room_capacity"] = self.diagnostic_room_capacity
    reverie_meta["testing_probability_by_ctas"] = Patient.testing_probability_by_ctas
    reverie_meta["preload_waiting_room_patients"] = self.preload_waiting_room_patients
    reverie_meta["simulate_hospital_admission"] = self.simulate_hospital_admission
    reverie_meta["admission_probability_by_ctas"] = self.admission_probability_by_ctas
    reverie_meta["admission_boarding_minutes_min"] = self.admission_boarding_minutes_min
    reverie_meta["admission_boarding_minutes_max"] = self.admission_boarding_minutes_max

    # Save name and role into meta file
    persona_list = []
    for p_name in self.personas.keys():
      p = self.personas[p_name]
      persona_list.append([p.name,p.role])

    reverie_meta["persona_names"] = persona_list
    reverie_meta["step"] = self.step
    _atomic_write_json(reverie_meta_f, reverie_meta)

    # In headless mode, write the environment file for the current step so that
    # the next safe-mode chunk can bootstrap from it in __init__.
    if self.headless:
      env_dir = f"{sim_folder}/environment"
      env_data = {}
      for p_name, tile in self.personas_tile.items():
        env_data[p_name] = {"maze": "Emergency Department",
                            "x": tile[0], "y": tile[1]}
      _atomic_write_json(f"{env_dir}/{self.step}.json", env_data)

    # Save the personas.
    for persona_name, persona in self.personas.items(): 
      save_folder = f"{sim_folder}/personas/{persona_name}/bootstrap_memory"
      persona.save(save_folder)
      self.data_collection[persona.role][persona_name] = persona.save_data(self.data_collection[persona.role][persona_name])

    # Save maze variables
    self.maze.save(reverie_maze_f)

    data_collection_output = copy.deepcopy(self.data_collection)
    data_collection_output.setdefault("summarized_by_ctas", {})
    self._apply_travel_time_adjustments(data_collection_output)

    # Start with a blank slate in each ctas score from 1 to 5
    for i in range(0,6):
      data_collection_output["summarized_by_ctas"][str(i)] = {        
        "num_of_patients": 0,
        "percentage_of_total": 0,

        "total":{
          "time_spent_area":{},
          "time_spent_state":{}
        },
        "normalized":{
          "time_spent_area":{},
          "time_spent_state":{}
        },
        "standard_deviation": {
          "time_spent_area":{},
          "time_spent_state":{}
        }
      }
      

    # For CSV file so that we know how many states and areas need to be filled to make a CSV file
    # DataFrame so that when we add new Patient's to the data and don't have certain fields they are filled with NaN
    state_times_csv = pd.DataFrame()
    area_times_csv = pd.DataFrame()
    completed_stage_times_csv = pd.DataFrame()
    ed_metrics_csv = pd.DataFrame()


    std_states = {}
    std_areas = {}
    required_states = [
      "WAITING_FOR_TRIAGE",
      "TRIAGE",
      "WAITING_FOR_NURSE",
      "WAITING_FOR_FIRST_ASSESSMENT",
      "WAITING_FOR_TEST",
      "GOING_FOR_TEST",
      "WAITING_FOR_RESULT",
      "WAITING_FOR_DOCTOR",
      "ADMITTED_BOARDING",
      "LEAVING"
    ]

    # Put data in groups sorted by CTAS score
    for name,persona_data in data_collection_output["Patient"].items():
      if persona_data["exempt_from_data_collection"]:
        continue
      if(not persona_data["CTAS_score"] ):
        persona_data["CTAS_score"] = 0

      ctas_dict = data_collection_output["summarized_by_ctas"][str(persona_data["CTAS_score"])]
      # Total amount of Patients with certain CTAS
      ctas_dict["num_of_patients"] += 1

      # Number of Patients in each zone
      if(persona_data["injuries_zone"] in ctas_dict.keys()):
        ctas_dict[persona_data["injuries_zone"]] += 1
      else:
        ctas_dict[persona_data["injuries_zone"]] = 1


      ctas_dict_total = data_collection_output["summarized_by_ctas"][str(persona_data["CTAS_score"])]["total"]

      # Grab totals of time spent in area for a CTAS score
      for area, time in persona_data["time_spent_area"].items():
        if(area not in ctas_dict_total["time_spent_area"].keys()):
          ctas_dict_total["time_spent_area"][area] = time
          std_areas[area] = [time]

        else:
          ctas_dict_total["time_spent_area"][area] += time
          std_areas[area].append(time)


      # Grab totals of time spent in a state for a CTAS score
      for state, time in persona_data["time_spent_state"].items():
        if(state not in ctas_dict_total["time_spent_state"].keys()):
          ctas_dict_total["time_spent_state"][state] = time
          std_states[state] = [time]
        else:
          ctas_dict_total["time_spent_state"][state] += time
          std_states[state].append(time)

      base_entry = {"name": [name], "CTAS": [persona_data["CTAS_score"]]}

      # CSV compiling
      # Ensure all required states exist as columns with a default of 0
      state_entry = {
        **base_entry,
        **{state: [persona_data["time_spent_state"].get(state, 0)] for state in required_states}
      }
      # Preserve any additional states that may be present for debugging
      for state_name, time in persona_data["time_spent_state"].items():
        if state_name not in state_entry:
          state_entry[state_name] = [time]
      leaving_time = float(persona_data["time_spent_state"].get("LEAVING", 0) or 0)
      state_entry["left_ED"] = [leaving_time > 0]
      state_entry = pd.DataFrame(state_entry)

      # Add entry to total csv list
      state_times_csv = pd.concat([state_entry, state_times_csv],ignore_index=True)

      # Area data
      time_entry = {"name": [name], "CTAS": [persona_data["CTAS_score"]]}

      time_entry.update(persona_data["time_spent_area"])
      time_entry = pd.DataFrame(time_entry)
      area_times_csv = pd.concat([time_entry, area_times_csv], ignore_index=True)

      if self._patient_should_export_completed_stage(persona_data):
        time_spent_state = persona_data.get("time_spent_state", {}) or {}
        real_stage1, real_stage2, real_stage3 = self._compute_real_stage_minutes(time_spent_state)
        original_stage1, original_stage2, original_stage3 = self._extract_original_stage_targets(
          name, persona_data, sim_folder
        )

        completed_stage_entry = pd.DataFrame({
          "name": [name],
          "CTAS": [persona_data["CTAS_score"]],
          "real_stage1_minutes": [real_stage1],
          "real_stage2_minutes": [real_stage2],
          "real_stage3_minutes": [real_stage3],
          "original_stage1_minutes": [original_stage1],
          "original_stage2_minutes": [original_stage2],
          "original_stage3_minutes": [original_stage3],
        })
        completed_stage_times_csv = pd.concat(
          [completed_stage_entry, completed_stage_times_csv],
          ignore_index=True
        )

      # ED metrics row
      tss = persona_data.get("time_spent_state", {}) or {}
      door_to_doctor = sum(float(tss.get(s, 0) or 0) for s in [
          "WAITING_FOR_TRIAGE", "TRIAGE", "WAITING_FOR_NURSE", "WAITING_FOR_FIRST_ASSESSMENT"])
      length_of_stay = sum(float(v or 0) for v in tss.values())
      treatment_time = sum(float(tss.get(s, 0) or 0) for s in [
          "WAITING_FOR_TEST", "GOING_FOR_TEST", "WAITING_FOR_RESULT"])
      boarding_time = float(tss.get("ADMITTED_BOARDING", 0) or 0)

      lwbs_data = persona_data.get("left_department_by_choice", {}) or {}
      lwbs_occurred = lwbs_data.get("occurred", False)
      lwbs_wait = lwbs_data.get("wait_minutes") if lwbs_occurred else None

      admit_data = persona_data.get("admitted_to_hospital", {}) or {}
      admitted = admit_data.get("occurred", False)

      linger_data = persona_data.get("lingered_after_discharge", {}) or {}
      lingered = linger_data.get("occurred", False)

      completed = (leaving_time > 0) and not lwbs_occurred

      metrics_entry = pd.DataFrame({
          "name": [name],
          "CTAS": [persona_data["CTAS_score"]],
          "ICD_code": [persona_data.get("ICD-10-CA_code", "")],
          "injuries_zone": [persona_data.get("injuries_zone", "")],
          "door_to_doctor_minutes": [door_to_doctor],
          "length_of_stay_minutes": [length_of_stay],
          "treatment_time_minutes": [treatment_time],
          "boarding_time_minutes": [boarding_time],
          "left_without_being_seen": [lwbs_occurred],
          "lwbs_wait_minutes": [lwbs_wait],
          "admitted_to_hospital": [admitted],
          "lingered_after_discharge": [lingered],
          "completed_treatment": [completed],
          "stage1_target_minutes": [persona_data.get("stage1_minutes")],
          "stage2_target_minutes": [persona_data.get("stage2_minutes")],
          "stage3_target_minutes": [persona_data.get("stage3_minutes")],
      })
      ed_metrics_csv = pd.concat([metrics_entry, ed_metrics_csv], ignore_index=True)

    # Use averages per patient in each CTAS score
    for data in data_collection_output["summarized_by_ctas"].values():
      # If there is no patients with CTAS score skip
      if(data["num_of_patients"] == 0):
        continue
      
      # Find percentage of patients with CTAS from the total patient count
      data["percentage_of_total"] = float((data["num_of_patients"]  * 100) // self.num_roles["Patient"]) 

      # Normalize amount for area time spent
      for key, total in data["total"]["time_spent_area"].items():
        data["normalized"]["time_spent_area"][key] = total // data["num_of_patients"]
        data["standard_deviation"]["time_spent_area"][key] = np.std(std_areas[key])

      # Normalize amount for state time spent
      for key, total in data["total"]["time_spent_state"].items():
        data["normalized"]["time_spent_state"][key] = total // data["num_of_patients"]
        data["standard_deviation"]["time_spent_state"][key] = np.std(std_states[key])

    # Persist the RAW (unadjusted) data so that travel-time subtraction
    # is not applied cumulatively across safe-mode restart cycles.
    # The adjusted copy (data_collection_output) is only used for CSV export.
    with open(f"{sim_folder}/reverie/data_collection.json", "w") as outfile:
      outfile.write(json.dumps(self.data_collection, indent=2))


    # Save state and areas to different for better seperation
    state_times_csv.to_csv(f'{sim_folder}/reverie/state_times.csv', index=False)
    area_times_csv.to_csv(f'{sim_folder}/reverie/area_times.csv', index=False)
    completed_stage_times_csv.to_csv(
      f'{sim_folder}/reverie/completed_patient_stage_times.csv',
      index=False
    )
    ed_metrics_csv.to_csv(f'{sim_folder}/reverie/ed_metrics.csv', index=False)


  def start_path_tester_server(self): 
    """
    Starts the path tester server. This is for generating the spatial memory
    that we need for bootstrapping a persona's state. 

    To use this, you need to open server and enter the path tester mode, and
    open the front-end side of the browser. 

    INPUT 
      None
    OUTPUT 
      None
      * Saves the spatial memory of the test agent to the path_tester_env.json
        of the temp storage. 
    """
    def print_tree(tree): 
      def _print_tree(tree, depth):
        dash = " >" * depth

        if type(tree) == type(list()): 
          if tree:
            print (dash, tree)
          return 

        for key, val in tree.items(): 
          if key: 
            print (dash, key)
          _print_tree(val, depth+1)
      
      _print_tree(tree, 0)

    # <curr_vision> is the vision radius of the test agent. Recommend 8 as 
    # our default. 
    curr_vision = 8
    # <s_mem> is our test spatial memory. 
    s_mem = dict()

    # The main while loop for the test agent. 
    while (True): 
      try: 
        curr_dict = {}
        tester_file = fs_temp_storage + "/path_tester_env.json"
        if check_if_file_exists(tester_file): 
          with open(tester_file) as json_file: 
            curr_dict = json.load(json_file)
            os.remove(tester_file)
          
          # Current camera location
          curr_sts = self.maze.sq_tile_size
          curr_camera = (int(math.ceil(curr_dict["x"]/curr_sts)), 
                         int(math.ceil(curr_dict["y"]/curr_sts))+1)
          curr_tile_det = self.maze.access_tile(curr_camera)

          # Initiating the s_mem
          world = curr_tile_det["world"]
          if curr_tile_det["world"] not in s_mem: 
            s_mem[world] = dict()

          # Iterating throughn the nearby tiles.
          nearby_tiles = self.maze.get_nearby_tiles(curr_camera, curr_vision)
          for i in nearby_tiles: 
            i_det = self.maze.access_tile(i)
            if (curr_tile_det["sector"] == i_det["sector"] 
                and curr_tile_det["arena"] == i_det["arena"]): 
              if i_det["sector"] != "": 
                if i_det["sector"] not in s_mem[world]: 
                  s_mem[world][i_det["sector"]] = dict()
              if i_det["arena"] != "": 
                if i_det["arena"] not in s_mem[world][i_det["sector"]]: 
                  s_mem[world][i_det["sector"]][i_det["arena"]] = list()
              if i_det["game_object"] != "": 
                if (i_det["game_object"] 
                    not in s_mem[world][i_det["sector"]][i_det["arena"]]):
                  s_mem[world][i_det["sector"]][i_det["arena"]] += [
                                                         i_det["game_object"]]

        # Incrementally outputting the s_mem and saving the json file. 
        print ("= " * 15)
        out_file = fs_temp_storage + "/path_tester_out.json"
        with open(out_file, "w") as outfile: 
          outfile.write(json.dumps(s_mem, indent=2))
        print_tree(s_mem)

      except:
        pass

      time.sleep(self.server_sleep * 10)

  def add_patient_in_bed(self, symptoms, position_loc,zone, symptoms_index,):
    """Adds a Patient persona directly into a bed in the specified injuries zone.
    This is used for filling up injuries zones at the start of the simulation."""
    
    curr_patient, curr_tile = self.add_persona_to_sim(
        "Patient",
        f"""Experiencing {symptoms} |
                For CTAS field pick a number from 1 to 5 based on symptoms of the patient. 1 being severe and 5 being not urgent""",
        position_loc,
    )
    # Mark filler patients as exempt programmatically (not via GPT prompt).
    # Must also update the data_collection entry since it was created by
    # add_persona_to_sim before the flag was set on the scratch.
    curr_patient.scratch.exempt_from_data_collection = True
    dc_entry = self.data_collection.get("Patient", {}).get(curr_patient.name)
    if dc_entry is not None:
      dc_entry["exempt_from_data_collection"] = True
    _assign_wait_targets(curr_patient, self.ctas_wait_config, self.curr_time, self.surge_multiplier)


    self.add_persona_to_step(curr_patient, curr_tile)

    # Set the Patient data to the correct states for the injuries zones
    curr_patient.scratch.injuries_zone = zone
    curr_patient.scratch.ICD = self.symptoms['ICD-10-CA'][symptoms_index]
    curr_patient.scratch.act_path_set = True
    bed_target = self.maze.assign_bed(curr_patient.name, zone, position_loc)
    if bed_target:
      curr_patient.scratch.bed_assignment = list(bed_target)
    bed_address = (self.maze.get_bed_address(zone, bed_target)
                   if bed_target else f"ed map:emergency department:{zone}:bed")
    curr_patient.scratch.next_step = f"<tile> {bed_target}"
    curr_patient.scratch.act_address = f"<tile> {bed_target}"
    curr_patient.scratch.CTAS = int(self.symptoms["CTAS"][symptoms_index])

    # Add them to the injuries zone array to keep track of Patients
    self.maze.injuries_zones[zone]["current_patients"].append(curr_patient.name)

    # Assign a Patient randomly at which stage they are at in the injuries zone
    states = ["WAITING_FOR_FIRST_ASSESSMENT", "WAITING_FOR_TEST", "WAITING_FOR_DOCTOR", "WAITING_FOR_RESULT"]

    choosen_state = random.choice(states)
    curr_patient.scratch.state = choosen_state = choosen_state
    # Staged waits assume initial assessment will happen after the wait threshold
    if choosen_state != "WAITING_FOR_TRIAGE":
      curr_patient.scratch.initial_assessment_ready_at = max(
        curr_patient.scratch.initial_assessment_ready_at or self.curr_time,
        self.curr_time)
    
    doctor_taking_patients = self.maze.doctors_taking_more_patients
    assessment_queue = None
    if(doctor_taking_patients != []):
      doctor_name = random.choice(doctor_taking_patients)
      doctor = self.personas.get(doctor_name)
      if doctor:
        curr_patient.scratch.assigned_doctor = doctor_name
        assessment_queue = doctor.scratch.assigned_patients_waitlist
        doctor.assign_patient(doctor_taking_patients, curr_patient, self.personas)
    
    if(assessment_queue is None):
      curr_patient.scratch.state = choosen_state = "WAITING_FOR_FIRST_ASSESSMENT"
      bisect.insort_right(self.maze.patients_waiting_for_doctor, [curr_patient.scratch.CTAS * Patient.priority_factor, curr_patient.name])

    # Find state it has selected and make sure all Patient variables are properly set so there is no errors
    if(choosen_state == "WAITING_FOR_FIRST_ASSESSMENT"):
      if ((not curr_patient.scratch.initial_assessment_ready_at or self.curr_time >= curr_patient.scratch.initial_assessment_ready_at) 
          and assessment_queue is not None):
        assessment_queue.append([curr_patient.scratch.CTAS * Patient.priority_factor, curr_patient.name])

    elif(choosen_state == "WAITING_FOR_TEST"):
      # Preloaded patients skip diagnostic room - go straight to WAITING_FOR_RESULT
      curr_patient.scratch.state = "WAITING_FOR_RESULT"
      curr_patient.scratch.initial_assessment_done = True
      curr_patient.scratch.time_to_next = self.curr_time + datetime.timedelta(
          minutes=random.randint(1, Patient.testing_result_time))
      if curr_patient.scratch.disposition_ready_at is None:
        curr_patient.scratch.disposition_ready_at = self.curr_time + datetime.timedelta(minutes=float(curr_patient.scratch.stage2_minutes or 0) + float(curr_patient.scratch.stage2_surge_extra or 0))

    elif(choosen_state == "WAITING_FOR_DOCTOR"):
      curr_patient.scratch.initial_assessment_done = True
      if curr_patient.scratch.disposition_ready_at is None:
        curr_patient.scratch.disposition_ready_at = self.curr_time
      #if self.curr_time >= (curr_patient.scratch.disposition_ready_at or self.curr_time) and assessment_queue:
      assessment_queue.append([curr_patient.scratch.CTAS * (Patient.priority_factor // 2), curr_patient.name])

    elif(choosen_state == "WAITING_FOR_RESULT"):
      curr_patient.scratch.time_to_next = self.curr_time + datetime.timedelta(minutes=random.randint(1, Patient.testing_result_time))
      curr_patient.scratch.initial_assessment_done = True
      if curr_patient.scratch.disposition_ready_at is None:
        curr_patient.scratch.disposition_ready_at = self.curr_time + datetime.timedelta(minutes=float(curr_patient.scratch.stage2_minutes or 0) + float(curr_patient.scratch.stage2_surge_extra or 0))

    # Assign a randomized departure deadline so this preloaded patient
    # eventually vacates the bed, staggered across the configured window.
    # Minimum 30 minutes so patients don't depart immediately after setup.
    min_offset = 30
    max_offset = self._preload_departure_window_hours * 60
    departure_offset_minutes = random.uniform(min_offset, max(min_offset, max_offset))
    curr_patient.scratch.preload_departure_at = self.curr_time + datetime.timedelta(minutes=departure_offset_minutes)

    # Add Patient to the data collection dict
    if(curr_patient.name not in self.data_collection[curr_patient.role].keys()):
      temp_dict = curr_patient.data_collection_dict()

      self.data_collection[curr_patient.role][curr_patient.name] = temp_dict

  def _preload_waiting_room(self):
    """Spawn real patients into the waiting room at simulation start.

    Unlike filler patients (add_patient_in_bed), these are NOT exempt from
    data collection and go through the full triage flow like dynamically
    spawned patients."""
    count = self.preload_waiting_room_patients
    if not count or count <= 0:
      return

    # Only run once
    self.preload_waiting_room_patients = 0

    for i in range(int(count)):
      symptoms = numpy.random.choice(self.symptoms["Symptoms"], 1, p=self.symptoms["normalized_fraction"])
      symptoms_index = self.symptoms["Symptoms"].index(symptoms)
      innates = ["Impatient, Friendly", "Unstable, Friendly"]
      choosen_innate = random.choice(innates)

      new_patient, curr_tile = self.add_persona_to_sim(
        "Patient",
        f"Experiencing {symptoms} | Innate: {choosen_innate}",
        persona_loc=random.choice(list(self.maze.address_tiles["<spawn_loc>exit"]))
      )

      self.add_persona_to_step(new_patient, curr_tile)

      new_patient.scratch.ICD = self.symptoms["ICD-10-CA"][symptoms_index]
      new_patient.scratch.CTAS = int(self.symptoms["CTAS"][symptoms_index])
      new_patient.scratch.injuries_zone = self.symptoms["Zone"][symptoms_index]

      # Add to triage queue so triage nurse picks them up
      self.maze.triage_queue.append(new_patient.name)

    print(f"(reverie): Preloaded {count} real patients into the waiting room")

  def start_server(self, int_counter):
    """
    The main backend server of Reverie. 
    This function retrieves the environment file from the frontend to 
    understand the state of the world, calls on each personas to make 
    decisions based on the world state, and saves their moves at certain step
    intervals. 
    INPUT
      int_counter: Integer value for the number of steps left for us to take
                   in this iteration. 
    OUTPUT 
      None
    """

    # Adding more personas before simualation
    # According to the amounts set in the meta json add the right amount of medical staff
    for i in range(self.doctor_starting_amount - self.num_roles["Doctor"]):
      new_persona, pos = self.add_persona_to_sim("Doctor")
      self.add_persona_to_step(new_persona, pos)
      self.maze.doctors_taking_more_patients.append(new_persona.name)

    for i in range(self.bedside_starting_amount - self.num_roles["BedsideNurse"]):
      new_persona, pos = self.add_persona_to_sim("BedsideNurse")
      self.add_persona_to_step(new_persona, pos)

    for i in range(self.triage_starting_amount - self.num_roles["TriageNurse"]):
      new_persona, pos = self.add_persona_to_sim("TriageNurse")
      self.add_persona_to_step(new_persona, pos)


    # Add Patients to fill up a fraction of the injuries zones capacity
    if(self.fill_injuries > 0):
      # So we don't keep filling injuries zones if the user only wants it for one round of steps
      fill_fraction = self.fill_injuries
      self.fill_injuries = 0

      # Grab variables set in the meta.json file
      sim_folder = f"{fs_storage}/{self.sim_code}"

      # Iterate over the injuries zones
      zones = ["minor injuries zone", "major injuries zone"]
      for zone in zones:
        available = self.maze.injuries_zones[zone]["capacity"] - len(self.maze.injuries_zones[zone]["current_patients"])
        beds_to_fill = int(self.maze.injuries_zones[zone]["capacity"] * fill_fraction) - len(self.maze.injuries_zones[zone]["current_patients"])
        beds_to_fill = max(0, min(beds_to_fill, available))
        for i in range(beds_to_fill):
          # Select symptom based on probabilities
          position_loc = list(self.maze.address_tiles[f"ed map:emergency department:{zone}:bed"])[i]

          curr_tile_ev = self.maze.tiles[position_loc[1]][position_loc[0]]["events"]
          for event in curr_tile_ev:
            if "Patient" in event:
              continue

          symptoms = numpy.random.choice(self.symptoms["Symptoms"], 1, p=self.symptoms["normalized_fraction"])
          symptoms_index = self.symptoms["Symptoms"].index(symptoms)
          self.add_patient_in_bed(symptoms[0], position_loc, zone, symptoms_index)

    # Preload real patients into the waiting room (counted in data collection)
    self._preload_waiting_room()

    # # If the waiting room has stranded patients, make sure they get enqueued for triage
    # if not self.maze.triage_queue:
    #   for persona_name, persona in self.personas.items():
    #     if persona.role == "Patient" and persona.scratch.state == "WAITING_FOR_TRIAGE":
    #       # Skip if already queued (safety) or marked as exempt from intake
    #       if persona_name not in self.maze.triage_queue and not getattr(persona.scratch, "exempt_from_data_collection", False):
    #         self.maze.triage_queue.append(persona_name)

    # # Keep triage capacity accounting in sync with the actual patients being triaged
    # self.maze.triage_patients = sum(
    #   1 for persona in self.personas.values()
    #   if getattr(persona, "role", None) == "Patient" and persona.scratch.state == "TRIAGE"
    # )

    # # Recover bedside nurse queue for patients already cleared from triage but not yet escorted
    # if not self.maze.injuries_zones["bedside_nurse_waiting"]:
    #   for persona in self.personas.values():
    #     if getattr(persona, "role", None) == "Patient" and persona.scratch.state == "WAITING_FOR_NURSE":
    #       ctas_val = persona.scratch.CTAS if getattr(persona.scratch, "CTAS", None) is not None else 3
    #       priority = ctas_val * Triage_Nurse.priority_factor
    #       bisect.insort_right(
    #         self.maze.injuries_zones["bedside_nurse_waiting"],
    #         [priority, persona.name]
    #       )

    # <sim_folder> points to the current simulation folder.
    sim_folder = f"{fs_storage}/{self.sim_code}"

    # When a persona arrives at a game object, we give a unique event
    # to that object. 
    # e.g., ('double studio[...]:bed', 'is', 'unmade', 'unmade')
    # Later on, before this cycle ends, we need to return that to its 
    # initial state, like this: 
    # e.g., ('double studio[...]:bed', None, None, None)
    # So we need to keep track of which event we added. 
    # <game_obj_cleanup> is used for that. 
    game_obj_cleanup = dict()

    # The main while loop of Reverie.
    while (True):
      # Done with this iteration if <int_counter> reaches 0.
      if int_counter == 0:
        break

      # --- Determine the environment snapshot for this step ---
      env_retrieved = False
      new_env = None

      if self.headless:
        # Headless mode: build environment directly from current tile positions
        # instead of waiting for frontend file I/O.
        new_env = {}
        for p_name, tile in self.personas_tile.items():
          new_env[p_name] = {"x": tile[0], "y": tile[1]}
        env_retrieved = True
      else:
        # Normal mode: poll for the environment file written by the frontend.
        curr_env_file = f"{sim_folder}/environment/{self.step}.json"
        if check_if_file_exists(curr_env_file):
          env_retrieved, new_env = self._try_load_json_file(curr_env_file)

      if env_retrieved: 
          # This is where we go through <game_obj_cleanup> to clean up all 
          # object actions that were used in this cylce. 
          for key, val in game_obj_cleanup.items(): 
            # We turn all object actions to their blank form (with None). 
            self.maze.turn_event_from_tile_idle(key, val)
          # Then we initialize game_obj_cleanup for this cycle. 
          game_obj_cleanup = dict()

          # Track the patients that are in the exit area and leaving
          leaving_patient = []

          # We first move our personas in the backend environment to match 
          # the frontend environment. 
          for persona_name, persona in list(self.personas.items()): 
            # <curr_tile> is the tile that the persona was at previously. 
            curr_tile = self.personas_tile.get(persona_name)
            if curr_tile is None:
              print(f"(reverie): Warning - missing tile entry for {persona_name}, skipping movement update")
              continue
            print(persona_name)

            # Check if patient is in the exit are and actually leaving the ED 
            if(self.maze.tiles[curr_tile[1]][curr_tile[0]]['arena'] == "exit" and 
               persona.scratch.next_step == "ed map:emergency department:exit"):
              
              leaving_patient.append(persona)
              # Free up any bed space the patient was occupying
              if hasattr(persona, "_release_bed"):
                persona._release_bed(self.maze)
              # Remove them from the tile events
              self.maze.remove_subject_events_from_tile(persona.name, curr_tile)
              continue

            # <new_tile> is the tile that the persona will move to right now,
            # during this cycle. 
            env_entry = new_env.get(persona_name)
            if env_entry is None:
              print(f"(reverie): Warning - missing environment snapshot for {persona_name}, skipping movement update")
              continue
            new_tile = (env_entry["x"], 
                        env_entry["y"])
            
            # We actually move the persona on the backend tile map here. 
            self.personas_tile[persona_name] = new_tile
            self.maze.remove_subject_events_from_tile(persona.name, curr_tile)
            self.maze.add_event_from_tile(persona.scratch
                                         .get_curr_event_and_desc(), new_tile)

            # Now, the persona will travel to get to their destination. *Once*
            # the persona gets there, we activate the object action.
            if not persona.scratch.planned_path: 
              # We add that new object action event to the backend tile map. 
              # At its creation, it is stored in the persona's backend. 
              game_obj_cleanup[persona.scratch
                               .get_curr_obj_event_and_desc()] = new_tile
              self.maze.add_event_from_tile(persona.scratch
                                     .get_curr_obj_event_and_desc(), new_tile)
              # We also need to remove the temporary blank action for the 
              # object that is current_state taking the action. 
              blank = (persona.scratch.get_curr_obj_event_and_desc()[0], 
                       None, None, None)
              self.maze.remove_event_from_tile(blank, new_tile)

          # Check for any patients who are leaving as assigned in the previous for loop
          for curr_persona in leaving_patient:
            curr_persona.leave_ed(self.maze, self.personas, sim_folder, self.data_collection)
            # Remove persona from runtime trackers
            self.personas.pop(curr_persona.name, None)
            self.personas_tile.pop(curr_persona.name, None)




          # Then we need to actually have each of the personas perceive and
          # move. The movement for each of the personas comes in the form of
          # x y coordinates where the persona will move towards. e.g., (50, 34)
          # This is where the core brains of the personas are invoked. 
          movements = {"persona": dict(), 
                       "meta": dict()}
          for persona_name, persona in list(self.personas.items()): 
            # <next_tile> is a x,y coordinate. e.g., (58, 9)
            # <pronunciatio> is an emoji. e.g., "\ud83d\udca4"
            # <description> is a string description of the movement. e.g., 
            #   writing her next novel (editing her novel) 
            #   @ double studio:double studio:common room:sofa
            tile_entry = self.personas_tile.get(persona_name)
            if tile_entry is None:
              print(f"(reverie): Warning - missing tile entry for {persona_name}, skipping movement frame")
              continue
            role_bucket = self.data_collection.setdefault(persona.role, {})
            persona_bucket = role_bucket.get(persona_name)
            if persona_bucket is None:
              persona_bucket = persona.data_collection_dict()
              role_bucket[persona_name] = persona_bucket
            pre_state = None
            pre_area = None
            if persona.role == "Patient":
              pre_state = persona.scratch.state
              pre_area = self.maze.tiles[tile_entry[1]][tile_entry[0]]['arena']
            next_tile, pronunciatio, description = persona.move(
              self.maze, self.personas, tile_entry, 
              self.curr_time, persona_bucket)
            if persona.role == "Patient" and self.travel_minutes_per_tile > 0:
              tiles_moved = 0
              if next_tile and (next_tile[0] != tile_entry[0] or next_tile[1] != tile_entry[1]):
                tiles_moved = abs(next_tile[0] - tile_entry[0]) + abs(next_tile[1] - tile_entry[1])
                if tiles_moved == 0:
                  tiles_moved = 1
              if tiles_moved > 0:
                travel_minutes = tiles_moved * self.travel_minutes_per_tile
                persona_bucket.setdefault("tiles_traveled", 0)
                persona_bucket["tiles_traveled"] += tiles_moved
                persona_bucket.setdefault("travel_time_minutes", 0.0)
                persona_bucket["travel_time_minutes"] += travel_minutes
                travel_state = persona_bucket.setdefault("travel_time_state", {})
                if pre_state:
                  travel_state[pre_state] = travel_state.get(pre_state, 0) + travel_minutes
                travel_area = persona_bucket.setdefault("travel_time_area", {})
                if pre_area:
                  travel_area[pre_area] = travel_area.get(pre_area, 0) + travel_minutes
            movements["persona"][persona_name] = {}
            movements["persona"][persona_name]["movement"] = next_tile
            movements["persona"][persona_name]["pronunciatio"] = pronunciatio
            movements["persona"][persona_name]["description"] = description
            movements["persona"][persona_name]["chat"] = (persona
                                                          .scratch.chat)

          # Fix orphaned patients, age global queue, boost overdue patients,
          # triage timeouts, and process scheduled preloaded patient departures
          self._rescue_orphaned_patients()
          self._age_global_doctor_queue()
          self._boost_overdue_patients()
          self._check_triage_timeouts()
          self._process_preloaded_departures()
          self._write_sim_status(sim_folder)

          # Add new Patient based on threshold when it's over or equal to one
          if(self.add_patient_threshold >= 1):
            # Select symptom based on probabilities 
            symptoms = numpy.random.choice(self.symptoms["Symptoms"], 1, p=self.symptoms["normalized_fraction"])
            symptoms_index = self.symptoms["Symptoms"].index(symptoms)
            innates = ["Impatient, Friendly", "Unstable, Friendly"]
            choosen_innate = random.choice(innates)
            new_patient, curr_tile = self.add_persona_to_sim("Patient",f"Experiencing {symptoms} | Innate: {choosen_innate}", 
                                                             persona_loc=random.choice(list(self.maze.address_tiles["<spawn_loc>exit"])))

            # Add to this steps movement dict so that frontend can see it
            movements["persona"][new_patient.name] = {}
            movements["persona"][new_patient.name]["movement"] = curr_tile
            movements["persona"][new_patient.name]["pronunciatio"] = ""
            movements["persona"][new_patient.name]["description"] = ""
            movements["persona"][new_patient.name]["chat"] = (new_patient.scratch.chat)

            new_patient.scratch.ICD = self.symptoms["ICD-10-CA"][symptoms_index]
            new_patient.scratch.CTAS = int(self.symptoms["CTAS"][symptoms_index])
            new_patient.scratch.injuries_zone = self.symptoms["Zone"][symptoms_index]

            # Add patient to triage queue
            self.maze.triage_queue.append(new_patient.name)

            # Reset counter 
            self.add_patient_threshold -= 1
          else:
            # First calculate the (patient added)/(steps in a hour)
            # Then added that to the threshold to add in patients throughout the hour
            # External rate to affect how many Patient coming in. Change in meta file.
            self.add_patient_threshold += (float(self.ed_visits["num_of_patients"][self.curr_time.hour]) / (3600.0/self.sec_per_step)) * self.patient_rate

          # Include the meta information about the current stage in the 
          # movements dictionary. 
          movements["meta"]["curr_time"] = (self.curr_time 
                                             .strftime("%B %d, %Y, %H:%M:%S"))

          # In headless mode, update personas_tile directly from movements
          # so the next iteration uses the new positions.
          if self.headless:
            for p_name, p_data in movements["persona"].items():
              mv = p_data["movement"]
              self.personas_tile[p_name] = (mv[0], mv[1])

          # Write movement file for replay support (skipped in pure logic runs).
          if self.write_movement:
            curr_move_file = f"{sim_folder}/movement/{self.step}.json"
            _atomic_write_json(curr_move_file, movements)

          # After this cycle, the world takes one step forward, and the
          # current time moves by <sec_per_step> amount.
          self.step += 1
          self.curr_time += datetime.timedelta(seconds=self.sec_per_step)

          int_counter -= 1

      curr_step = dict()
      curr_step["step"] = self.step
      _atomic_write_json(f"{fs_temp_storage}/curr_step.json", curr_step)

      # Sleep so we don't burn our machines.
      #self.save()
      time.sleep(self.server_sleep)


  def open_server(self, frontend_ui: str = None, input_command: str = None) -> None:
    """
    Run simulation control loop. If environment variable REVERIE_FRONTEND_CONTROL=1
    (or if temp command dir exists), the server will look for command files in
    temp_storage/commands/ instead of waiting for terminal input.
    """
    print("Note: The agents in this simulation package are computational")
    print("constructs powered by generative agents architecture and LLM. We")
    print("clarify that these agents lack human-like agency, consciousness,")
    print("and independent decision-making.\n---")

    sim_folder = f"{fs_storage}/{self.sim_code}"

    # --- Frontend control paths ---
    cmd_dir = Path(f"{fs_temp_storage}/commands")
    cmd_dir.mkdir(parents=True, exist_ok=True)

    out_file = Path(f"{fs_temp_storage}/sim_output.json")
    if not out_file.exists():
        out_file.write_text(json.dumps({"outputs": []}, indent=2))

    frontend_control = (
        'y' in frontend_ui.lower()
        and cmd_dir.exists()
    )

    def cleanup_temp_files():
        try:
            if cmd_dir.exists():
                shutil.rmtree(cmd_dir)
        except Exception as e:
            print("(reverie): Failed to remove command dir:", e)

        try:
            if out_file.exists():
                out_file.unlink()
        except Exception as e:
            print("(reverie): Failed to remove output file:", e)

    print("Ready for Input Commands.")

    while True:
        sim_command = None
        cmd_id = None
        cmd_path = None
        finished = False
        ret_str = ""

        if input_command:
            sim_command = input_command.strip()

        elif frontend_control:
            cmd_files = sorted(cmd_dir.glob("cmd_*.json"))
            if not cmd_files:
                time.sleep(self.server_sleep)
                continue

            cmd_path = cmd_files[0]
            try:
                with open(cmd_path) as f:
                    payload = json.load(f)
                sim_command = payload.get("command", "").strip()
                cmd_id = payload.get("id", cmd_path.stem)
            except Exception as e:
                print("(reverie): Failed to read command file:", e)
                cmd_path.unlink(missing_ok=True)
                continue

        else:
            try:
                sim_command = input("Enter option: ").strip()
            except EOFError:
                break

        if not sim_command:
            if input_command:
                break
            continue

        # -------- Command execution --------
        try:
          cmd_lower = sim_command.lower()

          if cmd_lower in ["f", "fin", "finish", "save and finish"]:
              print("Saving...")
              self.save()
              ret_str = "Save Successful.\n"
              finished = True

          elif cmd_lower == "start path tester mode":
              shutil.rmtree(sim_folder, ignore_errors=True)
              self.start_path_tester_server()

          elif cmd_lower == "exit":
              print("Exiting...")
              shutil.rmtree(sim_folder, ignore_errors=True)
              ret_str = "Exited and removed simulation folder.\n"
              finished = True

          elif cmd_lower == "save":
              self.save()
              ret_str = "Save Successful.\n"

          elif cmd_lower.startswith("run"):
              int_count = int(sim_command.split()[-1])
              self.start_server(int_count)
              ret_str = f"Ran {int_count} steps.\n"

          elif cmd_lower.startswith("print persona schedule"):
              name = " ".join(sim_command.split()[-2:])
              ret_str = (
                  self.personas[name]
                  .scratch.get_str_daily_schedule_summary()
              )

          elif cmd_lower.startswith("print all persona schedule"):
              for name, persona in self.personas.items():
                  ret_str += f"{name}\n"
                  ret_str += persona.scratch.get_str_daily_schedule_summary()
                  ret_str += "\n---\n"

          elif "print hourly org persona schedule" in cmd_lower:
              name = " ".join(sim_command.split()[-2:])
              ret_str = (
                  self.personas[name]
                  .scratch.get_str_daily_schedule_hourly_org_summary()
              )

          elif cmd_lower.startswith("print persona current tile"):
              name = " ".join(sim_command.split()[-2:])
              ret_str = str(self.personas[name].scratch.curr_tile)

          elif "print persona chatting with buffer" in cmd_lower:
              name = " ".join(sim_command.split()[-2:])
              persona = self.personas[name]
              for p, c in persona.scratch.chatting_with_buffer.items():
                  ret_str += f"{p}: {c}\n"

          elif "print persona associative memory (event)" in cmd_lower:
              name = " ".join(sim_command.split()[-2:])
              ret_str += self.personas[name].a_mem.get_str_seq_events()

          elif "print persona associative memory (thought)" in cmd_lower:
              name = " ".join(sim_command.split()[-2:])
              ret_str += self.personas[name].a_mem.get_str_seq_thoughts()

          elif "print persona associative memory (chat)" in cmd_lower:
              name = " ".join(sim_command.split()[-2:])
              ret_str += self.personas[name].a_mem.get_str_seq_chats()

          elif "print persona spatial memory" in cmd_lower:
              name = " ".join(sim_command.split()[-2:])
              self.personas[name].s_mem.print_tree()

          elif cmd_lower.startswith("print current time"):
              ret_str += self.curr_time.strftime("%B %d, %Y, %H:%M:%S")
              ret_str += f"\nsteps: {self.step}"

          elif cmd_lower.startswith("print tile event"):
              coordinate = [int(i.strip()) for i in sim_command[16:].split(",")]
              for e in self.maze.access_tile(coordinate)["events"]:
                  ret_str += f"{e}\n"

          elif cmd_lower.startswith("print tile details"):
              coordinate = [int(i.strip()) for i in sim_command[18:].split(",")]
              for k, v in self.maze.access_tile(coordinate).items():
                  ret_str += f"{k}: {v}\n"

          elif cmd_lower.startswith("call -- analysis"):
              persona_name = sim_command[len("call -- analysis"):].strip()
              self.personas[persona_name].open_convo_session("analysis")

          elif cmd_lower.startswith("call -- load history"):
              curr_file = (
                  maze_assets_loc + "/" +
                  sim_command[len("call -- load history"):].strip()
              )
              rows = read_file_to_list(curr_file, header=True, strip_trail=True)[1]
              clean_whispers = []
              for row in rows:
                  agent = row[0].strip()
                  for w in row[1].split(";"):
                      clean_whispers.append([agent, w.strip()])
              load_history_via_whisper(self.personas, clean_whispers)

          else:
              ret_str = f"Unknown command: {sim_command}\n"

        except Exception as e:
            ret_str = f"(reverie): Error: {str(e)}\n"

            if self.driver:
                self.driver.quit()

            movement_file = f"{sim_folder}/movement/{self.step}.json"
            env_file = f"{sim_folder}/environment/{self.step}.json"

            if os.path.exists(movement_file):
                os.remove(movement_file)
            if os.path.exists(env_file):
                os.remove(env_file)

            print(f"(reverie): Error at step {self.step}\n\n{ret_str}")
            
            self.step -= 1
            self.curr_time -= datetime.timedelta(seconds=self.sec_per_step)
            if(not frontend_control):
              raise Exception(e, self.step)
        finally:
            # Remove processed command file
            if frontend_control and cmd_path and cmd_path.exists():
                cmd_path.unlink(missing_ok=True)

            # Write output
            try:
                outputs = json.loads(out_file.read_text())
            except Exception:
                outputs = {"outputs": []}

            outputs["outputs"].append({
                "id": cmd_id or str(uuid.uuid4()),
                "command": sim_command,
                "output": ret_str,
                "timestamp": datetime.datetime.utcnow().isoformat()
            })

            out_file.write_text(json.dumps(outputs, indent=2))

        # -------- Exit conditions --------
        if input_command:
            break

        if finished:
            cleanup_temp_files()
            break
        
  #########################################################
  # OLD TERMINAL COMMAND INTERFACE FOR SIMULATION CONTROL #
  #########################################################

  """
  def open_server(self, input_command: str = None) -> None: 
    
    Open up an interactive terminal prompt that lets you run the simulation 
    step by step and probe agent state. 

    INPUT 
      None
    OUTPUT
      None

    print ("Note: The agents in this simulation package are computational")
    print ("constructs powered by generative agents architecture and LLM. We")
    print ("clarify that these agents lack human-like agency, consciousness,")
    print ("and independent decision-making.\n---")

    # <sim_folder> points to the current simulation folder.
    sim_folder = f"{fs_storage}/{self.sim_code}"

    while True: 
      if not input_command:
        sim_command = input("Enter option: ")
      else:
        sim_command = input_command
      sim_command = sim_command.strip()
      ret_str = ""

      try: 
        if sim_command.lower() in ["f", "fin", "finish", "save and finish"]: 
          # Finishes the simulation environment and saves the progress. 
          # Example: fin
          print("Saving...")
          self.save()
          print("Save Successful.")
          break

        elif sim_command.lower() == "start path tester mode": 
          # Starts the path tester and removes the current_state forked sim files.
          # Note that once you start this mode, you need to exit out of the
          # session and restart in case you want to run something else. 
          shutil.rmtree(sim_folder) 
          self.start_path_tester_server()

        elif sim_command.lower() == "exit": 
          # Finishes the simulation environment but does not save the progress
          # and erases all saved data from current simulation. 
          # Example: exit 
          shutil.rmtree(sim_folder) 
          break 

        elif sim_command.lower() == "save": 
          # Saves the current simulation progress. 
          # Example: save
          self.save()

        elif sim_command[:3].lower() == "run": 
          # Runs the number of steps specified in the prompt.
          # Example: run 1000
          int_count = int(sim_command.split()[-1])
          self.start_server(int_count)

        elif ("print persona schedule" 
              in sim_command[:22].lower()): 
          # Print the decomposed schedule of the persona specified in the 
          # prompt.
          # Example: print persona schedule Isabella Rodriguez
          ret_str += (self.personas[" ".join(sim_command.split()[-2:])]
                      .scratch.get_str_daily_schedule_summary())

        elif ("print all persona schedule" 
              in sim_command[:26].lower()): 
          # Print the decomposed schedule of all personas in the world. 
          # Example: print all persona schedule
          for persona_name, persona in self.personas.items(): 
            ret_str += f"{persona_name}\n"
            ret_str += f"{persona.scratch.get_str_daily_schedule_summary()}\n"
            ret_str += f"---\n"

        elif ("print hourly org persona schedule" 
              in sim_command.lower()): 
          # Print the hourly schedule of the persona specified in the prompt.
          # This one shows the original, non-decomposed version of the 
          # schedule.
          # Ex: print persona schedule Isabella Rodriguez
          ret_str += (self.personas[" ".join(sim_command.split()[-2:])]
                      .scratch.get_str_daily_schedule_hourly_org_summary())

        elif ("print persona current tile" 
              in sim_command[:26].lower()): 
          # Print the x y tile coordinate of the persona specified in the 
          # prompt. 
          # Ex: print persona current tile Isabella Rodriguez
          ret_str += str(self.personas[" ".join(sim_command.split()[-2:])]
                      .scratch.curr_tile)

        elif ("print persona chatting with buffer" 
              in sim_command.lower()): 
          # Print the chatting with buffer of the persona specified in the 
          # prompt.
          # Ex: print persona chatting with buffer Isabella Rodriguez
          curr_persona = self.personas[" ".join(sim_command.split()[-2:])]
          for p_n, count in curr_persona.scratch.chatting_with_buffer.items(): 
            ret_str += f"{p_n}: {count}"

        elif ("print persona associative memory (event)" 
              in sim_command.lower()):
          # Print the associative memory (event) of the persona specified in
          # the prompt
          # Ex: print persona associative memory (event) Isabella Rodriguez
          ret_str += f'{self.personas[" ".join(sim_command.split()[-2:])]}\n'
          ret_str += (self.personas[" ".join(sim_command.split()[-2:])]
                                       .a_mem.get_str_seq_events())

        elif ("print persona associative memory (thought)" 
              in sim_command.lower()): 
          # Print the associative memory (thought) of the persona specified in
          # the prompt
          # Ex: print persona associative memory (thought) Isabella Rodriguez
          ret_str += f'{self.personas[" ".join(sim_command.split()[-2:])]}\n'
          ret_str += (self.personas[" ".join(sim_command.split()[-2:])]
                                       .a_mem.get_str_seq_thoughts())

        elif ("print persona associative memory (chat)" 
              in sim_command.lower()): 
          # Print the associative memory (chat) of the persona specified in
          # the prompt
          # Ex: print persona associative memory (chat) Isabella Rodriguez
          ret_str += f'{self.personas[" ".join(sim_command.split()[-2:])]}\n'
          ret_str += (self.personas[" ".join(sim_command.split()[-2:])]
                                       .a_mem.get_str_seq_chats())

        elif ("print persona spatial memory" 
              in sim_command.lower()): 
          # Print the spatial memory of the persona specified in the prompt
          # Ex: print persona spatial memory Isabella Rodriguez
          self.personas[" ".join(sim_command.split()[-2:])].s_mem.print_tree()

        elif ("print current time" 
              in sim_command[:18].lower()): 
          # Print the current time of the world. 
          # Ex: print current time
          ret_str += f'{self.curr_time.strftime("%B %d, %Y, %H:%M:%S")}\n'
          ret_str += f'steps: {self.step}'

        elif ("print tile event" 
              in sim_command[:16].lower()): 
          # Print the tile events in the tile specified in the prompt 
          # Ex: print tile event 50, 30
          cooordinate = [int(i.strip()) for i in sim_command[16:].split(",")]
          for i in self.maze.access_tile(cooordinate)["events"]: 
            ret_str += f"{i}\n"

        elif ("print tile details" 
              in sim_command.lower()): 
          # Print the tile details of the tile specified in the prompt 
          # Ex: print tile event 50, 30
          cooordinate = [int(i.strip()) for i in sim_command[18:].split(",")]
          for key, val in self.maze.access_tile(cooordinate).items(): 
            ret_str += f"{key}: {val}\n"

        elif ("call -- analysis" 
              in sim_command.lower()): 
          # Starts a stateless chat session with the agent. It does not save 
          # anything to the agent's memory. 
          # Ex: call -- analysis Isabella Rodriguez
          persona_name = sim_command[len("call -- analysis"):].strip() 
          self.personas[persona_name].open_convo_session("analysis")

        elif ("call -- load history" 
              in sim_command.lower()): 
          curr_file = maze_assets_loc + "/" + sim_command[len("call -- load history"):].strip() 
          # call -- load history the_ville/agent_history_init_n3.csv

          rows = read_file_to_list(curr_file, header=True, strip_trail=True)[1]
          clean_whispers = []
          for row in rows: 
            agent_name = row[0].strip() 
            whispers = row[1].split(";")
            whispers = [whisper.strip() for whisper in whispers]
            for whisper in whispers: 
              clean_whispers += [[agent_name, whisper]]

          load_history_via_whisper(self.personas, clean_whispers)

        print (ret_str)
        
      except Exception as e:
        print("(reverie): Error: ", e)

        if self.driver:
          self.driver.quit()

        # remove movement file if it exists
        movement_file = f"{sim_folder}/movement/{self.step}.json"
        if os.path.exists(movement_file):
          os.remove(movement_file)
        # remove environment file if it exists
        env_file = f"{sim_folder}/environment/{self.step}.json"
        if os.path.exists(env_file):
          os.remove(env_file)
        print(f"(reverie): Error at step {self.step}")
        self.step -= 1
        self.curr_time -= datetime.timedelta(seconds=self.sec_per_step)
        raise Exception(e, self.step)
      else:
        # If an input command was passed, then execute one command and exit.
        if input_command:
          break
  """

  # To create patient during simulation
  # Adds and initiate persona in simulation
  def add_persona_to_sim(self, persona_role, agent_desc = "", persona_loc = None):
    self.num_roles[persona_role] += 1
    sim_folder = f"{fs_storage}/{self.sim_code}"

    # Grab constructor for persona class based on role
    PersonaClass = self.persona_classes.get(persona_role, Persona)
    curr_persona, pos = Persona.create_persona(
        PersonaClass,
        persona_role,
        self.num_roles[persona_role],
        agent_desc,
        self.curr_time,
        sim_folder,
        self.maze,
        persona_loc=persona_loc,
        seed=self.seed,
    )

    _assign_wait_targets(curr_persona, self.ctas_wait_config, self.curr_time, self.surge_multiplier)


    self.personas[curr_persona.name] = curr_persona
    self.personas_tile[curr_persona.name] = (pos[0], pos[1])
    self.maze.tiles[pos[1]][pos[0]]["events"].add(curr_persona.scratch
                                .get_curr_event_and_desc())
    
    if(curr_persona.name not in self.data_collection[curr_persona.role].keys()):
      temp_dict = curr_persona.data_collection_dict()
  
      self.data_collection[curr_persona.role][curr_persona.name] = temp_dict

    return self.personas[curr_persona.name], pos

  # To add persona before a before simulation such as right after getting the run command from user
  # Adds new persona to step file in the enviroment step file
  def add_persona_to_step(self, curr_persona, pos = None):
    # In headless mode, personas_tile is already updated by add_persona_to_sim;
    # no environment file to write.
    if self.headless:
      return curr_persona, [pos[0], pos[1]]

    sim_folder = f"{fs_storage}/{self.sim_code}"

    # Add new persona to current step file
    curr_env_file = f"{sim_folder}/environment/{self.step}.json"
    with open(curr_env_file) as json_file:
      new_env = json.load(json_file)

    new_env[curr_persona.name] = {
      "maze": "Emergency Department",
      "x": pos[0],
      "y": pos[1]
    }

    with open(curr_env_file, 'w') as json_file:
      json_file.write(json.dumps(new_env, indent=2))

    return curr_persona, [pos[0], pos[1]]


if __name__ == '__main__':

  # Pars input params
  parser = argparse.ArgumentParser(description='Reverie Server')
  parser.add_argument(
    '--origin',
    type=str,
    default="ed_sim_n5",
    help='The name of the forked simulation'
  )
  parser.add_argument(
    '--target',
    type=str,
    default="test-simulation",
    help='The name of the new simulation'
  )
  parser.add_argument(
    '--browser',
    type=str,
    default="no",
    help='Opens a Firefox tab automatically of the simulation'
  )
  parser.add_argument(
    '--frontend_ui',
    type=str,
    default="no",
    help='Use the frontend UI for simulation control'
  )
  parser.add_argument(
    '--headless',
    type=str,
    default="no",
    help='Run in headless mode (skip frontend file I/O for faster batch runs)'
  )
  parser.add_argument(
    '--write_movement',
    type=str,
    default="yes",
    help='Write movement/{step}.json files each step (yes = full replay support, no = pure fast logic run)'
  )

  args = parser.parse_args()
  origin = args.origin
  target = args.target
  browser = args.browser
  frontend_ui = args.frontend_ui
  headless = args.headless
  write_movement = args.write_movement

  rs = ReverieServer(origin, target)

  if "y" in headless:
    rs.headless = True

  if "n" in write_movement:
    rs.write_movement = False

  if("y" in browser):
    rs.driver = webdriver.Firefox()
    rs.driver.get("http://localhost:8000/simulator_home")

  rs.open_server(frontend_ui)
  time.sleep(2)

  if rs.driver:
    rs.driver.quit()
