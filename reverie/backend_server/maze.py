import json
import numpy
import datetime
import pickle
import time
import math
import heapq
from global_methods import *
from utils import *
import bisect

class Maze: 
  def __init__(self, maze_name, fork_folder, sim_folder,seed): 
    random.seed(seed)
    # READING IN THE BASIC META INFORMATION ABOUT THE MAP
    self.maze_name = maze_name
    # Reading in the meta information about the world. If you want tp see the
    # example variables, check out the maze_meta_info.json file. 
    # meta_info = json.load(open(f"{env_matrix}/maze_meta_info.json"))
    # <maze_width> and <maze_height> denote the number of tiles make up the 
    # height and width of the map. 

    # Grab default maze data
    if(os.path.exists(f"{fork_folder}/reverie/maze_visuals.json")):
      maze_visual_info = json.load(open(f"{fork_folder}/reverie/maze_visuals.json"))
    else:
      maze_visual_info = json.load(open(f"{maze_assets_loc}/the_ed/visuals/{self.maze_name}.json"))

    self.maze_width = int(maze_visual_info["width"])
    self.maze_height = int(maze_visual_info["height"])
    # <sq_tile_size> denotes the pixel height/width of a tile. 
    self.sq_tile_size = int(maze_visual_info["tilewidth"])
    # <special_constraint> is a string description of any relevant special 
    # constraints the world might have. 
    # e.g., "planning to stay at home all day and never go out of her home"
    # self.special_constraint = meta_info["special_constraint"]


    layer_info = maze_visual_info["layers"]
    # READING IN SPECIAL BLOCKS
    # Special blocks are those that are colored in the Tiled map. 

    # Here is an example row for the arena block file: 
    # e.g., "25335, Double Studio, Studio, Common Room"
    # And here is another example row for the game object block file: 
    # e.g, "25331, Double Studio, Studio, Bedroom 2, Painting"

    # Notice that the first element here is the color marker digit from the 
    # Tiled export. Then we basically have the block path: 
    # World, Sector, Arena, Game Object -- again, these paths need to be 
    # unique within an instance of Reverie. 
    blocks_folder = f"{env_matrix}/special_blocks"

    _wb = blocks_folder + "/world_blocks.csv"
    wb_rows = read_file_to_list(_wb, header=False)
    wb = wb_rows[0][-1]
   
    _sb = blocks_folder + "/sector_blocks.csv"
    sb_rows = read_file_to_list(_sb, header=False)
    sb_dict = dict()
    for i in sb_rows: sb_dict[i[0]] = i[-1]
    
    _ab = blocks_folder + "/arena_blocks.csv"
    ab_rows = read_file_to_list(_ab, header=False)
    ab_dict = dict()
    for i in ab_rows: ab_dict[i[0]] = i[-1]
    
    _gob = blocks_folder + "/game_object_blocks.csv"
    gob_rows = read_file_to_list(_gob, header=False)
    gob_dict = dict()
    for i in gob_rows: gob_dict[i[0]] = i[-1]
    
    _slb = blocks_folder + "/spawning_location_blocks.csv"
    slb_rows = read_file_to_list(_slb, header=False)
    slb_dict = dict()
    for i in slb_rows: slb_dict[i[0]] = i[-1]

    # [SECTION 3] Reading in the matrices 
    # This is your typical two dimensional matrices. It's made up of 0s and 
    # the number that represents the color block from the blocks folder. 
    # maze_folder = f"{env_matrix}/maze"

    # _cm = maze_folder + "/collision_maze.csv"
    # self.collision_maze  = read_file_to_list(_cm, header=False)
    # _sm = maze_folder + "/sector_maze.csv"
    # sector_maze = read_file_to_list(_sm, header=False)
    # _am = maze_folder + "/arena_maze.csv"
    # arena_maze = read_file_to_list(_am, header=False)
    # _gom = maze_folder + "/game_object_maze.csv"
    # game_object_maze = read_file_to_list(_gom, header=False)
    # _slm = maze_folder + "/spawning_location_maze.csv"
    # spawning_location_maze = read_file_to_list(_slm, header=False)

    layer_data = {}

    for layer in layer_info:
      layer_data[layer["name"]] = layer

    self.collision_maze  = array_to_2d(layer_data["Collisions"], self.maze_height, self.maze_width)
    sector_maze = array_to_2d(layer_data["Sector Layer"], self.maze_height, self.maze_width)
    arena_maze = array_to_2d(layer_data["Arena Layer"], self.maze_height, self.maze_width)
    game_object_maze = array_to_2d(layer_data["Object Interaction Layer"], self.maze_height, self.maze_width)
    spawning_location_maze = array_to_2d(layer_data["Spawning Blocks"], self.maze_height, self.maze_width)

    # Loading the maze. The mazes are taken directly from the json exports of
    # Tiled maps. They should be in csv format. 
    # Importantly, they are "not" in a 2-d matrix format -- they are single 
    # row matrices with the length of width x height of the maze. So we need
    # to convert here. 
    # We can do this all at once since the dimension of all these matrices are
    # identical (e.g., 70 x 40).
    # example format: [['0', '0', ... '25309', '0',...], ['0',...]...]
    # 25309 is the collision bar number right now.
    # self.collision_maze = []
    # sector_maze = []
    # arena_maze = []
    # game_object_maze = []
    # spawning_location_maze = []
    # for i in range(0, len(collision_maze_raw), meta_info["maze_width"]): 
    #   tw = meta_info["maze_width"]
    #   self.collision_maze += [collision_maze_raw[i:i+tw]]
    #   sector_maze += [sector_maze_raw[i:i+tw]]
    #   arena_maze += [arena_maze_raw[i:i+tw]]
    #   game_object_maze += [game_object_maze_raw[i:i+tw]]
    #   spawning_location_maze += [spawning_location_maze_raw[i:i+tw]]

    # Once we are done loading in the maze, we now set up self.tiles. This is
    # a matrix accessed by row:col where each access point is a dictionary
    # that contains all the things that are taking place in that tile. 
    # More specifically, it contains information about its "world," "sector,"
    # "arena," "game_object," "spawning_location," as well as whether it is a
    # collision block, and a set of all events taking place in it. 
    # e.g., self.tiles[32][59] = {'world': 'double studio', 
    #            'sector': '', 'arena': '', 'game_object': '', 
    #            'spawning_location': '', 'collision': False, 'events': set()}
    # e.g., self.tiles[9][58] = {'world': 'double studio', 
    #         'sector': 'double studio', 'arena': 'bedroom 2', 
    #         'game_object': 'bed', 'spawning_location': 'bedroom-2-a', 
    #         'collision': False,
    #         'events': {('double studio:double studio:bedroom 2:bed',
    #                    None, None)}} 

    self.tiles = []
    for i in range(self.maze_height): 
      row = []
      for j in range(self.maze_width):
        tile_details = dict()
        tile_details["world"] = wb
        
        tile_details["sector"] = ""
        if str(sector_maze[i][j]) in sb_dict: 
          tile_details["sector"] = sb_dict[str(sector_maze[i][j])]

        tile_details["arena"] = ""
        if str(arena_maze[i][j]) in ab_dict: 
          tile_details["arena"] = ab_dict[str(arena_maze[i][j])]
        
        tile_details["game_object"] = ""
        if str(game_object_maze[i][j]) in gob_dict: 
          tile_details["game_object"] = gob_dict[str(game_object_maze[i][j])]
        
        tile_details["spawning_location"] = ""
        if str(spawning_location_maze[i][j]) in slb_dict: 
          tile_details["spawning_location"] = slb_dict[str(spawning_location_maze[i][j])]
        
        tile_details["collision"] = False
        if self.collision_maze[i][j] != 0: 
          tile_details["collision"] = True
        tile_details["events"] = set()
        
        row += [tile_details]
      self.tiles += [row]
    # Each game object occupies an event in the tile. We are setting up the 
    # default event value here. 
    for i in range(self.maze_height):
      for j in range(self.maze_width): 
        if self.tiles[i][j]["game_object"]:
          object_name = ":".join([self.tiles[i][j]["world"], 
                                  self.tiles[i][j]["sector"], 
                                  self.tiles[i][j]["arena"], 
                                  self.tiles[i][j]["game_object"]])
          go_event = (object_name, None, None, None)
          self.tiles[i][j]["events"].add(go_event)



    # Reverse tile access. 
    # <self.address_tiles> -- given a string address, we return a set of all 
    # tile coordinates belonging to that address (this is opposite of  
    # self.tiles that give you the string address given a coordinate). This is
    # an optimization component for finding paths for the personas' movement. 
    # self.address_tiles['<spawn_loc>bedroom-2-a'] == {(58, 9)}
    # self.address_tiles['double studio:recreation:pool table'] 
    #   == {(29, 14), (31, 11), (30, 14), (32, 11), ...}, 
    self.address_tiles = dict()
    for i in range(self.maze_height):
      for j in range(self.maze_width): 
        addresses = []
        if self.tiles[i][j]["sector"]: 
          add = f'{self.tiles[i][j]["world"]}:'
          add += f'{self.tiles[i][j]["sector"]}'
          addresses += [add]
        if self.tiles[i][j]["arena"]: 
          add = f'{self.tiles[i][j]["world"]}:'
          add += f'{self.tiles[i][j]["sector"]}:'
          add += f'{self.tiles[i][j]["arena"]}'
          addresses += [add]
        if self.tiles[i][j]["game_object"]: 
          add = f'{self.tiles[i][j]["world"]}:'
          add += f'{self.tiles[i][j]["sector"]}:'
          add += f'{self.tiles[i][j]["arena"]}:'
          add += f'{self.tiles[i][j]["game_object"]}'
          addresses += [add]
        if self.tiles[i][j]["spawning_location"]: 
          add = f'<spawn_loc>{self.tiles[i][j]["arena"]}'
          addresses += [add]

        for add in addresses: 
          if add in self.address_tiles: 
            self.address_tiles[add].add((j, i))
          else: 
            self.address_tiles[add] = set([(j, i)])


    # Keep track of triage capacity and patients in triage
    # First get all the triage chairs to know triage capacity
    self.triage_capacity = len(self.address_tiles["ed map:emergency department:triage room:chair"])
    
    meta_info = json.load(open(f"{fork_folder}/reverie/maze_status.json"))

    # C:\repo\Capstone-Project-ED-Simulation\environment\frontend_server\static_dirs\assets\the_ed\visuals\emerg_with_collision_and_tilesets.json
    self.triage_patients = meta_info["triage_patients"]

    self.injuries_zones = meta_info["injuries_zones"]
    self.triage_queue = meta_info["triage_queue"]

    # Removing Beds system

    # Set capacity to bed amounts    
    self.injuries_zones["diagnostic room"]["capacity"] = len(self.address_tiles["ed map:emergency department:diagnostic room:diagnostic table"])
    self.injuries_zones["trauma room"]["capacity"] = len(self.address_tiles["ed map:emergency department:trauma room:bed"])

    visual_layer = layer_data["Tile Layer 1"]

    # Turn array into 2D array
    visual_layer_2d = array_to_2d(visual_layer, visual_layer["height"] , visual_layer["width"])

    # Remove beds
    for zone in self.injuries_zones["change_bed_amount"]:
      # Determine how many beds we need to remove
      remove_beds = self.injuries_zones[zone]["remove_beds"]
      self.injuries_zones[zone]["remove_beds"] = 0
      self.injuries_zones[zone]["capacity"]  = len(self.address_tiles[f"ed map:emergency department:{zone}:bed"]) - remove_beds

      #Can't remove negative beds
      if (remove_beds <= 0):
        continue

      for i in range(remove_beds):
        # Grab bed position
        bed_tile = self.address_tiles[f"ed map:emergency department:{zone}:bed"].pop()
        # Remove bed on backend
        self.tiles[bed_tile[1]][bed_tile[0]]["game_object"] = None

        # Remove bed and equipment on the frontend
        self.remove_visual_square(bed_tile, -1, 1, -1, 0, visual_layer_2d)



    # Put 2D array back into a 1D array
    combined_visual_data = []

    for line in visual_layer_2d:
      combined_visual_data += line

    visual_layer["data"] = combined_visual_data

    # Save into sim folder so can use same map over and over
    with open(f"{sim_folder}/reverie/maze_visuals.json", "w") as outfile:  
      outfile.write(json.dumps(maze_visual_info))

    self.patients_waiting_for_doctor = meta_info.get("patients_waiting_for_doctor", [])
    self.doctors_taking_more_patients = meta_info.get("doctors_taking_more_patients", [])
    # Initialize beds
    self._initialize_beds()

  
  def save(self, reverie_maze_f):
    # Ensuring bed states are up to date
    self._sync_all_bed_states()

    maze_meta = dict()
    maze_meta["triage_patients"] = self.triage_patients
    maze_meta["injuries_zones"] = self.injuries_zones
    maze_meta["triage_queue"] = self.triage_queue
    maze_meta["patients_waiting_for_doctor"] = self.patients_waiting_for_doctor
    maze_meta["doctors_taking_more_patients"] = self.doctors_taking_more_patients

    # Atomic write to prevent corruption on crash
    import tempfile, os
    dir_name = os.path.dirname(reverie_maze_f)
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
      with os.fdopen(fd, "w") as f:
        json.dump(maze_meta, f, indent=2)
      os.replace(tmp_path, reverie_maze_f)
    except BaseException:
      try:
        os.unlink(tmp_path)
      except OSError:
        pass
      raise


  # Removes visual items from the visual aspect of the maze starting at the tile
  # 0,0,0,0 removing the only the origin
  def remove_visual_square(self, tile, x_start, x_end, y_start, y_end, visual_layer):
    for x in range(x_start,x_end + 1):
      for y in range(y_start, y_end + 1):
        visual_layer[tile[1] + y][tile[0] + x] = 0

  def turn_coordinate_to_tile(self, px_coordinate): 
    """
    Turns a pixel coordinate to a tile coordinate. 

    INPUT
      px_coordinate: The pixel coordinate of our interest. Comes in the x, y
                     format. 
    OUTPUT
      tile coordinate (x, y): The tile coordinate that corresponds to the 
                              pixel coordinate. 
    EXAMPLE OUTPUT 
      Given (1600, 384), outputs (50, 12)
    """
    x = math.ceil(px_coordinate[0]/self.sq_tile_size)
    y = math.ceil(px_coordinate[1]/self.sq_tile_size)
    return (x, y)


  def access_tile(self, tile): 
    """
    Returns the tiles details dictionary that is stored in self.tiles of the 
    designated x, y location. 

    INPUT
      tile: The tile coordinate of our interest in (x, y) form.
    OUTPUT
      The tile detail dictionary for the designated tile. 
    EXAMPLE OUTPUT
      Given (58, 9), 
      self.tiles[9][58] = {'world': 'double studio', 
            'sector': 'double studio', 'arena': 'bedroom 2', 
            'game_object': 'bed', 'spawning_location': 'bedroom-2-a', 
            'collision': False,
            'events': {('double studio:double studio:bedroom 2:bed',
                       None, None)}} 
    """
    x = tile[0]
    y = tile[1]
    return self.tiles[y][x]


  def get_tile_path(self, tile, level): 
    """
    Get the tile string address given its coordinate. You designate the level
    by giving it a string level description. 

    INPUT: 
      tile: The tile coordinate of our interest in (x, y) form.
      level: world, sector, arena, or game object
    OUTPUT
      The string address for the tile.
    EXAMPLE OUTPUT
      Given tile=(58, 9), and level=arena,
      "double studio:double studio:bedroom 2"
    """
    x = tile[0]
    y = tile[1]
    tile = self.tiles[y][x]

    path = f"{tile['world']}"
    if level == "world": 
      return path
    else: 
      path += f":{tile['sector']}"
    
    if level == "sector": 
      return path
    else: 
      path += f":{tile['arena']}"

    if level == "arena": 
      return path
    else: 
      path += f":{tile['game_object']}"

    return path


  def get_nearby_tiles(self, tile, vision_r): 
    """
    Given the current tile and vision_r, return a list of tiles that are 
    within the radius. Note that this implementation looks at a square 
    boundary when determining what is within the radius. 
    i.e., for vision_r, returns x's. 
    x x x x x 
    x x x x x
    x x P x x 
    x x x x x
    x x x x x

    INPUT: 
      tile: The tile coordinate of our interest in (x, y) form.
      vision_r: The radius of the persona's vision. 
    OUTPUT: 
      nearby_tiles: a list of tiles that are within the radius. 
    """
    left_end = 0
    if tile[0] - vision_r > left_end: 
      left_end = tile[0] - vision_r

    right_end = self.maze_width - 1
    if tile[0] + vision_r + 1 < right_end: 
      right_end = tile[0] + vision_r + 1

    bottom_end = self.maze_height - 1
    if tile[1] + vision_r + 1 < bottom_end: 
      bottom_end = tile[1] + vision_r + 1

    top_end = 0
    if tile[1] - vision_r > top_end: 
      top_end = tile[1] - vision_r 

    nearby_tiles = []
    for i in range(left_end, right_end): 
      for j in range(top_end, bottom_end): 
        nearby_tiles += [(i, j)]
    return nearby_tiles


  def add_event_from_tile(self, curr_event, tile): 
    """
    Add an event triple to a tile.  

    INPUT: 
      curr_event: Current event triple. 
        e.g., ('double studio:double studio:bedroom 2:bed', None,
                None)
      tile: The tile coordinate of our interest in (x, y) form.
    OUPUT: 
      None
    """
    print(tile)
    self.tiles[tile[1]][tile[0]]["events"].add(curr_event)


  def remove_event_from_tile(self, curr_event, tile):
    """
    Remove an event triple from a tile.  

    INPUT: 
      curr_event: Current event triple. 
        e.g., ('double studio:double studio:bedroom 2:bed', None,
                None)
      tile: The tile coordinate of our interest in (x, y) form.
    OUPUT: 
      None
    """
    curr_tile_ev_cp = self.tiles[tile[1]][tile[0]]["events"].copy()
    for event in curr_tile_ev_cp: 
      if event == curr_event:  
        self.tiles[tile[1]][tile[0]]["events"].remove(event)


  def turn_event_from_tile_idle(self, curr_event, tile):
    curr_tile_ev_cp = self.tiles[tile[1]][tile[0]]["events"].copy()
    for event in curr_tile_ev_cp: 
      if event == curr_event:  
        self.tiles[tile[1]][tile[0]]["events"].remove(event)
        new_event = (event[0], None, None, None)
        self.tiles[tile[1]][tile[0]]["events"].add(new_event)


  def remove_subject_events_from_tile(self, subject, tile):
    """
    Remove an event triple that has the input subject from a tile. 

    INPUT: 
      subject: "Isabella Rodriguez"
      tile: The tile coordinate of our interest in (x, y) form.
    OUPUT: 
      None
    """
    curr_tile_ev_cp = self.tiles[tile[1]][tile[0]]["events"].copy()
    for event in curr_tile_ev_cp: 
      if event[0] == subject:  
        self.tiles[tile[1]][tile[0]]["events"].remove(event)


  def _initialize_beds(self):
    """
    Build internal tracking for bed availability and assignments.
    """
    self.bed_address_lookup = {}
    self.bed_assignments = {}
    self.available_beds = {}

    for zone, zone_info in self.injuries_zones.items():
      if not isinstance(zone_info, dict):
        continue
      bed_key = f"ed map:emergency department:{zone}:bed"
      if bed_key not in self.address_tiles:
        continue

      beds = set(self.address_tiles[bed_key])
      assigned_raw = zone_info.get("bed_assignments", {})
      assigned = {}
      for patient, coord in assigned_raw.items():
        coord_tuple = tuple(coord) if isinstance(coord, list) else tuple(coord)
        if coord_tuple in beds:
          assigned[patient] = coord_tuple

      available_raw = zone_info.get("available_beds", [])
      available = set()
      for coord in available_raw or []:
        coord_tuple = tuple(coord) if isinstance(coord, list) else tuple(coord)
        if coord_tuple in beds and coord_tuple not in assigned.values():
          available.add(coord_tuple)

      for bed in beds:
        self._ensure_bed_address(zone, bed)
        if bed not in assigned.values():
          available.add(bed)

      self.bed_assignments[zone] = assigned
      self.available_beds[zone] = available

    self._sync_all_bed_states()

    # Assign beds to any patients that were already marked as present
    for zone, zone_info in self.injuries_zones.items():
      if not isinstance(zone_info, dict):
        continue
      if zone not in self.bed_assignments:
        continue
      for patient_name in zone_info.get("current_patients", []):
        if patient_name not in self.bed_assignments[zone]:
          self.assign_bed(patient_name, zone)

  def _ensure_bed_address(self, zone, bed):
    """
    Register a unique address for a specific bed tile so patients can target a single bed.
    """
    bed = tuple(bed)
    if zone not in self.bed_address_lookup:
      self.bed_address_lookup[zone] = dict()

    if bed not in self.bed_address_lookup[zone]:
      bed_addr = f"ed map:emergency department:{zone}:bed:{bed[0]}:{bed[1]}"
      self.bed_address_lookup[zone][bed] = bed_addr
      self.address_tiles[bed_addr] = set([bed])
    return (bed[0], bed[1])
  
  def get_bed_address(self, zone, bed):
    if zone not in self.available_beds:
      return None
    return self._ensure_bed_address(zone, bed)

  def assign_bed(self, patient_name, zone, preferred=None):
    if zone not in self.available_beds:
      return None

    if patient_name in self.bed_assignments.get(zone, {}):
      return self.bed_assignments[zone][patient_name]

    preferred_tuple = tuple(preferred) if preferred is not None else None
    bed = None
    if preferred_tuple and preferred_tuple in self.available_beds[zone]:
      bed = preferred_tuple
      self.available_beds[zone].discard(bed)
    elif self.available_beds[zone]:
      bed = self.available_beds[zone].pop()

    if not bed:
      return None

    self.bed_assignments[zone][patient_name] = bed
    self._sync_bed_state(zone)
    return bed

  def release_bed(self, patient_name, zone=None):
    zone = zone or self._find_patient_zone(patient_name)
    if not zone or zone not in self.bed_assignments:
      return

    bed = self.bed_assignments[zone].pop(patient_name, None)
    if bed:
      self.available_beds[zone].add(bed)
    self._sync_bed_state(zone)

  def discharge_patient(self, patient_name, zone=None):
    zone = zone or self._find_patient_zone(patient_name)
    if not zone:
      return
    zone_info = self.injuries_zones.get(zone, {})
    if isinstance(zone_info, dict):
      current_patients = zone_info.get("current_patients", [])
      if patient_name in current_patients:
        current_patients.remove(patient_name)
    self.release_bed(patient_name, zone)

  def _find_patient_zone(self, patient_name):
    for zone, assignments in self.bed_assignments.items():
      if patient_name in assignments:
        return zone
    return None

  def _sync_bed_state(self, zone):
    zone_info = self.injuries_zones.get(zone, {})
    if not isinstance(zone_info, dict):
      zone_info = {}
      self.injuries_zones[zone] = zone_info
    zone_info["bed_assignments"] = {patient: list(coord) for patient, coord in self.bed_assignments.get(zone, {}).items()}
    zone_info["available_beds"] = [list(coord) for coord in sorted(self.available_beds.get(zone, []))]

  def _sync_all_bed_states(self):
    for zone in self.bed_assignments.keys():
      self._sync_bed_state(zone)
























