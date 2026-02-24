import sys
import datetime
import json

sys.path.append('../../')
from persona.memory_structures.scratch import *
from global_methods import *

class patient_scratch(Scratch):
    def __init__(self, f_saved):
        super().__init__(f_saved)
        self.ICD = None
        self.CTAS = None
        self.next_room = None
        self.state = None
        self.time_to_next = None
        self.exempt_from_data_collection = False
        self.left_without_being_seen = False
        self.left_without_being_seen_time = None
        self.left_without_being_seen_state = None
        self.left_without_being_seen_wait_minutes = None
        self.walkout_last_check_minute = 0.0
        self.walkout_recorded = False
        self.lingering_after_discharge = False
        self.linger_started_at = None
        self.linger_end_time = None
        self.linger_duration_minutes = None
        self.linger_recorded = False
        self.bed_assignment = None
        self.initial_assessment_ready_at = None
        self.disposition_ready_at = None
        self.exit_ready_at = None
        self.stage1_minutes = None
        self.stage1_surge_extra = None
        self.stage2_minutes = None
        self.stage2_surge_extra = None
        self.stage3_minutes = None
        self.initial_assessment_done = False
        self.disposition_done = False
        self.in_queue = False
        self.assigned_doctor = None
        self.preload_departure_at = None
        self.testing_end_time = None
        self.admitted_to_hospital = False
        self.admission_boarding_start = None
        self.admission_boarding_end = None
        if check_if_file_exists(f_saved):

            scratch_load = json.load(open(f_saved))
            
            self.ICD =  scratch_load["ICD"]
            self.CTAS = scratch_load["CTAS"]
            self.next_room = scratch_load["next_room"]
            self.state = scratch_load["state"]
            # self.injuries_zone = scratch_load["injuries_zone"]
            self.injuries_zone = scratch_load.get("injuries_zone")
            if scratch_load["time_to_next"]: 
                self.time_to_next = datetime.datetime.strptime(scratch_load["time_to_next"],
                                                            "%B %d, %Y, %H:%M:%S")
                
            self.exempt_from_data_collection = scratch_load["exempt_from_data_collection"]
            self.left_without_being_seen = scratch_load.get("left_without_being_seen", False)
            left_time = scratch_load.get("left_without_being_seen_time")
            if left_time:
                self.left_without_being_seen_time = datetime.datetime.strptime(left_time, "%B %d, %Y, %H:%M:%S")
            self.left_without_being_seen_state = scratch_load.get("left_without_being_seen_state")
            self.left_without_being_seen_wait_minutes = scratch_load.get("left_without_being_seen_wait_minutes")
            self.walkout_last_check_minute = scratch_load.get("walkout_last_check_minute", 0.0)
            self.walkout_recorded = scratch_load.get("walkout_recorded", False)

            self.lingering_after_discharge = scratch_load.get("lingering_after_discharge", False)
            linger_start = scratch_load.get("linger_started_at")
            if linger_start:
                self.linger_started_at = datetime.datetime.strptime(linger_start, "%B %d, %Y, %H:%M:%S")
            linger_end = scratch_load.get("linger_end_time")
            if linger_end:
                self.linger_end_time = datetime.datetime.strptime(linger_end, "%B %d, %Y, %H:%M:%S")

                self.linger_duration_minutes = scratch_load.get("linger_duration_minutes")
                self.linger_recorded = scratch_load.get("linger_recorded", False)
            self.bed_assignment = scratch_load.get("bed_assignment")

            ia_ready = scratch_load.get("initial_assessment_ready_at")
            if ia_ready:
                self.initial_assessment_ready_at = datetime.datetime.strptime(ia_ready, "%B %d, %Y, %H:%M:%S")
            disp_ready = scratch_load.get("disposition_ready_at")
            if disp_ready:
                self.disposition_ready_at = datetime.datetime.strptime(disp_ready, "%B %d, %Y, %H:%M:%S")
            exit_ready = scratch_load.get("exit_ready_at")
            if exit_ready:
                self.exit_ready_at = datetime.datetime.strptime(exit_ready, "%B %d, %Y, %H:%M:%S")
            self.stage1_minutes = scratch_load.get("stage1_minutes")
            self.stage1_surge_extra = scratch_load.get("stage1_surge_extra")
            self.stage2_minutes = scratch_load.get("stage2_minutes")
            self.stage2_surge_extra = scratch_load.get("stage2_surge_extra")
            self.stage3_minutes = scratch_load.get("stage3_minutes")
            self.initial_assessment_done = scratch_load.get("initial_assessment_done", False)
            self.disposition_done = scratch_load.get("disposition_done", False)
            self.in_queue = scratch_load.get("in_queue", False)
            self.assigned_doctor = scratch_load.get("assigned_doctor", None)
            preload_dep = scratch_load.get("preload_departure_at")
            if preload_dep:
                self.preload_departure_at = datetime.datetime.strptime(preload_dep, "%B %d, %Y, %H:%M:%S")
            testing_end = scratch_load.get("testing_end_time")
            if testing_end:
                self.testing_end_time = datetime.datetime.strptime(testing_end, "%B %d, %Y, %H:%M:%S")

            self.admitted_to_hospital = scratch_load.get("admitted_to_hospital", False)
            boarding_start = scratch_load.get("admission_boarding_start")
            if boarding_start:
                self.admission_boarding_start = datetime.datetime.strptime(boarding_start, "%B %d, %Y, %H:%M:%S")
            boarding_end = scratch_load.get("admission_boarding_end")
            if boarding_end:
                self.admission_boarding_end = datetime.datetime.strptime(boarding_end, "%B %d, %Y, %H:%M:%S")

    def save(self, out_json):
        scratch = super().save(out_json)
        scratch["ICD"] = self.ICD
        scratch["CTAS"] = self.CTAS 
        scratch["next_room"] = self.next_room
        scratch["state"] = self.state
        scratch["injuries_zone"] = self.injuries_zone

        if self.time_to_next:
            scratch["time_to_next"] = (self.time_to_next
                                        .strftime("%B %d, %Y, %H:%M:%S"))
        else:
            scratch["time_to_next"] = None

        scratch["exempt_from_data_collection"] = self.exempt_from_data_collection
        scratch["left_without_being_seen"] = self.left_without_being_seen
        scratch["left_without_being_seen_time"] = (self.left_without_being_seen_time.strftime("%B %d, %Y, %H:%M:%S")
                                                   if self.left_without_being_seen_time else None)
        scratch["left_without_being_seen_state"] = self.left_without_being_seen_state
        scratch["left_without_being_seen_wait_minutes"] = self.left_without_being_seen_wait_minutes
        scratch["walkout_last_check_minute"] = self.walkout_last_check_minute
        scratch["walkout_recorded"] = self.walkout_recorded
        scratch["lingering_after_discharge"] = self.lingering_after_discharge
        scratch["linger_started_at"] = (self.linger_started_at.strftime("%B %d, %Y, %H:%M:%S")
                                        if self.linger_started_at else None)
        scratch["linger_end_time"] = (self.linger_end_time.strftime("%B %d, %Y, %H:%M:%S")
                                      if self.linger_end_time else None)
        scratch["linger_duration_minutes"] = self.linger_duration_minutes
        scratch["linger_recorded"] = self.linger_recorded
        scratch["bed_assignment"] = self.bed_assignment
        scratch["initial_assessment_ready_at"] = (self.initial_assessment_ready_at.strftime("%B %d, %Y, %H:%M:%S")
                                                 if self.initial_assessment_ready_at else None)
        scratch["disposition_ready_at"] = (self.disposition_ready_at.strftime("%B %d, %Y, %H:%M:%S")
                                           if self.disposition_ready_at else None)
        scratch["exit_ready_at"] = (self.exit_ready_at.strftime("%B %d, %Y, %H:%M:%S")
                                    if self.exit_ready_at else None)
        scratch["stage1_minutes"] = self.stage1_minutes
        scratch["stage1_surge_extra"] = self.stage1_surge_extra
        scratch["stage2_minutes"] = self.stage2_minutes
        scratch["stage2_surge_extra"] = self.stage2_surge_extra
        scratch["stage3_minutes"] = self.stage3_minutes
        scratch["initial_assessment_done"] = self.initial_assessment_done
        scratch["disposition_done"] = self.disposition_done
        scratch["in_queue"] = self.in_queue
        scratch["assigned_doctor"] = self.assigned_doctor
        scratch["preload_departure_at"] = (self.preload_departure_at.strftime("%B %d, %Y, %H:%M:%S")
                                           if self.preload_departure_at else None)
        scratch["testing_end_time"] = (self.testing_end_time.strftime("%B %d, %Y, %H:%M:%S")
                                       if self.testing_end_time else None)
        scratch["admitted_to_hospital"] = self.admitted_to_hospital
        scratch["admission_boarding_start"] = (self.admission_boarding_start.strftime("%B %d, %Y, %H:%M:%S")
                                               if self.admission_boarding_start else None)
        scratch["admission_boarding_end"] = (self.admission_boarding_end.strftime("%B %d, %Y, %H:%M:%S")
                                             if self.admission_boarding_end else None)
        with open(out_json, "w") as outfile:
            json.dump(scratch, outfile, indent=2)  
