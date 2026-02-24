
import datetime
import math
import random 
import sys
import time
import heapq
import bisect

sys.path.append('../../')
from persona.persona import *
from persona.memory_structures.scratch import *
from persona.memory_structures.scratch_types.doctor_scratch import *

class Doctor(Persona):

    doctor_resting_time = 15  # in minutes
    priority_factor = 3
    max_patients = 5
    idle_move_min_interval_minutes = 15
    queue_aging_interval_minutes = 15  # How often to decrease queue priorities
    queue_aging_decrement = 2          # Amount to decrease per aging tick

    # Patients in these states are effectively done — don't count toward capacity
    TERMINAL_STATES = frozenset({"WAITING_FOR_EXIT", "LEAVING", "DISCHARGED_WAITING", "ADMITTED_BOARDING"})


    def __init__(self, name, folder_mem_saved=False, role=None, seed=0):
        super().__init__(name,folder_mem_saved,role,seed=seed)
        scratch_saved = f"{folder_mem_saved}/bootstrap_memory/scratch.json"
        self.scratch = doctor_scratch(scratch_saved)

    def _should_skip_cognition(self):
        """Skip LLM perceive/retrieve/plan when the doctor is busy with
        something that doesn't require new cognitive processing."""
        # Already in a conversation — timer will handle cleanup
        if self.scratch.chatting_with:
            return True
        # Resting cooldown hasn't expired yet
        if self.scratch.time_to_next:
            return True
        # Still walking toward target — more than one step's worth of tiles away
        tps = getattr(self.scratch, '_tiles_per_step', 1)
        if len(self.scratch.planned_path) > tps + 1:
            return True
        return False

    def move(self, maze, personas, curr_tile, curr_time, data_collection):
        plan = super().move(maze, personas, curr_tile, curr_time, data_collection)

        # Validate assigned patients still exist in the simulation
        for p_name in self.scratch.assigned_patients[:]:
            if p_name not in personas or personas[p_name].scratch.state == "LEAVING":
                self.scratch.assigned_patients.remove(p_name)
                print(f"(Doctor) {self.name}: removed stale patient {p_name} from assigned_patients")
        self.scratch.assigned_patients_waitlist[:] = [
            entry for entry in self.scratch.assigned_patients_waitlist
            if entry[1] in personas and personas[entry[1]].scratch.state != "LEAVING"
        ]
        # If next_step targets a persona that left, clear it
        if self.scratch.next_step and "<persona>" in str(self.scratch.next_step):
            target = str(self.scratch.next_step).split("<persona>")[-1].strip()
            if target not in personas:
                self.scratch.next_step = None
                print(f"(Doctor) {self.name}: cleared stale next_step targeting {target}")

        # Keep the "available doctors" list consistent and free of duplicates.
        in_list = self.name in maze.doctors_taking_more_patients
        active_count = self._active_patient_count(personas)
        if active_count < self.max_patients and maze.patients_waiting_for_doctor != []:
            # Only assign patients who are actually in a bed and ready for
            # assessment.  Patients still in WAITING_FOR_NURSE have not been
            # transported by a bedside nurse yet, so assigning them wastes a
            # doctor slot and stalls throughput.
            ready_states = {"WAITING_FOR_FIRST_ASSESSMENT", "WAITING_FOR_TEST",
                            "GOING_FOR_TEST", "WAITING_FOR_RESULT",
                            "WAITING_FOR_DOCTOR"}
            selected = None
            i = 0
            while i < len(maze.patients_waiting_for_doctor):
                entry = maze.patients_waiting_for_doctor[i]
                p = personas.get(entry[1])
                if not p:
                    # Stale entry — clean it and keep looking
                    maze.patients_waiting_for_doctor.pop(i)
                    continue
                if p.scratch.state in ready_states:
                    selected = maze.patients_waiting_for_doctor.pop(i)
                    break
                i += 1
            if selected:
                patient = personas.get(selected[1])
                if patient:
                    self.assign_patient(maze.doctors_taking_more_patients, patient, personas)
            if not in_list and active_count < self.max_patients:
                maze.doctors_taking_more_patients.append(self.name)


        # Special condition for patient to do whatever the medical staff tells them. next_step changed in plan.py.
        # To easily control what a patient should do next in a given room
        if(self.scratch.time_to_next):
            if curr_time >= self.scratch.time_to_next:
                self.scratch.time_to_next = None

        elif(self.scratch.chatting_with == None and self.scratch.time_to_next == None):
            queue = self.scratch.assigned_patients_waitlist

            # Age queue entries periodically so long-waiting CTAS 3-5 patients eventually get seen
            if queue and curr_time:
                last_aged = getattr(self.scratch, '_last_queue_aging_time', None)
                if not last_aged or (curr_time - last_aged) >= datetime.timedelta(minutes=self.queue_aging_interval_minutes):
                    self.scratch._last_queue_aging_time = curr_time
                    for entry in queue:
                        entry[0] = max(1, entry[0] - self.queue_aging_decrement)
                    # Sort by priority only; Python's sort is stable, so FIFO is preserved for ties.
                    queue.sort(key=lambda entry: entry[0])

            # If they were chatting with Patient add them to the bedside nurse queue for transfer to testing
            # self.scratch.chatting is assigned in react_to_chat method
            
            if(self.scratch.chatting_patient):
                # Reset variable — patient now self-manages testing
                self.scratch.chatting_patient = None
                self.scratch.time_to_next = curr_time + datetime.timedelta(minutes=self.doctor_resting_time)
                
            # Check if any Patients are in Queue
            # Also that they are not occupied with another task
            elif(queue != [] and self.scratch.next_step == None):
                # Deterministic selection — queue is already sorted by
                # priority (lowest CTAS first, aged over time for fairness).
                patient_assessment = queue.pop(0)

                data_collection["Patients_Attended"].append([patient_assessment[0], patient_assessment[1]])

                target_name = str(patient_assessment[1]).strip()
                self.scratch.next_step = f"<persona> {patient_assessment[1]}"

                # Deterministic state transition — don't wait for chat.
                # The doctor still walks to the patient (for realism), but
                # the patient's state advances immediately.
                patient = personas.get(target_name)
                if patient:
                    patient.do_initial_assessment(self, maze)
                    patient.do_disposition(self, maze)
 
            # Force Patient to go somewhere
            if(self.scratch.next_step != None):
                plan = self.scratch.next_step

                # So the act_address works more friendly with other parts when going towards a persona
                self.scratch.act_address = plan.split("> ")[-1]
            else:
                # Light idle rounding so doctors appear busy even when queue is empty
                idle = self._set_idle_rounding(maze, personas, curr_time)
                if idle:
                    plan = idle
                    self.scratch.act_address = idle
                    self.scratch.act_path_set = False
        print("Plan: " + plan)

        return self.execute(maze, personas, plan)  
    
    def react_to_chat(self, convo_summary, other_persona, maze):
        # State transitions are now handled deterministically when the
        # doctor selects the patient from the waitlist.  This method is
        # kept for flavor — chats still happen but don't gate progression.
        if("Patient" == other_persona.role):
            print(other_persona.name)
            self.scratch.chatting_patient = other_persona.name

            # Idempotent fallback — disposition may already have been
            # applied at selection time, but remove_patient is safe to
            # call multiple times.
            if other_persona.scratch.state == "WAITING_FOR_DOCTOR":
                self.remove_patient(other_persona, maze)

            self.scratch.next_step = None


    def decide_to_chat(self, target_persona):
        # If the doctor is walking to someone force them to talk with them
        if(target_persona.name in str(self.scratch.next_step)):
            self.scratch.next_step = None
            return True
        # If a Patient is not in a bed doctor will not talk with them
        elif(target_persona.role == "Patient"):
            return False
        # No staff-to-staff conversations — skip LLM fallthrough
        return False
    
    def data_collection_dict(self):
        new_dict = {}

        new_dict["Patients_Attended"] = []
        return new_dict
    
    # Spawn location in major injuries zone
    def get_spawn_loc(self, maze):
        return random.choice(list(maze.address_tiles["<spawn_loc>major injuries zone"]))

    def _set_idle_rounding(self, maze, personas, curr_time):
        """
        Lightweight idle movement so doctors don't look idle; wanders within the zone.
        """
        if self.scratch.last_idle_move_time and curr_time:
            cooldown = datetime.timedelta(minutes=self.idle_move_min_interval_minutes)
            if curr_time - self.scratch.last_idle_move_time < cooldown:
                return False

        zone = "major injuries zone"

        # Wander to a location in the zone (no patient approach to avoid triggering conversations)
        zone_keys = [k for k in maze.address_tiles.keys() if f"ed map:emergency department:{zone}" in k]
        if zone_keys:
            self.scratch.last_idle_move_time = curr_time
            return random.choice(zone_keys)

        return False
    
    def _active_patient_count(self, personas):
        """Count assigned patients NOT in terminal states (done/leaving)."""
        count = 0
        for p_name in self.scratch.assigned_patients:
            p = personas.get(p_name)
            if p and p.scratch.state not in self.TERMINAL_STATES:
                count += 1
        return count

    def assign_patient(self, queue, patient, personas=None):
        if(patient.name not in self.scratch.assigned_patients):
            self.scratch.assigned_patients.append(patient.name)
            patient.scratch.assigned_doctor = self.name
        active = self._active_patient_count(personas) if personas else len(self.scratch.assigned_patients)
        if active >= self.max_patients:
            # Remove all occurrences so the doctor isn't considered available.
            while self.name in queue:
                queue.remove(self.name)

    def remove_patient(self, persona, maze, personas=None):
        if persona.name in self.scratch.assigned_patients:
            self.scratch.assigned_patients.remove(persona.name)
        # Use active count when personas dict is available; fallback to raw length
        count = self._active_patient_count(personas) if personas else len(self.scratch.assigned_patients)
        if (count < self.max_patients
            and self.name not in maze.doctors_taking_more_patients
            ):
                maze.doctors_taking_more_patients.append(self.name)

