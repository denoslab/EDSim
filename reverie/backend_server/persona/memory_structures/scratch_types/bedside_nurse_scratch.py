import sys
import datetime
import json
import sys

sys.path.append('../../')
from persona.memory_structures.scratch import *
from global_methods import *

class bedside_nurse_scratch(Scratch):
    def __init__(self, f_saved):
        super().__init__(f_saved)
        self.occupied = None
        self.time_to_next = None
        self.last_idle_move_time = None

        if check_if_file_exists(f_saved): 
            scratch_load = json.load(open(f_saved))

            self.occupied =  scratch_load["occupied"]

            if scratch_load["time_to_next"]:
                self.time_to_next = datetime.datetime.strptime(
                    scratch_load["time_to_next"], "%B %d, %Y, %H:%M:%S"
                )
            if scratch_load.get("last_idle_move_time"):
                self.last_idle_move_time = datetime.datetime.strptime(
                    scratch_load["last_idle_move_time"], "%B %d, %Y, %H:%M:%S"
                )

                
    def save(self, out_json):
        scratch = super().save(out_json)
        scratch["occupied"] = self.occupied

        if self.time_to_next:
            scratch["time_to_next"] = (self.time_to_next
                                        .strftime("%B %d, %Y, %H:%M:%S"))
        else:
            scratch["time_to_next"] = None
        if self.last_idle_move_time:
            scratch["last_idle_move_time"] = self.last_idle_move_time.strftime("%B %d, %Y, %H:%M:%S")
        else:
            scratch["last_idle_move_time"] = None

        with open(out_json, "w") as outfile:
            json.dump(scratch, outfile, indent=2)  
