"""
Tests for LevelGenerator.

Smoke-tests that generation produces valid terrain and that the public API
(update, prune, enemy spawns) behaves correctly.  These replace the old
test_levels.py script.
"""

import pytest
from level import LevelGenerator


# ── Basic generation ──────────────────────────────────────────────────────────

def test_default_generator_produces_segments():
    gen = LevelGenerator()
    gen.update(500)
    assert len(gen.segments) > 0

def test_segments_cover_player_position():
    gen = LevelGenerator()
    gen.update(500)
    # At least one segment should contain or be ahead of x=0
    assert any(s.x2 > 0 for s in gen.segments)

def test_default_generator_produces_stars():
    gen = LevelGenerator()
    gen.update(1000)
    assert len(gen.stars) > 0

def test_segments_are_contiguous_at_start():
    """Gaps between segment endpoints should be small (gap chunks aside)."""
    gen = LevelGenerator()
    gen.update(2000)
    segs = sorted(gen.segments, key=lambda s: s.x1)
    for a, b in zip(segs, segs[1:]):
        # Adjacent segments should be no more than gap_max apart
        gap = b.x1 - a.x2
        assert gap <= gen._cfg["gap_max"] + 1  # +1 for float rounding


# ── Level files ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "levels/default.json",
    "levels/easy.json",
    "levels/hard.json",
])
def test_level_file_generates_segments(path):
    gen = LevelGenerator.from_file(path)
    gen.update(500)
    assert len(gen.segments) > 0

def test_level_file_generates_stars(tmp_path):
    gen = LevelGenerator.from_file("levels/default.json")
    gen.update(1000)
    assert len(gen.stars) > 0


# ── Seamless mid-run start ────────────────────────────────────────────────────

def test_from_file_mid_run_start():
    gen = LevelGenerator.from_file("levels/hard.json", start_x=3000.0, start_y=350.0)
    gen.update(3100)
    assert len(gen.segments) > 0
    # Segments should begin near the start position, not at 0
    assert gen.segments[0].x1 >= 2000


# ── update / prune ────────────────────────────────────────────────────────────

def test_update_extends_ahead_of_player():
    gen = LevelGenerator()
    gen.update(0)
    gen.update(1000)
    assert any(s.x2 > 1000 for s in gen.segments)

def test_prune_removes_far_behind_segments():
    gen = LevelGenerator()
    gen.update(0)
    gen.update(5000)   # advance far enough that early segments are pruned
    # No segment should end more than PRUNE_BEHIND behind the player
    for s in gen.segments:
        assert s.x2 > 5000 - gen.PRUNE_BEHIND


# ── Enemy spawns ──────────────────────────────────────────────────────────────

def test_take_enemy_spawns_clears_list():
    gen = LevelGenerator()
    gen.update(5000)
    spawns = gen.take_enemy_spawns()
    assert isinstance(spawns, list)
    assert gen.enemy_spawns == []

def test_enemy_spawns_have_valid_coordinates():
    gen = LevelGenerator()
    gen.update(5000)
    spawns = gen.take_enemy_spawns()
    for x, y in spawns:
        assert x > 0
        assert 0 < y < 700   # within plausible screen range


# ── Flip triggers ─────────────────────────────────────────────────────────────

def test_flip_triggers_generated_eventually():
    gen = LevelGenerator()
    gen.update(10000)
    assert len(gen.flip_triggers) > 0

def test_flip_triggers_are_after_first_flip_x():
    gen = LevelGenerator()
    gen.update(10000)
    first_flip_x = gen._cfg["first_flip_x"]
    for tx in gen.flip_triggers:
        assert tx >= first_flip_x
