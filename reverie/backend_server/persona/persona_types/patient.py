
import datetime
import random
import sys
import bisect
sys.path.append('../../')
from persona.persona import *
from persona.memory_structures.scratch_types.patient_scratch import patient_scratch


class Patient(Persona):
    state_to_act_pronunciatio = {
        "WAITING_FOR_TRIAGE": "\u231b",
        "TRIAGE": "\u2695\uFE0F",
        "WAITING_FOR_NURSE": "\u231b",
        "WAITING_FOR_FIRST_ASSESSMENT": "\uD83D\uDECC",
        "WAITING_FOR_TEST": "\u231b",
        "GOING_FOR_TEST": "\uD83D\uDEB6\u200D\u2642\uFE0F",
        "WAITING_FOR_RESULT": "\u231b",
        "WAITING_FOR_DOCTOR": "\u231b",
        "ADMITTED_BOARDING": "\U0001f3e5"
        }

    time_increment = 0 # In minutes
    priority_factor = 0
    testing_result_time = 0
    testing_time = 0  # In minutes, set from meta.json
    testing_probability_by_ctas = {"1": 1.0, "2": 0.8, "3": 0.5, "4": 0.3, "5": 0.0}
    walkout_probability = 0.0
    walkout_check_minutes = 20
    post_discharge_linger_probability = 0.0
    post_discharge_linger_minutes = 0
    simulate_hospital_admission = False
    admission_probability_by_ctas = {}
    admission_boarding_minutes_min = 60
    admission_boarding_minutes_max = 480
    walkout_states = {
        "WAITING_FOR_TRIAGE",
        "TRIAGE",
        "WAITING_FOR_NURSE",
        "WAITING_FOR_TEST",
        "WAITING_FOR_RESULT",
        "WAITING_FOR_DOCTOR",
        "WAITING_FOR_EXIT",
        "WAITING_FOR_FIRST_ASSESSMENT",
    }
    def __init__(self, name, folder_mem_saved=False, role=None, ICD = None, seed=0):
        super().__init__(name,folder_mem_saved,role, seed)
        
        # <scratch> is the persona's scratch (short term memory) space. 
        scratch_saved = f"{folder_mem_saved}/bootstrap_memory/scratch.json"
        self.scratch = patient_scratch(scratch_saved)
        self.role = role
        # Default settings
        if(self.scratch.state == None):
            self.scratch.state = "WAITING_FOR_TRIAGE"
        if(self.scratch.next_step == None):
            self.scratch.next_step = "ed map:emergency department:waiting room:waiting room chair"
        if(self.scratch.ICD == None):
            self.scratch.ICD = ICD



    def _target_bed(self, maze, zone):
        if not zone:
            return None
        bed = maze.assign_bed(self.name, zone, self.scratch.bed_assignment)
        if bed:
            self.scratch.bed_assignment = list(bed)
            return maze.get_bed_address(zone, bed)
        return None

    def _release_bed(self, maze):
        """
        Free up the patient's bed assignment so capacity is not blocked.
        Safe to call multiple times.
        
        """

        maze.discharge_patient(self.name, self.scratch.injuries_zone)
        self.scratch.bed_assignment = None


    def move(self, maze, personas, curr_tile, curr_time, data_collection):
        # Area
        if( maze.tiles[curr_tile[1]][curr_tile[0]]['arena'] not in data_collection["time_spent_area"].keys()):
            data_collection["time_spent_area"][maze.tiles[curr_tile[1]][curr_tile[0]]['arena']] = self.time_increment
        else:
            data_collection["time_spent_area"][maze.tiles[curr_tile[1]][curr_tile[0]]['arena']] += self.time_increment

        # State
        if ( self.scratch.state not in data_collection["time_spent_state"].keys()):
            data_collection["time_spent_state"][self.scratch.state] = self.time_increment
        else:
            data_collection["time_spent_state"][self.scratch.state] += self.time_increment

        # Free up the bed once the patient has started leaving so capacity is not blocked.
        if self.scratch.state == "LEAVING":
            self._release_bed(maze)

        data_collection.setdefault("left_department_by_choice", {"occurred": False})
        data_collection.setdefault("lingered_after_discharge", {"occurred": False})
        data_collection.setdefault("admitted_to_hospital", {"occurred": False})

        # Generate if Patient should leave the ED right now
        if (
            self.walkout_probability > 0
            and not self.scratch.left_without_being_seen
            and self.scratch.state in self.walkout_states
            and not self.scratch.chatting_with
            and not self.scratch.time_to_next
        ):
            waited_minutes = data_collection["time_spent_state"][self.scratch.state]
            last_check = getattr(self.scratch, "walkout_last_check_minute", 0.0) or 0.0
            if waited_minutes - last_check >= self.walkout_check_minutes:
                self.scratch.walkout_last_check_minute = waited_minutes
                if random.random() <= self.walkout_probability:
                    self._initiate_walkout(maze, data_collection, waited_minutes, curr_time, personas)

        if self.scratch.lingering_after_discharge and not self.scratch.linger_recorded:
            data_collection["lingered_after_discharge"] = {
                "occurred": True,
                "decided_at": (self.scratch.linger_started_at.strftime("%B %d, %Y, %H:%M:%S")
                               if self.scratch.linger_started_at else None),
                "expected_duration_minutes": self.scratch.linger_duration_minutes,
            }
            self.scratch.linger_recorded = True

        if (
            self.scratch.lingering_after_discharge
            and self.scratch.linger_end_time
            and curr_time
            and curr_time >= self.scratch.linger_end_time
            and self.scratch.state == "DISCHARGED_WAITING"
        ):
            self._release_bed(maze)
            self.scratch.lingering_after_discharge = False
            self.scratch.state = "LEAVING"
            self.scratch.next_step = "ed map:emergency department:exit"
            self.scratch.act_path_set = False
            entry = data_collection.get("lingered_after_discharge")
            if isinstance(entry, dict) and entry.get("occurred"):
                entry["ended_at"] = curr_time.strftime("%B %d, %Y, %H:%M:%S")


        # plan = super().move(maze, personas, curr_tile, curr_time, data_collection)
        self.scratch.curr_tile = curr_tile
        print("curr_tile",curr_tile)

        self.scratch.curr_time = curr_time

        #Check for available doctor and assign if there isn't one already assigned and patient isn't waiting for triage or waiting for nurse
        # if(not self.scratch.assigned_doctor and self.scratch.state not in ["WAITING_FOR_TRIAGE", "TRIAGE", "WAITING_FOR_NURSE", "LEAVING"] 
        #    and maze.doctors_taking_more_patients != []):
        #     self.scratch.assigned_doctor = random.choice(maze.doctors_taking_more_patients)
        #     personas[self.scratch.assigned_doctor].assign_patient(maze.doctors_taking_more_patients, self)
        #     maze.patients_waiting_for_doctor.remove(self.name)

        # Check if the Patient chatting time is over
        if(self.scratch.chatting_end_time):
            if (self.scratch.chatting_end_time <= curr_time):
                # Reset variables back to default
                self.scratch.chatting_with = None
                self.scratch.chat  = None
                self.scratch.chatting_end_time  = None
                self.scratch.act_path_set = False

        # Special condition for patient to do whatever the medical staff tells them. next_step changed in plan.py.
        # To easily control what a patient should do next in a given room

        # If Patient isn't talking with other agent, control their movement
        if(self.scratch.chatting_with == None):
            assigned_doctor = personas.get(str(self.scratch.assigned_doctor), None)

            # If assigned_doctor name is set but the doctor object is gone, clear
            # the stale reference so the patient can be re-assigned.
            if self.scratch.assigned_doctor is not None and assigned_doctor is None:
                print(f"(Patient) {self.name}: clearing stale assigned_doctor "
                      f"'{self.scratch.assigned_doctor}' (not found in personas)")
                self.scratch.assigned_doctor = None

            if(self.scratch.assigned_doctor == None):
                # If waiting for results with timer expired but no doctor, transition
                # to WAITING_FOR_DOCTOR so rescue mechanism can re-assign one.
                if (self.scratch.state == "WAITING_FOR_RESULT"
                    and self.scratch.time_to_next
                    and self.scratch.curr_time >= self.scratch.time_to_next):
                    self.scratch.state = "WAITING_FOR_DOCTOR"
                    priority = self.scratch.CTAS * (self.priority_factor / 2) if self.scratch.CTAS else 3
                    already_queued = any(entry[1] == self.name for entry in maze.patients_waiting_for_doctor)
                    if not already_queued:
                        bisect.insort_right(maze.patients_waiting_for_doctor,
                                            [priority, self.name])
                    print(f"(Patient) {self.name}: no doctor assigned, moved from "
                          f"WAITING_FOR_RESULT to WAITING_FOR_DOCTOR")

            # If they are waiting for test results check if results came back
            elif(
                self.scratch.state == "WAITING_FOR_RESULT"
                and self.scratch.time_to_next
                and self.scratch.curr_time >= self.scratch.time_to_next
                and assigned_doctor is not None
            ):
                queue = assigned_doctor.scratch.assigned_patients_waitlist

                ready_for_disposition = True
                # If a staged disposition time is set, ensure we've reached it
                if self.scratch.disposition_ready_at and self.scratch.curr_time < self.scratch.disposition_ready_at:
                    ready_for_disposition = False
                already_in_queue = any(entry[1] == self.name for entry in queue)
                if ready_for_disposition and not already_in_queue:
                    bisect.insort_right(queue,
                                    [self.scratch.CTAS * (self.priority_factor / 2), self.name])
                    self.scratch.state = "WAITING_FOR_DOCTOR"

            elif(self.scratch.state == "WAITING_FOR_FIRST_ASSESSMENT" and assigned_doctor is not None):
                queue = assigned_doctor.scratch.assigned_patients_waitlist

                bed_target = self._target_bed(maze, self.scratch.injuries_zone)
                ready_at = self.scratch.initial_assessment_ready_at
                if (not ready_at or self.scratch.curr_time >= ready_at):
                    if (bed_target
                        and (not self.scratch.in_queue)
                        and bed_target[0] == curr_tile[0]
                        and bed_target[1] == curr_tile[1]):
                        self.scratch.in_queue = True
                        if not any(entry[1] == self.name for entry in queue):
                            bisect.insort_right(queue,
                                            [self.scratch.CTAS * self.priority_factor, self.name])

            # Patient self-manages testing: check if diagnostic room has space, go directly
            elif self.scratch.state == "WAITING_FOR_TEST":
                diag_info = maze.injuries_zones.get("diagnostic room", {})
                current = diag_info.get("current_patients", [])
                capacity = diag_info.get("capacity", 5)
                if len(current) < capacity and self.name not in current:
                    # Space available — go to diagnostic room
                    current.append(self.name)
                    self.scratch.next_step = "ed map:emergency department:diagnostic room:diagnostic table"
                    self.scratch.next_room = "diagnostic room"
                    self.scratch.state = "GOING_FOR_TEST"
                    self.scratch.testing_end_time = self.scratch.curr_time + datetime.timedelta(minutes=self.testing_time)
                    self.scratch.act_path_set = False
                    # Remove from bedside_nurse_waiting if present
                    for entry in maze.injuries_zones.get("bedside_nurse_waiting", [])[:]:
                        if entry[1] == self.name:
                            maze.injuries_zones["bedside_nurse_waiting"].remove(entry)
                            break

            # Patient self-manages diagnostic testing: when testing_end_time expires,
            # leave diagnostic room and walk back to bed.
            elif(self.scratch.state == "GOING_FOR_TEST"
                 and self.scratch.testing_end_time
                 and self.scratch.curr_time >= self.scratch.testing_end_time):
                diag_patients = maze.injuries_zones["diagnostic room"].get("current_patients", [])
                if self.name in diag_patients:
                    diag_patients.remove(self.name)
                self.scratch.testing_end_time = None
                bed_target = self._target_bed(maze, self.scratch.injuries_zone)
                if bed_target:
                    self.scratch.next_step = f"<tile> {bed_target}"
                else:
                    self.scratch.next_step = f"ed map:emergency department:{self.scratch.injuries_zone}:bed"
                self.scratch.next_room = self.scratch.injuries_zone
                self.scratch.time_to_next = self.scratch.curr_time + datetime.timedelta(minutes=self.testing_result_time)
                self.scratch.state = "WAITING_FOR_RESULT"
                self.scratch.act_path_set = False
                # Surge extra: push disposition gate forward so surge
                # slowdown is experienced in-bed after testing.
                surge_extra = float(self.scratch.stage2_surge_extra or 0)
                if surge_extra > 0:
                    self.scratch.disposition_ready_at = (
                        max(self.scratch.disposition_ready_at or self.scratch.curr_time,
                            self.scratch.curr_time)
                        + datetime.timedelta(minutes=surge_extra)
                    )

            # Safety: if GOING_FOR_TEST but no testing_end_time, auto-set it
            elif (self.scratch.state == "GOING_FOR_TEST" and not self.scratch.testing_end_time):
                self.scratch.testing_end_time = self.scratch.curr_time + datetime.timedelta(minutes=self.testing_time)

            plan = str(self.scratch.next_step)

            # If the plan doesn't match the last assigned act_address
            # Means that the plan has changed and the Patient has to move now
            if(plan != self.scratch.act_address):
                # Patient now has to move to new position
                self.scratch.act_path_set = False
                self.scratch.act_address = plan.split("> ")[-1]

            # Patient leaves the ED
            if self.scratch.state == "WAITING_FOR_EXIT" and self.scratch.exit_ready_at and self.scratch.curr_time >= self.scratch.exit_ready_at:
                self.scratch.state = "LEAVING"
                self._release_bed(maze)
                self.scratch.next_step = "ed map:emergency department:exit"
                self.scratch.act_path_set = False

            # Admitted patient finishes boarding and leaves
            if self.scratch.state == "ADMITTED_BOARDING" and self.scratch.admission_boarding_end and self.scratch.curr_time >= self.scratch.admission_boarding_end:
                self.scratch.state = "LEAVING"
                self._release_bed(maze)
                self.scratch.next_step = "ed map:emergency department:exit"
                self.scratch.act_path_set = False

        else:
            # If they are chatting set the plan to talk with other persona
            plan = f"<persona> {self.scratch.chatting_with }"
            self.scratch.act_address = self.scratch.chatting_with 
            
        self.scratch.act_pronunciatio = self.state_to_act_pronunciatio.get(self.scratch.state, "\ud83e\udd22")

        return self.execute(maze, personas, plan)

    def _initiate_walkout(self, maze, data_collection, waited_minutes, curr_time, personas):
        """
        Trigger a patient walk-out event and remove the patient from any queues.
        """
        self.scratch.next_step = "ed map:emergency department:exit"
        self.scratch.act_path_set = False
        self.scratch.left_without_being_seen = True
        self.scratch.left_without_being_seen_time = curr_time
        self.scratch.left_without_being_seen_state = self.scratch.state
        self.scratch.left_without_being_seen_wait_minutes = waited_minutes
        self.scratch.walkout_recorded = True

        timestamp = curr_time.strftime("%B %d, %Y, %H:%M:%S") if curr_time else None
        data_collection["left_department_by_choice"] = {
            "occurred": True,
            "state": self.scratch.left_without_being_seen_state,
            "wait_minutes": waited_minutes,
            "timestamp": timestamp,
        }

        if self.name in maze.triage_queue:
            maze.triage_queue.remove(self.name)

        for entry in maze.injuries_zones["bedside_nurse_waiting"][:]:
            if entry[1] == self.name:
                maze.injuries_zones["bedside_nurse_waiting"].remove(entry)
                break

        maze.patients_waiting_for_doctor[:] = [
            entry for entry in maze.patients_waiting_for_doctor
            if not (isinstance(entry, (list, tuple)) and len(entry) >= 2 and str(entry[1]).strip() == self.name)
        ]

        self._release_bed(maze)
        assigned_doctor = personas.get(str(self.scratch.assigned_doctor), None)
        if assigned_doctor:
            assigned_doctor.remove_patient(self, maze)
            # Ensure the doctor won't keep trying to see a patient who has left.
            queue = getattr(assigned_doctor.scratch, "assigned_patients_waitlist", None)
            if isinstance(queue, list):
                queue[:] = [
                    entry
                    for entry in queue
                    if not (
                        isinstance(entry, (list, tuple))
                        and len(entry) >= 2
                        and str(entry[1]).strip() == self.name
                    )
                ]

        for entry in maze.injuries_zones["assessment_queue"][:]:
            if entry[1] == self.name:
                maze.injuries_zones["assessment_queue"].remove(entry)
                break


    def _stay_after_discharge(self, maze):
        """
        Keep a discharged patient in their bed space for additional time.
        """
        zone = self.scratch.injuries_zone or "waiting room"
        self.scratch.state = "DISCHARGED_WAITING"
        bed_target = self._target_bed(maze, zone)
        if bed_target:
            self.scratch.next_step = f"<tile> {bed_target}"
        else:
            self.scratch.next_step = f"ed map:emergency department:{zone}:bed"
        linger_start = self.scratch.curr_time or datetime.datetime.now()
        self.scratch.lingering_after_discharge = True
        self.scratch.linger_started_at = linger_start
        duration = getattr(self, "post_discharge_linger_minutes", 0) or 0
        if duration > 0:
            self.scratch.linger_duration_minutes = duration
            self.scratch.linger_end_time = linger_start + datetime.timedelta(minutes=duration)
        else:
            self.scratch.linger_duration_minutes = None
            self.scratch.linger_end_time = None
        self.scratch.linger_recorded = False


    # ------------------------------------------------------------------
    # Deterministic state transitions (called from doctor.move())
    # ------------------------------------------------------------------

    def do_initial_assessment(self, doctor, maze):
        """Transition after first doctor assessment — deterministic, no chat needed.
        Returns True if the transition was applied, False if already past this state."""
        if self.scratch.state != "WAITING_FOR_FIRST_ASSESSMENT":
            return False

        self.scratch.act_path_set = False
        self.scratch.initial_assessment_done = True

        if self.scratch.stage2_minutes is None:
            self.scratch.stage2_minutes = 0
        # Baseline gate — surge extra is added when entering WAITING_FOR_RESULT
        self.scratch.disposition_ready_at = (
            self.scratch.curr_time
            + datetime.timedelta(minutes=float(self.scratch.stage2_minutes))
        )

        # Probabilistic testing decision based on CTAS
        ctas_key = str(self.scratch.CTAS) if self.scratch.CTAS else "3"
        test_prob = float(self.testing_probability_by_ctas.get(ctas_key, 0.5))

        if random.random() < test_prob:
            self.scratch.state = "WAITING_FOR_TEST"
            self.scratch.next_room = "diagnostic room"
        else:
            # No test — enters WAITING_FOR_RESULT immediately, apply surge extra now
            self.scratch.state = "WAITING_FOR_RESULT"
            self.scratch.time_to_next = self.scratch.curr_time
            surge_extra = float(self.scratch.stage2_surge_extra or 0)
            if surge_extra > 0:
                self.scratch.disposition_ready_at = (
                    max(self.scratch.disposition_ready_at or self.scratch.curr_time,
                        self.scratch.curr_time)
                    + datetime.timedelta(minutes=surge_extra)
                )

        return True

    def do_disposition(self, doctor, maze):
        """Transition after disposition visit — deterministic, no chat needed.
        Returns True if the transition was applied, False if already past this state."""
        if self.scratch.state != "WAITING_FOR_DOCTOR":
            return False

        if self.scratch.assigned_doctor and str(self.scratch.assigned_doctor) == doctor.name:
            doctor.remove_patient(self, maze)

        self.scratch.act_path_set = False
        self.scratch.disposition_done = True

        # Check if patient should be admitted to hospital (boarding)
        if self.simulate_hospital_admission and self.admission_probability_by_ctas:
            ctas_key = str(self.scratch.CTAS) if self.scratch.CTAS else "3"
            admit_prob = float(self.admission_probability_by_ctas.get(ctas_key, 0.0))
            if random.random() < admit_prob:
                self.scratch.admitted_to_hospital = True
                self.scratch.admission_boarding_start = self.scratch.curr_time
                boarding_minutes = random.uniform(
                    self.admission_boarding_minutes_min,
                    self.admission_boarding_minutes_max,
                )
                self.scratch.admission_boarding_end = (
                    self.scratch.curr_time + datetime.timedelta(minutes=boarding_minutes)
                )
                self.scratch.state = "ADMITTED_BOARDING"
                self.scratch.next_step = (
                    f"ed map:emergency department:{self.scratch.injuries_zone}:bed"
                )
                return True

        if self.scratch.stage3_minutes is None:
            self.scratch.stage3_minutes = 0
        self.scratch.exit_ready_at = (
            self.scratch.curr_time
            + datetime.timedelta(minutes=float(self.scratch.stage3_minutes))
        )
        self.scratch.state = "WAITING_FOR_EXIT"
        self.scratch.next_step = (
            f"ed map:emergency department:{self.scratch.injuries_zone}:bed"
        )
        if (
            self.post_discharge_linger_probability > 0
            and random.random() <= self.post_discharge_linger_probability
        ):
            self._stay_after_discharge(maze)

        return True

    def react_to_chat(self, convo_summary, other_persona, maze):
        self.scratch.act_path_set = False
        if(other_persona.role == "TriageNurse"):
            # While only in the traige assessment state
            if(self.scratch.state == "TRIAGE"):
                # If talking to Triage Nurse assigned the next room to go to for the Bedside Nurse to take them there 
                self.scratch.next_room = self.scratch.injuries_zone

                self.scratch.state = "WAITING_FOR_NURSE"

                self.scratch.next_step = "ed map:emergency department:waiting room:waiting room chair"
                
        elif(other_persona.role == "BedsideNurse"):
            # State transitions are now handled deterministically when the
            # nurse picks the patient from the queue.  This block is kept as
            # an idempotent fallback — if the transition already happened,
            # the guard condition prevents double-firing.
            if(self.scratch.next_room and self.scratch.state == "WAITING_FOR_NURSE"):
                bed_target = self._target_bed(maze, self.scratch.next_room)
                if bed_target:
                    self.scratch.next_step = f"<tile> {bed_target}"
                else:
                    self.scratch.next_step = f"ed map:emergency department:{self.scratch.next_room}:bed"
                self.scratch.state = "WAITING_FOR_FIRST_ASSESSMENT"
                # Surge extra: push the assessment gate forward so
                # the surge slowdown is experienced in-bed.
                surge_extra = float(self.scratch.stage1_surge_extra or 0)
                if surge_extra > 0:
                    self.scratch.initial_assessment_ready_at = (
                        max(self.scratch.initial_assessment_ready_at or self.scratch.curr_time,
                            self.scratch.curr_time)
                        + datetime.timedelta(minutes=surge_extra)
                    )

        elif(other_persona.role == "Doctor"):
            # State transitions are now handled deterministically when the
            # doctor selects the patient from their waitlist.  These calls
            # are idempotent — they check current state before acting.
            self.do_initial_assessment(other_persona, maze)
            self.do_disposition(other_persona, maze)



                




    # Get Patient to go to Triage Room and talk to Triage Nurse
    def to_triage(self, triage_persona):
        self.scratch.next_step = f"<persona> {triage_persona.name}"
        # self.scratch.next_step = "ed map:emergency department:triage room:chair"
        self.scratch.state = "TRIAGE"

        self.scratch.act_path_set = False

    
    # Remove ability to iniate conversations
    def decide_to_chat(self, target_persona):
        return False

    # Initialize their section in the data_collection dict
    def data_collection_dict(self):
        temp_dict = {}

        temp_dict["ICD-10-CA_code"] = ""
        temp_dict["CTAS_score"] = ""
        temp_dict["injuries_zone"] = ""
        temp_dict["time_spent_area"] = {}
        temp_dict["time_spent_state"] = {}
        temp_dict["tiles_traveled"] = 0
        temp_dict["travel_time_minutes"] = 0
        temp_dict["travel_time_state"] = {}
        temp_dict["travel_time_area"] = {}
        temp_dict["exempt_from_data_collection"] = self.scratch.exempt_from_data_collection
        temp_dict["left_department_by_choice"] = {"occurred": False}
        temp_dict["lingered_after_discharge"] = {"occurred": False}
        temp_dict["admitted_to_hospital"] = {"occurred": False}
        return temp_dict
    
    # Put their data in the data_collection dict
    def save_data(self, dict):

        dict["ICD-10-CA_code"] = self.scratch.ICD
        dict["CTAS_score"] = self.scratch.CTAS
        dict["injuries_zone"] = self.scratch.injuries_zone
        dict["stage1_minutes"] = (self.scratch.stage1_minutes or 0) + (self.scratch.stage1_surge_extra or 0)
        dict["stage2_minutes"] = (self.scratch.stage2_minutes or 0) + (self.scratch.stage2_surge_extra or 0)
        dict["stage3_minutes"] = self.scratch.stage3_minutes

        walkout_entry = dict.setdefault("left_department_by_choice", {"occurred": False})
        if self.scratch.left_without_being_seen:
            walkout_entry.update({
                "occurred": True,
                "state": self.scratch.left_without_being_seen_state,
                "wait_minutes": self.scratch.left_without_being_seen_wait_minutes,
                "timestamp": (self.scratch.left_without_being_seen_time.strftime("%B %d, %Y, %H:%M:%S")
                              if self.scratch.left_without_being_seen_time else None),
            })
        else:
            walkout_entry.setdefault("occurred", False)

        linger_entry = dict.setdefault("lingered_after_discharge", {"occurred": False})
        if self.scratch.linger_started_at:
            linger_entry.update({
                "occurred": True,
                "decided_at": self.scratch.linger_started_at.strftime("%B %d, %Y, %H:%M:%S"),
                "expected_duration_minutes": self.scratch.linger_duration_minutes,
                "ended_at": (self.scratch.linger_end_time.strftime("%B %d, %Y, %H:%M:%S")
                             if self.scratch.linger_end_time and not self.scratch.lingering_after_discharge else None),
            })
        else:
            linger_entry.setdefault("occurred", False)

        admission_entry = dict.setdefault("admitted_to_hospital", {"occurred": False})
        if self.scratch.admitted_to_hospital:
            boarding_duration = None
            if self.scratch.admission_boarding_start and self.scratch.admission_boarding_end:
                boarding_duration = (self.scratch.admission_boarding_end - self.scratch.admission_boarding_start).total_seconds() / 60
            admission_entry.update({
                "occurred": True,
                "boarding_start": (self.scratch.admission_boarding_start.strftime("%B %d, %Y, %H:%M:%S")
                                   if self.scratch.admission_boarding_start else None),
                "boarding_end": (self.scratch.admission_boarding_end.strftime("%B %d, %Y, %H:%M:%S")
                                 if self.scratch.admission_boarding_end else None),
                "boarding_duration_minutes": boarding_duration,
            })
        else:
            admission_entry.setdefault("occurred", False)

        return dict
    
    # For when you want to get a location of a spawn location
    def get_spawn_loc(self, maze):
        return random.choice(list(maze.address_tiles["<spawn_loc>exit"]))

    def leave_ed(self, maze, personas, sim_folder, data_collection=None):
        persona_key = self.name

        # --- Full cleanup from all queues and zones ---
        # Triage queue
        if self.name in maze.triage_queue:
            maze.triage_queue.remove(self.name)
        # Bedside nurse waiting queue
        for entry in maze.injuries_zones.get("bedside_nurse_waiting", [])[:]:
            if entry[1] == self.name:
                maze.injuries_zones["bedside_nurse_waiting"].remove(entry)
                break
        # Assessment queue
        for entry in maze.injuries_zones.get("assessment_queue", [])[:]:
            if entry[1] == self.name:
                maze.injuries_zones["assessment_queue"].remove(entry)
                break
        # Diagnostic room current_patients
        diag_patients = maze.injuries_zones.get("diagnostic room", {}).get("current_patients", [])
        if self.name in diag_patients:
            diag_patients.remove(self.name)
        # All injury zone current_patients
        for zone_name, zone_info in maze.injuries_zones.items():
            if isinstance(zone_info, dict):
                cp = zone_info.get("current_patients", [])
                if self.name in cp:
                    cp.remove(self.name)
        # Clear any bedside nurse occupied reference
        for p in personas.values():
            if getattr(p, 'role', None) == 'BedsideNurse':
                occ = getattr(p.scratch, 'occupied', None)
                if occ and self.name in str(occ):
                    p.scratch.occupied = None
                    p.scratch.next_step = None
                    p.scratch.act_path_set = False

        # Ensure bed capacity is freed and the patient is removed from zone tracking.
        self._release_bed(maze)

        maze.patients_waiting_for_doctor[:] = [
            entry for entry in maze.patients_waiting_for_doctor
            if not (isinstance(entry, (list, tuple)) and len(entry) >= 2 and str(entry[1]).strip() == self.name)
        ]

        # Ensure the doctor won't keep tracking / queuing this patient.
        assigned_doctor = personas.get(str(self.scratch.assigned_doctor), None)
        if assigned_doctor:
            assigned_doctor.remove_patient(self, maze)
            queue = getattr(assigned_doctor.scratch, "assigned_patients_waitlist", None)
            if isinstance(queue, list):
                queue[:] = [
                    entry
                    for entry in queue
                    if not (
                        isinstance(entry, (list, tuple))
                        and len(entry) >= 2
                        and str(entry[1]).strip() == self.name
                    )
                ]

        # Save info to scratch file
        self.save(f"{sim_folder}/personas/{persona_key}/bootstrap_memory")

        # Persist a final snapshot into the shared data collection (reverie.py owns it).
        if data_collection is not None:
            role_bucket = data_collection.setdefault(self.role, {})
            persona_bucket = role_bucket.get(persona_key)
            if persona_bucket is None:
                persona_bucket = self.data_collection_dict()
            role_bucket[persona_key] = self.save_data(persona_bucket)
