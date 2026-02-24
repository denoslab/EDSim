import math
import sys
import datetime
import random
import re
import copy
sys.path.append('../')

from global_methods import *

from persona.memory_structures.spatial_memory import *
from persona.memory_structures.associative_memory import *
from persona.memory_structures.scratch import *

from persona.cognitive_modules.perceive import *
from persona.cognitive_modules.retrieve import *
from persona.cognitive_modules.plan import *
from persona.cognitive_modules.reflect import *
from persona.cognitive_modules.execute import *
# from persona.cognitive_modules.converse import *

REQUIRED_FIELDS = {
    "vision_r": 8,
    "att_bandwidth": 8,
    "retention": 8,
    "curr_time": None,
    "curr_tile": None,
    "schedule_constraints": "",
    "name": "",
    "first_name": "",
    "last_name": "",
    "age": 0,
    "behavior_modifiers": "",
    "role_description": "",
    "current_state": "",
    "work_pattern": "",
    "living_area": "",
    "concept_forget": 100,
    "daily_reflection_time": 180,
    "daily_reflection_size": 5,
    "overlap_reflect_th": 2,
    "kw_strg_event_reflect_th": 4,
    "kw_strg_thought_reflect_th": 4,
    "recency_w": 1,
    "relevance_w": 1,
    "importance_w": 1,
    "recency_decay": 0.99,
    "importance_trigger_max": 150,
    "importance_trigger_curr": 150,
    "importance_ele_n": 0,
    "thought_count": 5,
    "daily_req": [],
    "f_daily_schedule": [],
    "f_daily_schedule_hourly_org": [],
    "act_address": None,
    "act_start_time": None,
    "act_duration": None,
    "act_description": None,
    "act_pronunciatio": None,
    "act_event": ["", None, None],
    "act_obj_description": None,
    "act_obj_pronunciatio": None,
    "act_obj_event": [None, None, None],
    "chatting_with": None,
    "chat": None,
    "chatting_with_buffer": {},
    "chatting_end_time": None,
    "act_path_set": False,
    "planned_path": [],
    "next_step": None,
    "ICD": None,
    "CTAS": None,
    "next_room": None,
    "state": None,
    "time_to_next": None,
    "injuries_zone": None,
    "exempt_from_data_collection": False,
}

def normalize_patient_scratch(raw):
    # legacy key fixes
    if "act_pronunciation" in raw and "act_pronunciatio" not in raw:
        raw["act_pronunciatio"] = raw.pop("act_pronunciation")

    normalized = {}
    for key, default in REQUIRED_FIELDS.items():
        normalized[key] = raw.get(key, default)

    # carry over anything extra the template might add
    for key, value in raw.items():
        if key not in normalized:
            normalized[key] = value
    return normalized

class Persona:

  # Class-level cache for role templates (LLM-once pattern)
  _role_scratch_cache = {}

  def __init__(self, name, folder_mem_saved=False, role=None, seed=0):
    # PERSONA BASE STATE 
    # <name> is the full name of the persona. This is a unique identifier for
    # the persona within Reverie. 
    self.name = name
    print(self.name, flush=True)
    # PERSONA MEMORY 
    # If there is already memory in folder_mem_saved, we load that. Otherwise,
    # we create new memory instances. 
    # <s_mem> is the persona's spatial memory. 
    f_s_mem_saved = f"{folder_mem_saved}/bootstrap_memory/spatial_memory.json"
    self.s_mem = MemoryTree(f_s_mem_saved)
    # <s_mem> is the persona's associative memory. 
    f_a_mem_saved = f"{folder_mem_saved}/bootstrap_memory/associative_memory"
    self.a_mem = AssociativeMemory(f_a_mem_saved)

    number = int(name.split(' ')[-1]) if name.split(' ')[-1].isnumeric() else 0
    random.seed(seed + number)

    #Find role for persona using their what was in the meta.json file
    self.role = role
    

  def save(self, save_folder): 
    """
    Save persona's current state (i.e., memory). 

    INPUT: 
      save_folder: The folder where we wil be saving our persona's state. 
    OUTPUT: 
      None
    """
    # Spatial memory contains a tree in a json format. 
    # e.g., {"double studio": 
    #         {"double studio": 
    #           {"bedroom 2": 
    #             ["painting", "easel", "closet", "bed"]}}}
    f_s_mem = f"{save_folder}/spatial_memory.json"
    self.s_mem.save(f_s_mem)
    
    # Associative memory contains a csv with the following rows: 
    # [event.type, event.created, event.expiration, s, p, o]
    # e.g., event,2022-10-23 00:00:00,,Isabella Rodriguez,is,idle
    f_a_mem = f"{save_folder}/associative_memory"
    self.a_mem.save(f_a_mem)

    # Scratch contains non-permanent data associated with the persona. When 
    # it is saved, it takes a json form. When we load it, we move the values
    # to Python variables. 
    f_scratch = f"{save_folder}/scratch.json"
    self.scratch.save(f_scratch)


  def perceive(self, maze):
    """
    This function takes the current maze, and returns events that are 
    happening around the persona. Importantly, perceive is guided by 
    two key hyper-parameter for the  persona: 1) att_bandwidth, and 
    2) retention. 

    First, <att_bandwidth> determines the number of nearby events that the 
    persona can perceive. Say there are 10 events that are within the vision
    radius for the persona -- perceiving all 10 might be too much. So, the 
    persona perceives the closest att_bandwidth number of events in case there
    are too many events. 

    Second, the persona does not want to perceive and think about the same 
    event at each time step. That's where <retention> comes in -- there is 
    temporal order to what the persona remembers. So if the persona's memory
    contains the current surrounding events that happened within the most 
    recent retention, there is no need to perceive that again. xx

    INPUT: 
      maze: Current <Maze> instance of the world. 
    OUTPUT: 
      a list of <ConceptNode> that are perceived and new. 
        See associative_memory.py -- but to get you a sense of what it 
        receives as its input: "s, p, o, desc, persona.scratch.curr_time"
    """
    return perceive(self, maze)


  def retrieve(self, perceived):
    """
    This function takes the events that are perceived by the persona as input
    and returns a set of related events and thoughts that the persona would 
    need to consider as context when planning. 

    INPUT: 
      perceive: a list of <ConceptNode> that are perceived and new.  
    OUTPUT: 
      retrieved: dictionary of dictionary. The first layer specifies an event,
                 while the latter layer specifies the "curr_event", "events", 
                 and "thoughts" that are relevant.
    """
    return retrieve(self, perceived)


  def plan(self, maze, personas, new_day, retrieved):
    """
    Main cognitive function of the chain. It takes the retrieved memory and 
    perception, as well as the maze and the first day state to conduct both 
    the long term and short term planning for the persona. 

    INPUT: 
      maze: Current <Maze> instance of the world. 
      personas: A dictionary that contains all persona names as keys, and the 
                Persona instance as values. 
      new_day: This can take one of the three values. 
        1) <Boolean> False -- It is not a "new day" cycle (if it is, we would
           need to call the long term planning sequence for the persona). 
        2) <String> "First day" -- It is literally the start of a simulation,
           so not only is it a new day, but also it is the first day. 
        2) <String> "New day" -- It is a new day. 
      retrieved: dictionary of dictionary. The first layer specifies an event,
                 while the latter layer specifies the "curr_event", "events", 
                 and "thoughts" that are relevant.
    OUTPUT 
      The target action address of the persona (persona.scratch.act_address).
    """
    return plan(self, maze, personas, new_day, retrieved)


  def execute(self, maze, personas, plan):
    """
    This function takes the agent's current plan and outputs a concrete 
    execution (what object to use, and what tile to travel to). 

    INPUT: 
      maze: Current <Maze> instance of the world. 
      personas: A dictionary that contains all persona names as keys, and the 
                Persona instance as values. 
      plan: The target action address of the persona  
            (persona.scratch.act_address).
    OUTPUT: 
      execution: A triple set that contains the following components: 
        <next_tile> is a x,y coordinate. e.g., (58, 9)
        <pronunciatio> is an emoji.
        <description> is a string description of the movement. e.g., 
        writing her next novel (editing her novel) 
        @ double studio:double studio:common room:sofa
    """
    return execute(self, maze, personas, plan)


  def reflect(self):
    """
    Reviews the persona's memory and create new thoughts based on it. 

    INPUT: 
      None
    OUTPUT: 
      None
    """
    reflect(self)


  def move(self, maze, personas, curr_tile, curr_time, data_collection = None):
    """
    This is the main cognitive function where our main sequence is called.

    INPUT:
      maze: The Maze class of the current world.
      personas: A dictionary that contains all persona names as keys, and the
                Persona instance as values.
      curr_tile: A tuple that designates the persona's current tile location
                 in (row, col) form. e.g., (58, 39)
      curr_time: datetime instance that indicates the game's current time.
    OUTPUT:
      execution: A triple set that contains the following components:
        <next_tile> is a x,y coordinate. e.g., (58, 9)
        <pronunciatio> is an emoji.
        <description> is a string description of the movement. e.g.,
        writing her next novel (editing her novel)
        @ double studio:double studio:common room:sofa
    """
    # Updating persona's scratch memory with <curr_tile>.
    self.scratch.curr_tile = curr_tile
    # Cache tiles_per_step on scratch so subclasses can use it in
    # _should_skip_cognition() (which doesn't receive maze).
    self.scratch._tiles_per_step = getattr(maze, 'tiles_per_step', 1)
    print("curr_tile",curr_tile)

    # We figure out whether the persona started a new day, and if it is a new
    # day, whether it is the very first day of the simulation. This is
    # important because we set up the persona's long term plan at the start of
    # a new day.


    self.scratch.act_address = f"<waiting> {curr_tile[0]} {curr_tile[1]}"
    new_day = False
    if not self.scratch.curr_time:
      new_day = "First day"
    elif (self.scratch.curr_time.strftime('%A %B %d')
          != curr_time.strftime('%A %B %d')):
      new_day = "New day"
    self.scratch.curr_time = curr_time

    # Skip expensive LLM-based cognition when the persona doesn't need it
    # (e.g., mid-walk, resting, already chatting). Subclasses override
    # _should_skip_cognition() to define their own skip conditions.
    if self._should_skip_cognition():
      self._tick_chat_cleanup()
      return self.scratch.act_address

    # Main cognitive sequence begins here.
    perceived = self.perceive(maze)
    retrieved = self.retrieve(perceived)

    plan = self.plan(maze, personas, new_day, retrieved)
    # self.reflect()

    # <execution> is a triple set that contains the following components:
    # <next_tile> is a x,y coordinate. e.g., (58, 9)
    # <pronunciatio> is an emoji. e.g., "\ud83d\udca4"
    # <description> is a string description of the movement. e.g.,
    #   writing her next novel (editing her novel)
    #   @ double studio:double studio:common room:sofa

    return plan


  def _should_skip_cognition(self):
    """Return True to skip perceive/retrieve/plan this tick.
    Base default is False; subclasses override with role-specific logic."""
    return False


  def _tick_chat_cleanup(self):
    """Duplicate of the chat-state cleanup from plan.py (lines 1023-1039).
    Must run every tick even when we skip the full plan() call, so that
    chatting_with gets cleared when the timer expires and the buffer
    decrements properly."""
    # Expire finished conversations
    if self.scratch.chatting_end_time:
      if self.scratch.chatting_end_time <= self.scratch.curr_time:
        self.scratch.chatting_with = None
        self.scratch.chat = None
        self.scratch.chatting_end_time = None
        self.scratch.act_path_set = False

    # chatting_with_buffer removed — ED staff decide_to_chat() never
    # returns None, so the buffer gate was dead code.

  def open_convo_session(self, convo_mode, safe_mode=True, direct=False, question=None): 
    if direct:
      return open_convo_session(self, convo_mode, safe_mode, direct, question)
    else: 
      return open_convo_session(self, convo_mode, safe_mode, direct)
  
  # Define what behaviour a persona should have after a chat
  def react_to_chat(self, convo_summary, other_persona, maze):
    pass

  # Define whether if a persona should talk to target persona
  def decide_to_chat(self, target_persona):
    pass
  
  # Set up data_collection for persona
  # Empty dict is the default
  def data_collection_dict(self):
    return {}
  
  # Saves data into data collection
  def save_data(self, data):
    return data
  
  # Define where a persona should spawn
  def get_spawn_loc(self, maze):
    None

  # Method to create a new persona using a API call and creating a new object
  @staticmethod
  def create_persona(PersonaClass, persona_role, role_num, desc, curr_time, sim_folder, maze,  persona_loc = None, seed=0):
    # Convert CamelCase to spaced name: "BedsideNurse" -> "Bedside Nurse"
    display_name = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', persona_role)
    full_name = f"{display_name} {role_num}"

    if persona_role in Persona._role_scratch_cache:
        # Copy from cached template
        new_scratch = copy.deepcopy(Persona._role_scratch_cache[persona_role])
        new_scratch["name"] = full_name
        new_scratch["first_name"] = display_name
        new_scratch["last_name"] = str(role_num)
        new_scratch["act_event"] = [full_name, None, None]
    else:
        # First of this role — generate via GPT
        new_scratch = run_gpt_generate_patient_scratch(persona_role, f"Name: ({full_name}) | Description: {desc}")
        new_scratch = normalize_patient_scratch(new_scratch)
        # Force correct name regardless of what GPT returned
        new_scratch["name"] = full_name
        new_scratch["first_name"] = display_name
        new_scratch["last_name"] = str(role_num)
        new_scratch["act_event"] = [full_name, None, None]
        # Cache for future copies
        Persona._role_scratch_cache[persona_role] = copy.deepcopy(new_scratch)

    new_scratch.setdefault("injuries_zone", None)
    # Always default to non-exempt; callers (e.g. add_patient_in_bed) override after creation.
    new_scratch["exempt_from_data_collection"] = False
    print(new_scratch)
    # Update the current time
    new_scratch["curr_time"] =  curr_time.strftime("%B %d, %Y, %H:%M:%S")
    # Get folder locations
    persona_folder = f"{sim_folder}/personas/{new_scratch['name']}"

    if "act_pronunciation" in new_scratch and "act_pronunciatio" not in new_scratch:
        new_scratch["act_pronunciatio"] = new_scratch.pop("act_pronunciation")

    # Copy from the patient template folder into persona folder to keep structure
    copyanything(f"folder_templates/{persona_role.lower()}_template", persona_folder + "/bootstrap_memory")

    with open(f"{persona_folder}/bootstrap_memory/scratch.json", "w") as outfile:
      outfile.write(json.dumps(new_scratch, indent=2, default=str))

    # Create a persona object and get them to move to the waiting room
    curr_persona = PersonaClass(new_scratch["name"], persona_folder, role=persona_role, seed=seed)

    # If we didn't designate a position in the arguments to spawn grab the ones from the scratch
    if(not persona_loc):
      spawn_loc = curr_persona.get_spawn_loc(maze)
      p_x = spawn_loc[0]
      p_y = spawn_loc[1] - 1
    else:
      p_x = persona_loc[0]
      p_y = persona_loc[1]


    curr_persona.scratch.curr_tile = [p_x, p_y]

    return curr_persona, [p_x, p_y]

































