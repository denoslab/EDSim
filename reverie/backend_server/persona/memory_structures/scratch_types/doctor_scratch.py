import sys
import datetime
import json
import sys

sys.path.append('../../')
from persona.memory_structures.scratch import *
from global_methods import *

class doctor_scratch(Scratch):
    def __init__(self, f_saved):
        super().__init__(f_saved)
        self.chatting_patient = None
        self.time_to_next = None
        self.last_idle_move_time = None
        self.assigned_patients = []
        self.assigned_patients_waitlist = []
        if check_if_file_exists(f_saved): 
            scratch_load = json.load(open(f_saved))
            if("chatting_patient" in scratch_load):
                self.chatting_patient = scratch_load["chatting_patient"]
            if("time_to_next" in scratch_load):
                if scratch_load["time_to_next"]: 
                    self.time_to_next = datetime.datetime.strptime(scratch_load["time_to_next"],
                                                                "%B %d, %Y, %H:%M:%S")
            if scratch_load.get("last_idle_move_time"):
                self.last_idle_move_time = datetime.datetime.strptime(
                    scratch_load["last_idle_move_time"], "%B %d, %Y, %H:%M:%S"
                )
            self.assigned_patients = scratch_load.get("assigned_patients", [])
            self.assigned_patients_waitlist = scratch_load.get("assigned_patients_waitlist", [])

                
    def save(self, out_json):
        scratch = super().save(out_json)

        scratch["chatting_patient"] = self.chatting_patient
        if self.time_to_next:
            scratch["time_to_next"] = (self.time_to_next
                                        .strftime("%B %d, %Y, %H:%M:%S"))
        else:
            scratch["time_to_next"] = None
            
        if self.last_idle_move_time:
            scratch["last_idle_move_time"] = self.last_idle_move_time.strftime("%B %d, %Y, %H:%M:%S")
        else:
            scratch["last_idle_move_time"] = None

        scratch["assigned_patients"] = self.assigned_patients
        scratch["assigned_patients_waitlist"] = self.assigned_patients_waitlist
        with open(out_json, "w") as outfile:
            json.dump(scratch, outfile, indent=2)  

