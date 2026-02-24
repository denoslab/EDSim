
import datetime
import math
import random 
import sys
import time
import heapq
import bisect
import utils
sys.path.append('../../')
from persona.persona import *
from persona.memory_structures.scratch_types.bedside_nurse_scratch import *

class Bedside_Nurse(Persona):
    testing_time = 0
    resting_time = 15
    priority_factor = 0
    idle_move_min_interval_minutes = 30

    def __init__(self, name, folder_mem_saved=False, role=None, seed=0):
        super().__init__(name,folder_mem_saved,role,seed)
        scratch_saved = f"{folder_mem_saved}/bootstrap_memory/scratch.json"
        self.scratch = bedside_nurse_scratch(scratch_saved)

        # ADDED: tracking fields for logging
        # Last state label and time we updated durations
        if not hasattr(self.scratch, "last_state_label"):
            self.scratch.last_state_label = None
        if not hasattr(self.scratch, "last_state_update_time"):
            self.scratch.last_state_update_time = None

        # Last action plan string we logged
        if not hasattr(self.scratch, "last_action_plan"):
            self.scratch.last_action_plan = None

        # Previous chat partner, to detect new interactions
        if not hasattr(self.scratch, "prev_chat_partner"):
            self.scratch.prev_chat_partner = None

        # Track when `occupied` was last set (for timeout detection)
        if not hasattr(self.scratch, "occupied_since"):
            self.scratch.occupied_since = None

    
    def _set_occupied(self, value, curr_time):
        """Set occupied and track when it changed for timeout detection."""
        self.scratch.occupied = value
        if value and value != "Resting":
            self.scratch.occupied_since = curr_time
        else:
            self.scratch.occupied_since = None

    def _should_skip_cognition(self):
        """Skip LLM perceive/retrieve/plan when the nurse is busy with
        something that doesn't require new cognitive processing."""
        # Already in a conversation — timer will handle cleanup
        if self.scratch.chatting_with:
            return True
        # Testing or resting timer hasn't expired yet
        if self.scratch.time_to_next:
            return True
        # Still walking toward target — more than one step's worth of tiles away
        tps = getattr(self.scratch, '_tiles_per_step', 1)
        if len(self.scratch.planned_path) > tps + 1:
            return True
        return False

    def move(self, maze, personas, curr_tile, curr_time, data_collection):
        plan = super().move(maze, personas, curr_tile, curr_time, data_collection)
        # Default to a neutral/thoughtful emoji for bedside nurses
        self.scratch.act_pronunciatio = "☁️"

        # Validate occupied patient still exists in the simulation
        if self.scratch.occupied and isinstance(self.scratch.occupied, str):
            patient_name = self.scratch.occupied.split("|")[-1]
            if patient_name not in personas:
                print(f"(BedsideNurse) {self.name}: clearing stale occupied={self.scratch.occupied}, "
                      f"{patient_name} no longer in simulation")
                self.scratch.occupied = None
                self.scratch.next_step = None
                self.scratch.chat = None
                self.scratch.chatting_with = None
                self.scratch.act_path_set = False

        # ADDED: log state + new chat interactions at this tick
        # 1) Update time spent in previous state
        self._update_state_durations(curr_time, data_collection)

        # 2) Log any new chat partner as an interaction with another persona
        self._log_new_chat_interaction(curr_time, personas, data_collection)

        # Special condition for patient to do whatever the medical staff tells them. next_step changed in plan.py.
        # To easily control what a patient should do next in a given room

        # When a patient needs moving set bedside nurse to walk to patient

        def zone_has_space(zone):
            """Check if a target zone has a free bed/slot using the synced bed tracker when available."""
            if not zone:
                return False
            if hasattr(maze, "available_beds") and zone in maze.available_beds:
                return len(maze.available_beds.get(zone, [])) > 0
            zone_info = maze.injuries_zones.get(zone, {})
            if not isinstance(zone_info, dict):
                return False
            return len(zone_info.get("current_patients", [])) < zone_info.get("capacity", 0)

        def reserve_bed(patient, zone):
            """
            Reserve a bed for the patient immediately so we don't rely on stale current_patients counts.
            Returns the reserved bed (tuple) or None when the zone is not bed-tracked.
            """
            if hasattr(maze, "available_beds") and zone in maze.available_beds:
                bed = maze.assign_bed(patient.name, zone, patient.scratch.bed_assignment)
                if bed:
                    patient.scratch.bed_assignment = list(bed)
                return bed
            return None

        # Checking if testing is done
        if(self.scratch.time_to_next):
            if(self.scratch.time_to_next <= curr_time):

                if ("Testing" in str(self.scratch.occupied)):
                    self.scratch.next_step = f"<persona> {self.scratch.occupied.split('|')[-1]}"
                    self.scratch.occupied = self.scratch.occupied.split('|')[-1]
                    maze.injuries_zones["diagnostic room"]["current_patients"].remove(self.scratch.occupied)
                    self.scratch.time_to_next = None
                    self.act_path_set = False
                elif("Resting" in str(self.scratch.occupied)):
                    self.scratch.occupied = None
                    self.scratch.time_to_next = None
            else:
                # Cancel rest early if patients are waiting in queue
                if (self.scratch.occupied == "Resting"
                    and (maze.injuries_zones.get("bedside_nurse_waiting", [])
                         or maze.injuries_zones.get("pager", []))):
                    self.scratch.occupied = None
                    self.scratch.time_to_next = None
                    self.scratch.act_path_set = False
                else:
                    self.scratch.act_path_set = True


        # CTAS 1 patients get placed in a separate pager queue
        if(maze.injuries_zones["pager"] != [] and not self.scratch.occupied):
            pager_patient_name = maze.injuries_zones["pager"][0][1]
            if pager_patient_name not in personas:
                maze.injuries_zones["pager"].pop(0)
            else:
                selected_patient = personas[pager_patient_name]
                print(selected_patient.name)
                target_zone = selected_patient.scratch.next_room
                # CTAS 1 (pager) patients always get placed — they override
                # bed capacity.  In a real ED a life-threatening patient is
                # never turned away for lack of beds.
                reserve_bed(selected_patient, target_zone)   # best-effort
                maze.injuries_zones["pager"].pop(0)

                # Reset all actions for both personas
                selected_patient.scratch.chat = None
                selected_patient.scratch.chatting_with = None

                self.scratch.chat = None
                self.scratch.chatting_with = None

                data_collection["Patients_Attended"].append([selected_patient.name, curr_time.strftime("%B %d, %Y, %H:%M:%S")])

                zone = selected_patient.scratch.next_room
                if(zone and zone in maze.injuries_zones and selected_patient.name not in maze.injuries_zones[zone]["current_patients"]):
                    maze.injuries_zones[zone]["current_patients"].append(selected_patient.name)

                # Deterministic state transition — don't wait for chat
                if selected_patient.scratch.state == "WAITING_FOR_NURSE":
                    selected_patient.scratch.next_room = selected_patient.scratch.injuries_zone
                    bed_target = selected_patient._target_bed(maze, selected_patient.scratch.injuries_zone)
                    if bed_target:
                        selected_patient.scratch.next_step = f"<tile> {bed_target}"
                        self.scratch.next_step = f"<tile> {bed_target}"
                    else:
                        selected_patient.scratch.next_step = f"ed map:emergency department:{selected_patient.scratch.injuries_zone}:bed"
                        self.scratch.next_step = f"ed map:emergency department:{selected_patient.scratch.injuries_zone}:bed"
                    selected_patient.scratch.state = "WAITING_FOR_FIRST_ASSESSMENT"
                    selected_patient.scratch.act_path_set = False
                    # Surge extra: push the assessment gate forward so
                    # the surge slowdown is experienced in-bed.
                    surge_extra = float(selected_patient.scratch.stage1_surge_extra or 0)
                    if surge_extra > 0:
                        import datetime as _dt
                        selected_patient.scratch.initial_assessment_ready_at = (
                            max(selected_patient.scratch.initial_assessment_ready_at or curr_time, curr_time)
                            + _dt.timedelta(minutes=surge_extra)
                        )
                elif selected_patient.scratch.state == "WAITING_FOR_TEST":
                    self.scratch.next_step = f"ed map:emergency department:{selected_patient.scratch.next_room}:chair"
                else:
                    self.scratch.next_step = f"<persona> {selected_patient.name}"

                self._set_occupied(f"Transfer|{selected_patient.name}", curr_time)
                self.scratch.act_path_set = False
                plan = self.scratch.next_step



        if (not self.scratch.chatting_with):
            # To Transport a Patient
            if(not self.scratch.occupied):

                # So we can properly remove this entry from the queue
                selected_patient = None
                self.scratch.act_path_set = False
                reserved_bed = None

                # Check the whole sorted array to see if there is a Patient ready and injuries zone open for another Patient
                for p_info in maze.injuries_zones["bedside_nurse_waiting"][:]:
                    curr_persona = personas.get(p_info[1])
                    if not curr_persona:
                        maze.injuries_zones["bedside_nurse_waiting"].remove(p_info)
                        continue
                    zone = curr_persona.scratch.next_room
                    if not zone:
                        maze.injuries_zones["bedside_nurse_waiting"].remove(p_info)
                        continue
                    if curr_persona.scratch.state != "WAITING_FOR_NURSE" and curr_persona.scratch.state != "WAITING_FOR_TEST":
                        maze.injuries_zones["bedside_nurse_waiting"].remove(p_info)
                        continue
                    print(p_info)
                    # Check if injuries zone is open for another Patient and Patient hasn't been selected yet
                    if(selected_patient == None and zone_has_space(zone)):
                        reserved_bed = reserve_bed(curr_persona, zone)
                        if(zone in getattr(maze, "available_beds", {}) and not reserved_bed):
                            continue
                        selected_patient = curr_persona
                        maze.injuries_zones["bedside_nurse_waiting"].remove(p_info)

                    # Increase priority for other Patients based on time waiting only if a Patient has been selected already in the queue
                    else:
                        if (p_info[0] > 3):
                            p_info[0] -= 1
                
                # Check if a Patient has been found
                if(selected_patient):
                    data_collection["Patients_Attended"].append([selected_patient.name, p_info[0]])

                    # Add patient to one of the patients in the zones
                    zone = selected_patient.scratch.next_room
                    if(zone and zone in maze.injuries_zones and selected_patient.name not in maze.injuries_zones[zone]["current_patients"]):
                        maze.injuries_zones[zone]["current_patients"].append(selected_patient.name)

                    # Deterministic state transition — don't wait for chat
                    if selected_patient.scratch.state == "WAITING_FOR_NURSE":
                        selected_patient.scratch.next_room = selected_patient.scratch.injuries_zone
                        bed_target = selected_patient._target_bed(maze, selected_patient.scratch.injuries_zone)
                        if bed_target:
                            selected_patient.scratch.next_step = f"<tile> {bed_target}"
                            self.scratch.next_step = f"<tile> {bed_target}"
                        else:
                            selected_patient.scratch.next_step = f"ed map:emergency department:{selected_patient.scratch.injuries_zone}:bed"
                            self.scratch.next_step = f"ed map:emergency department:{selected_patient.scratch.injuries_zone}:bed"
                        selected_patient.scratch.state = "WAITING_FOR_FIRST_ASSESSMENT"
                        selected_patient.scratch.act_path_set = False
                        # Surge extra: push the assessment gate forward so
                        # the surge slowdown is experienced in-bed.
                        surge_extra = float(selected_patient.scratch.stage1_surge_extra or 0)
                        if surge_extra > 0:
                            import datetime as _dt
                            selected_patient.scratch.initial_assessment_ready_at = (
                                max(selected_patient.scratch.initial_assessment_ready_at or curr_time, curr_time)
                                + _dt.timedelta(minutes=surge_extra)
                            )
                    elif selected_patient.scratch.state == "WAITING_FOR_TEST":
                        self.scratch.next_step = f"ed map:emergency department:{selected_patient.scratch.next_room}:chair"
                    else:
                        self.scratch.next_step = f"<persona> {selected_patient.name}"

                    self._set_occupied(f"Transfer|{selected_patient.name}", curr_time)
                    self.scratch.act_path_set = False

            elif (personas.get(self.scratch.occupied.split("|")[-1]) == None or personas[self.scratch.occupied.split("|")[-1]].scratch.state == "LEAVING"):
                self.scratch.occupied = None  

            # Check wether the nurse has reached the room assigneed to the patient
            elif("Transfer" in str(self.scratch.occupied) and maze.tiles[curr_tile[1]][curr_tile[0]]['arena'] in 
                str(personas[self.scratch.occupied.split("|")[-1]].scratch.next_room)):
                # Reset nurse state when delivering them to the room
                persona_name = self.scratch.occupied.split('|')[-1]


                # Check which room they happened to end up at and assign special behaviour depending on location and status
                # If they end up the diagnostic room, drop off the patient and become free
                if(maze.tiles[curr_tile[1]][curr_tile[0]]['arena'] == "diagnostic room"):
                    # Set the patient's testing timer so they self-manage their stay
                    patient_persona = personas.get(persona_name)
                    if patient_persona:
                        patient_persona.scratch.testing_end_time = curr_time + datetime.timedelta(minutes=self.testing_time)
                    # Nurse is now free
                    self.set_to_resting(curr_time)


                # After doing action bedside nurse rests for a bit
                else:
                    self.set_to_resting(curr_time)
                

            # If we want to control bedside nurse this will enforce it
            if(self.scratch.next_step):
                plan = self.scratch.next_step
                self.scratch.act_address = self.scratch.next_step.split("> ")[-1]
                self.scratch.act_address += "| Occupied:  " + str(self.scratch.occupied) if self.scratch.occupied else ""

                # Set a meaningful description based on current occupied state
                occ = self.scratch.occupied
                if occ and isinstance(occ, str):
                    if occ.startswith("Transfer|"):
                        self.scratch.act_description = f"Escorting {occ.split('|')[-1]} to room"
                    elif occ.startswith("Testing|"):
                        self.scratch.act_description = f"Waiting for {occ.split('|')[-1]}'s test"
                    elif occ == "Resting":
                        self.scratch.act_description = "Resting between tasks"
                    else:
                        self.scratch.act_description = f"Going to {occ}"

            # Lightweight idle behavior: roam within the assigned zone and monitor a patient.
            elif ((not self.scratch.occupied or "Resting" in self.scratch.occupied) and self.scratch.planned_path == []):
                self.scratch.act_path_set = False
                self._set_idle_roam_or_checkin(maze, personas, curr_time)
                if self.scratch.next_step:
                    plan = self.scratch.next_step
                    self.scratch.act_address = self.scratch.next_step
                    self.scratch.act_path_set = False
                else:
                    # Cooldown still active or nowhere to go — set fallback description
                    if not self.scratch.act_description or self.scratch.act_description == "None":
                        self.scratch.act_description = "Standing by"
       
        self._log_action_decision(plan, curr_time, data_collection, personas, maze)
        print("Occupied:", self.scratch.occupied)
        return self.execute(maze, personas, plan) 

    def set_to_resting(self, curr_time):
        self._set_occupied("Resting", curr_time)
        self.scratch.act_path_set = True
        self.scratch.next_step = None
        self.scratch.time_to_next = curr_time + datetime.timedelta(minutes=self.resting_time)

    # Persona actions after chatting
    def react_to_chat(self, convo_summary, other_persona, maze):
        # State transitions are now handled deterministically at queue pickup.
        # This method is kept for flavor/realism — chats still happen but
        # don't gate state progression.  Only act if somehow still in the
        # pre-transfer walk phase (idempotent guard).
        if (str(self.scratch.occupied) == other_persona.name
                and "Transfer" not in str(self.scratch.occupied)):
            if other_persona.scratch.state == "WAITING_FOR_NURSE":
                self.scratch.next_step = f"<tile> " + str(other_persona._target_bed(maze, other_persona.scratch.injuries_zone))
                other_persona.scratch.next_room = other_persona.scratch.injuries_zone
            else:
                self.scratch.next_step = "ed map:emergency department:" + other_persona.scratch.next_room + ":chair"
            self.scratch.occupied = f"Transfer|{other_persona.name}"
            self.scratch.act_path_set = False
        return

    # If the persona should chat with target persona based on role and state
    def decide_to_chat(self, target_persona):
        # If they come in contact with assigned Patient talk to them
        if(target_persona.name == str(self.scratch.occupied)):
            return True
        # If the person in view is a patient don't talk to them
        # Or don't talk to anyone when moving a patient
        elif("Patient" in target_persona.name or "Transfer" in str(self.scratch.occupied) or
             "Testing" in str(self.scratch.occupied)):
            return False
        
        # No staff-to-staff conversations — skip LLM fallthrough
        return False

    # Sets up data collection for Bedside Nurse
    def data_collection_dict(self):
        new_dict = {}

        # Existing
        new_dict["Patients_Attended"] = []

        # ADDED: detailed nurse logging
        # Total minutes spent in each high-level nurse state
        new_dict["State_Durations"] = {}

        # Action decisions over time
        new_dict["Action_Log"] = []

        # Interactions with other personas (chat, etc.)
        new_dict["Interactions"] = []

        return new_dict
    
    # Get spawn location in minor injuries zone
    def get_spawn_loc(self, maze):
        return random.choice(list(maze.address_tiles["<spawn_loc>minor injuries zone"]))

    def _assigned_zone(self):
        num = int(self.name.split(' ')[-1]) if self.name.split(' ')[-1].isnumeric() else 0
        return "minor injuries zone" if num % 2 == 0 else "major injuries zone"
   
    # ADDED HELPERS FOR LOGGING

    def _get_state_label(self):
        occ = self.scratch.occupied

        if not occ:
            return "IDLE"

        if isinstance(occ, str):
            if occ == "Resting":
                return "RESTING"
            if occ.startswith("Testing|"):
                return "TESTING_WITH_PATIENT"
            if occ.startswith("Transfer|"):
                return "TRANSFER_WITH_PATIENT"

        # Default: nurse is tied up with a specific patient
        return "WITH_PATIENT"

    def _update_state_durations(self, curr_time, data_collection):
        """
        Add elapsed minutes since last tick to the previous state label.
        Uses real curr_time differences instead of a fixed increment.
        """
        if curr_time is None:
            return

        prev_state = getattr(self.scratch, "last_state_label", None)
        prev_time = getattr(self.scratch, "last_state_update_time", None)
        curr_state = self._get_state_label()

        # If we've ticked before, accumulate elapsed time for the previous state
        if prev_state is not None and prev_time is not None:
            try:
                delta = curr_time - prev_time
                minutes = delta.total_seconds() / 60.0
            except Exception:
                minutes = 0.0
            if minutes < 0:
                minutes = 0.0

            state_durations = data_collection.setdefault("State_Durations", {})
            state_durations[prev_state] = state_durations.get(prev_state, 0.0) + minutes

        # Update the "current" state marker for the next call
        self.scratch.last_state_label = curr_state
        self.scratch.last_state_update_time = curr_time

    def _log_action_decision(self, plan, curr_time, data_collection, personas, maze):
        """
        Log a new action decision whenever the plan string changes.
        """
        if not plan:
            return

        last_plan = getattr(self.scratch, "last_action_plan", None)
        if plan == last_plan:
            return  # no new decision

        entry = {
            "time": curr_time.strftime("%B %d, %Y, %H:%M:%S") if curr_time else None,
            "plan": plan,
            "state": self._get_state_label(),
            "occupied": str(self.scratch.occupied),
        }

        if plan.startswith("<persona> "):
            entry["action_type"] = "GO_TO_PERSONA"
            target_name = plan.replace("<persona>", "").strip()
            entry["target_persona"] = target_name
            if target_name in personas:
                entry["target_role"] = personas[target_name].role
        elif plan.startswith("<tile> "):
            entry["action_type"] = "GO_TO_TILE"
        else:
            entry["action_type"] = "MOVE"

        data_collection.setdefault("Action_Log", []).append(entry)
        self.scratch.last_action_plan = plan

    def _log_new_chat_interaction(self, curr_time, personas, data_collection):
        """
        When chatting_with changes from previous value to a new persona,
        log that as an interaction.
        """
        current_chat = self.scratch.chatting_with
        prev_chat = getattr(self.scratch, "prev_chat_partner", None)

        # Only log when we start chatting with a new persona
        if current_chat and current_chat != prev_chat:
            entry = {
                "time": curr_time.strftime("%B %d, %Y, %H:%M:%S") if curr_time else None,
                "other_persona": current_chat,
                "other_role": personas[current_chat].role if current_chat in personas else None,
                "interaction_type": "CHAT_START",
                "state": self._get_state_label(),
                "occupied": str(self.scratch.occupied),
            }
            data_collection.setdefault("Interactions", []).append(entry)

        self.scratch.prev_chat_partner = current_chat

    def _set_idle_roam_or_checkin(self, maze, personas, curr_time):
        # Apply a cooldown between idle moves (default 30 minutes) to reduce frequency
        if self.scratch.last_idle_move_time and curr_time:
            cooldown = datetime.timedelta(minutes=self.idle_move_min_interval_minutes)
            if curr_time - self.scratch.last_idle_move_time < cooldown:
                return

        zone = self._assigned_zone()

        # Try to monitor a patient in the zone instead of wandering aimlessly
        zone_patients = maze.injuries_zones.get(zone, {}).get("current_patients", [])
        if zone_patients:
            # Pick the highest-acuity (lowest CTAS number) patient to monitor
            best_patient = None
            best_ctas = 999
            for p_name in zone_patients:
                p = personas.get(p_name)
                if not p:
                    continue
                ctas = getattr(p.scratch, "CTAS", 5) or 5
                if ctas < best_ctas:
                    best_ctas = ctas
                    best_patient = p_name
            if best_patient:
                self.scratch.next_step = f"<persona> {best_patient}"
                self.scratch.act_description = f"Monitoring {best_patient}"
                self.scratch.occupied = None
                self.scratch.last_idle_move_time = curr_time
                return

        # Fallback: wander within the assigned zone
        zone_keys = [k for k in maze.address_tiles.keys() if f"ed map:emergency department:{zone}" in k]
        if not zone_keys:
            zone_keys = [f"<spawn_loc>{zone}"] if f"<spawn_loc>{zone}" in maze.address_tiles else []
        if zone_keys:
            self.scratch.next_step = random.choice(zone_keys)
            self.scratch.act_description = "Standing by"
            self.scratch.occupied = None
            self.scratch.last_idle_move_time = curr_time