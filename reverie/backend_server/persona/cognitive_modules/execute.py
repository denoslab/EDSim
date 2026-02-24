import sys
import random
sys.path.append('../../')

from global_methods import *
from path_finder import *
from utils import *

def execute(persona, maze, personas, plan): 
  """
  Given a plan (action's string address), we execute the plan (actually 
  outputs the tile coordinate path and the next coordinate for the 
  persona). 

  INPUT:
    persona: Current <Persona> instance.  
    maze: An instance of current <Maze>.
    personas: A dictionary of all personas in the world. 
    plan: This is a string address of the action we need to execute. 
       It comes in the form of "{world}:{sector}:{arena}:{game_objects}". 
       It is important that you access this without doing negative 
       indexing (e.g., [-1]) because the latter address elements may not be 
       present in some cases. 
       e.g., "dolores double studio:double studio:bedroom 1:bed"
    
  OUTPUT: 
    execution
  """
  print(persona.name + " " + maze.tiles[persona.scratch.curr_tile[1]][persona.scratch.curr_tile[0]]['arena'] + " | EXECUTING PLAN: " + plan)
  if persona.scratch.planned_path != []:
    pass
  elif "<random>" in plan: 
    persona.scratch.act_path_set = False
  elif("tile" in plan):
    cords = plan.split("<tile>")[-1].replace('(', "").replace(')', "")
    x = int(cords.split(", ")[0].strip())
    y = int(cords.split(", ")[1].strip())
    if(persona.scratch.curr_tile[0] == x and persona.scratch.curr_tile[1] == y):
      plan = f"<waiting> {x} {y}"
      persona.scratch.act_path_set = True

    else:
      persona.scratch.act_path_set = False
      print("RESETTING PATH | " + persona.name + str([x,y])) 

  elif(( "waiting" not in plan) and (persona.scratch.chatting_with == None)):
    if(maze.tiles[persona.scratch.curr_tile[1]][persona.scratch.curr_tile[0]]['arena'] not in persona.scratch.act_address):

        persona.scratch.act_path_set = False
        print("RESETTING PATH | " + persona.name + " " + maze.tiles[persona.scratch.curr_tile[1]][persona.scratch.curr_tile[0]]['arena'])

  plan = plan.replace("operating", "diagnostic")
  # <act_path_set> is set to True if the path is set for the current action. 
  # It is False otherwise, and means we need to construct a new path. 
  if not persona.scratch.act_path_set: 
    # <target_tiles> is a list of tile coordinates where the persona may go 
    # to execute the current action. The goal is to pick one of them.
    target_tiles = None

    if "<persona>" in plan: 
      # Executing persona-persona interaction.
      persona_segment = plan.split("<persona>")[-1]
      persona_name = persona_segment.splitlines()[0].strip()
      persona_name = persona_name.split(":")[0].strip()
      persona_name = persona_name.strip("\"'`")
      if persona_name not in personas:
        persona_name = persona_name.rstrip(".,;")
      if persona_name not in personas:
        persona.scratch.next_step = None
        return persona.scratch.curr_tile, persona.scratch.act_pronunciatio, f"{persona_name} is no longer in the simulation."

      # Waits to interact with persona if they are current_state busy.
      if(personas[persona_name].scratch.chatting_with != None):

        return persona.scratch.curr_tile, persona.scratch.act_pronunciatio, f"Waiting to interact with {persona_name}."

      target_p_tile = (personas[persona_name]
                       .scratch.curr_tile)
      potential_path = path_finder(maze.collision_maze,
                                   persona.scratch.curr_tile,
                                   target_p_tile,
                                   collision_block_id)
      if len(potential_path) <= 2:
        target_tiles = [potential_path[-1]]
      else:
        potential_1 = path_finder(maze.collision_maze,
                                persona.scratch.curr_tile,
                                potential_path[int(len(potential_path)/2)],
                                collision_block_id)
        potential_2 = path_finder(maze.collision_maze,
                                persona.scratch.curr_tile,
                                potential_path[int(len(potential_path)/2)+1],
                                collision_block_id)
        if len(potential_1) <= len(potential_2):
          target_tiles = [potential_path[int(len(potential_path)/2)]]
        else:
          target_tiles = [potential_path[int(len(potential_path)/2+1)]]
    
    elif "<waiting>" in plan: 
      # Executing interaction where the persona has decided to wait before 
      # executing their action.
      persona.scratch.act_pronunciatio = "⏳"
      x = int(plan.split()[1])
      y = int(plan.split()[2])
      target_tiles = [[x, y]]

    elif "<random>" in plan: 
      # Executing a random location action.
      plan = ":".join(plan.split(":")[:-1])
      target_tiles = maze.address_tiles[plan]
      target_tiles = random.sample(list(target_tiles), 1)
    
    elif "<tile>" in plan:
      # Executing a specific tile action.
      tile_segment = plan.split("<tile>")[-1].replace('(', "").replace(')', "")
      x = int(tile_segment.split(",")[0].strip())
      y = int(tile_segment.split(",")[1].strip())
      target_tiles = [[x, y]]

    else: 
      # This is our default execution. We simply take the persona to the
      # location where the current action is taking place. 
      # Retrieve the target addresses. Again, plan is an action address in its
      # string form. <maze.address_tiles> takes this and returns candidate 
      # coordinates. 
      if plan not in maze.address_tiles:
        # Unknown address — stay at current tile instead of crashing
        print(f"(execute) WARNING: Unknown address '{plan}' for {persona.name}, staying put.")
        target_tiles = [persona.scratch.curr_tile]
      else:
        target_tiles = maze.address_tiles[plan]

    # There are sometimes more than one tile returned from this (e.g., a tabe
    # may stretch many coordinates). So, we sample a few here. And from that 
    # random sample, we will take the closest ones. 
    if len(target_tiles) < 4: 
      target_tiles = random.sample(list(target_tiles), len(target_tiles))
    else:
      target_tiles = random.sample(list(target_tiles), 2)
    # If possible, we want personas to occupy different tiles when they are 
    # headed to the same location on the maze. It is ok if they end up on the 
    # same time, but we try to lower that probability. 
    # We take care of that overlap here.  
    persona_name_set = set(personas.keys())
    new_target_tiles = []
    for i in target_tiles: 
      curr_event_set = maze.access_tile(i)["events"]
      pass_curr_tile = False
      for j in curr_event_set: 
        if j[0] in persona_name_set: 
          pass_curr_tile = True
      if not pass_curr_tile: 
        new_target_tiles += [i]
    if len(new_target_tiles) == 0: 
      new_target_tiles = target_tiles
    target_tiles = new_target_tiles

    # Now that we've identified the target tile, we find the shortest path to
    # one of the target tiles. 
    curr_tile = persona.scratch.curr_tile
    collision_maze = maze.collision_maze
    closest_target_tile = None
    path = None
    for i in target_tiles: 
      # path_finder takes a collision_mze and the curr_tile coordinate as 
      # an input, and returns a list of coordinate tuples that becomes the
      # path. 
      # e.g., [(0, 1), (1, 1), (1, 2), (1, 3), (1, 4)...]
      curr_path = path_finder(maze.collision_maze, 
                              curr_tile, 
                              i, 
                              collision_block_id)

      if not closest_target_tile: 
        closest_target_tile = i
        path = curr_path
      elif len(curr_path) < len(path): 
        closest_target_tile = i
        path = curr_path

    shorten_path_length = path[::1]
    if path[-1] not in shorten_path_length:
      shorten_path_length.append(path[-1])

    path = shorten_path_length

    # Actually setting the <planned_path> and <act_path_set>. We cut the 
    # first element in the planned_path because it includes the curr_tile. 
    persona.scratch.planned_path = path[1:]
    persona.scratch.act_path_set = True
  
  # Setting up the next immediate step. We stay at our curr_tile if there is
  # no <planned_path> left, but otherwise, we go to the next tile in the path.
  ret = persona.scratch.curr_tile
  if persona.scratch.planned_path:
    tiles_to_move = min(getattr(maze, 'tiles_per_step', 1),
                        len(persona.scratch.planned_path))
    ret = persona.scratch.planned_path[tiles_to_move - 1]
    persona.scratch.planned_path = persona.scratch.planned_path[tiles_to_move:]

  description = f"{persona.scratch.act_description}"
  description += f" @ {persona.scratch.act_address}"

  execution = ret, persona.scratch.act_pronunciatio, description
  return execution















