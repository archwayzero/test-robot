## GameState keys used across modules. Each key is written ONLY by the module named in its namespace;
## anyone may read it. Values must survive var_to_str/str_to_var (they are saved and synced).
## Owner: orchestrator.
class_name StateKeys
extends RefCounted

## Vector3, player's global position. Written by player (throttled: on stance change and at most every 0.5 s).
const PLAYER_POSITION := &"player/position"

## float, player's yaw in radians. Written by player together with PLAYER_POSITION.
const PLAYER_YAW := &"player/yaw"

## int stance: STANCE_STAND / STANCE_CROUCH / STANCE_CRAWL (equal to PlayerController.Stance). Written by player.
const PLAYER_STANCE := &"player/stance"

## Values of PLAYER_STANCE, so modules that do not depend on `player` (e.g. touch_controls) can read it.
const STANCE_STAND := 0
const STANCE_CROUCH := 1
const STANCE_CRAWL := 2

## String, visited cells as a Base64 bitset (row-major, bit (y * width + x)). Written by exploration.
const EXPLORATION_VISITED := &"exploration/visited"

## int, number of visited cells (redundant with the bitset; cheap progress signal). Written by exploration.
const EXPLORATION_COUNT := &"exploration/count"

## int, maze seed the save belongs to. Written by maze when built. A save with another seed is discarded.
const MAZE_SEED := &"maze/seed"

## Game phases (Core.state.set_phase), set by the `game` module.
const PHASE_LOADING := &"loading"
const PHASE_PLAYING := &"playing"
const PHASE_MAP_OPEN := &"map_open"
