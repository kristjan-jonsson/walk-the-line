"""Shared constants used across all Walk the Line modules."""

SCREEN_W   = 960
SCREEN_H   = 600
FPS        = 60

GRAVITY    = 0.55
JUMP_FORCE = -13.5
MOVE_SPEED = 4.2
RUN_SPEED_MULT = 1.8       # multiplier on MOVE_SPEED when running

# Character collision tuning
COLLISION_MARGIN   = 4     # px margin for terrain-edge collision detection
GROUND_FOLLOW_DOWN = 20    # max px character can be below line and still follow
GROUND_FOLLOW_UP   = 10    # max px character can be above line and still follow
SPRING_FORCE_MULT  = 0.30  # velocity coefficient for spring impact
SPRING_FORCE_BASE  = 0.40  # base force applied to spring on landing

# Character gameplay
INVINCIBLE_FRAMES  = 100   # frames of invincibility after damage (~1.7 s at 60 fps)
STAR_COLLECT_RX    = 24    # star collection horizontal radius (px)
STAR_COLLECT_RY    = 60    # star collection vertical radius (px)
