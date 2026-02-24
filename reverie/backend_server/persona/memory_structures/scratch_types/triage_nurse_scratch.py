import sys
import datetime
import json
import sys

sys.path.append('../../')
from persona.memory_structures.scratch import *
from global_methods import *

class triage_nurse_scratch(Scratch):
    def __init__(self, f_saved):
        super().__init__(f_saved)
        self.chatting_patient = None

        if check_if_file_exists(f_saved): 
            scratch_load = json.load(open(f_saved))

            self.chatting_patient =  scratch_load["chatting_patient"]

                
    def save(self, out_json):
        scratch = super().save(out_json)
        scratch["chatting_patient"] = self.chatting_patient

        with open(out_json, "w") as outfile:
            json.dump(scratch, outfile, indent=2)  