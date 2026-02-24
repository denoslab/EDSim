from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / 'environment' / 'frontend_server'
MAZE_ASSETS_ROOT = FRONTEND_ROOT / 'static_dirs' / 'assets'

maze_assets_loc = str(MAZE_ASSETS_ROOT)
env_matrix = str(MAZE_ASSETS_ROOT / 'the_ed' / 'matrix')
env_visuals = str(MAZE_ASSETS_ROOT / 'the_ed' / 'visuals')

fs_storage = str(FRONTEND_ROOT / 'storage')
fs_temp_storage = str(FRONTEND_ROOT / 'temp_storage')

collision_block_id = "1233"

static_sim_code = ""

# Verbose
debug = True
