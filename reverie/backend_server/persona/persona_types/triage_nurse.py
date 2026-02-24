
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
from persona.memory_structures.scratch_types.triage_nurse_scratch import *

class Triage_Nurse(Persona):
    priority_factor = 0
    def __init__(self, name, folder_mem_saved=False, role=None, seed=0):
        super().__init__(name,folder_mem_saved,role,seed)
        scratch_saved = f"{folder_mem_saved}/bootstrap_memory/scratch.json"
        self.scratch = triage_nurse_scratch(scratch_saved)

    def _should_skip_cognition(self):
        """Skip LLM perceive/retrieve/plan when the triage nurse is
        already in a conversation."""
        if self.scratch.chatting_with:
            return True
        return False

    def move(self, maze, personas, curr_tile, curr_time, data_collection):
        plan = super().move(maze, personas, curr_tile, curr_time, data_collection)

        # Validate chatting_patient still exists in the simulation
        if self.scratch.chatting_patient and self.scratch.chatting_patient not in personas:
            print(f"(TriageNurse) {self.name}: clearing stale chatting_patient={self.scratch.chatting_patient}")
            self.scratch.chatting_patient = None

        # Special condition for patient to do whatever the medical staff tells them. next_step changed in plan.py.
        # To easily control what a patient should do next in a given room

        # When the agent isn't talking to anyone control their movements or update state of world
        if(self.scratch.chatting_with == None):
            # If they had chatted to a patient add them to the waitlist for a bed
            if(self.scratch.chatting_patient):
                # Amount of patients in triage goes down
                if maze.triage_patients > 0:
                    maze.triage_patients -= 1
                print(self.scratch.chatting_patient)
                patient_name = self.scratch.chatting_patient
                patient = personas.get(patient_name)
                if patient:
                    ctas = patient.scratch.CTAS if patient.scratch.CTAS is not None else 3
                    bisect.insort_right(
                        maze.patients_waiting_for_doctor,
                        [ctas * self.priority_factor, patient_name]
                    )

                    # Add patient to priority list for bedside nurse assisstance
                    if ctas != 1:
                        bisect.insort_right(
                            maze.injuries_zones["bedside_nurse_waiting"],
                            [ctas * self.priority_factor, patient_name]
                        )
                    # If they have been assigned a CTAS page a nurse to treat patient as quickly as possible.
                    else:
                        bisect.insort_right(
                            maze.injuries_zones["pager"],
                            [ctas * self.priority_factor, patient.name]
                        )
                self.scratch.chatting_patient = None

            # Move patient into triage room when there is room to fit them
            if(maze.triage_queue != [] and maze.triage_patients < maze.triage_capacity):
                # Pop from the triage queue to grab Patient that been waiting the longest
                persona_name = maze.triage_queue.pop(0)
                patient = personas.get(persona_name)
                if patient:
                    patient.to_triage(self)
                    maze.triage_patients += 1
                self.scratch.next_step = f"<persona> {persona_name}"
            self.scratch.act_address = "ed map:emergency department:triage room:computer"
            plan = self.scratch.act_address
        return self.execute(maze, personas, plan)  

    def react_to_chat(self, convo_summary, other_persona, maze):
        if(other_persona.role == "Patient"):
            # While only in the triage room
            # To set up adding Patient to Bedside Nurse queue when done talking 
            if(other_persona.scratch.state == "TRIAGE"):
                self.scratch.chatting_patient = other_persona.name

    def decide_to_chat(self, target_persona):
        if(target_persona.role == "Patient"):
            if(target_persona.scratch.state == "TRIAGE"):
                return True
            else:
                return False
        # No staff-to-staff conversations — skip LLM fallthrough
        return False
    def get_spawn_loc(self, maze):
        return list(maze.address_tiles[f"ed map:emergency department:triage room:chair"])[int(self.name.split(' ')[-1]) % len(maze.address_tiles["ed map:emergency department:triage room:chair"])] 

        # return random.choice(list(maze.address_tiles["<spawn_loc>triage room"]))
    #ed map:emergency department:triage room:chair
