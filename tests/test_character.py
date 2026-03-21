"""
Tests for Character logic.

Covers physics-independent game rules (damage, gravity flip, star collection)
and terrain collision using a real SpringLine.  No pygame display is needed —
pygame constants (K_RIGHT etc.) are plain integers available after import.
"""

import collections
import pytest
import pygame
from character import Character
from spring_line import SpringLine
from constants import INVINCIBLE_FRAMES, STAR_COLLECT_RX, STAR_COLLECT_RY


def _no_keys():
    """Return a key-state mapping with all keys released."""
    return collections.defaultdict(bool)


def _keys(**pressed):
    """Return a key-state mapping with the given pygame key constants held."""
    d = collections.defaultdict(bool)
    d.update(pressed)
    return d


# ── Initial state ─────────────────────────────────────────────────────────────

def test_initial_lives():
    c = Character(0, 300)
    assert c.lives == 3

def test_initial_alive():
    c = Character(0, 300)
    assert c.alive is True

def test_initial_gravity_not_flipped():
    c = Character(0, 300)
    assert c.gravity_flipped is False

def test_initial_events_empty():
    c = Character(0, 300)
    assert len(c.events) == 0


# ── take_damage ───────────────────────────────────────────────────────────────

def test_take_damage_reduces_lives():
    c = Character(0, 300)
    c.take_damage()
    assert c.lives == 2

def test_take_damage_emits_hit_event():
    c = Character(0, 300)
    c.take_damage()
    assert 'hit' in c.events

def test_take_damage_at_one_life_kills():
    c = Character(0, 300)
    c.lives = 1
    c.take_damage()
    assert c.alive is False
    assert 'die' in c.events

def test_take_damage_dead_character_emits_die():
    c = Character(0, 300)
    c.lives = 1
    c.take_damage()
    assert c.lives == 0

def test_invincibility_prevents_second_hit():
    c = Character(0, 300)
    c.take_damage()          # lives → 2, invincible_timer set
    c.events.clear()
    c.take_damage()          # should be blocked
    assert c.lives == 2
    assert 'hit' not in c.events

def test_invincibility_timer_set_after_hit():
    c = Character(0, 300)
    c.take_damage()
    assert c.invincible_timer == INVINCIBLE_FRAMES

def test_no_invincibility_timer_on_kill():
    """On the killing hit there's no point setting an invincibility timer."""
    c = Character(0, 300)
    c.lives = 1
    c.take_damage()
    # Character is dead — timer value doesn't matter, but alive must be False
    assert c.alive is False


# ── flip_gravity ──────────────────────────────────────────────────────────────

def test_flip_gravity_toggles_state():
    c = Character(0, 300)
    c.flip_gravity()
    assert c.gravity_flipped is True

def test_flip_gravity_twice_restores_state():
    c = Character(0, 300)
    c.flip_gravity()
    c.flip_gravity()
    assert c.gravity_flipped is False

def test_flip_gravity_detaches_from_ground():
    c = Character(0, 300)
    c.on_ground = True
    c.flip_gravity()
    assert c.on_ground is False


# ── _collect_stars ────────────────────────────────────────────────────────────

def test_collect_star_within_range():
    c     = Character(100, 300)
    stars = [(100, 300)]
    c._collect_stars(stars)
    assert stars == []
    assert c.stars_collected == 1
    assert 'star' in c.events

def test_collect_star_just_within_horizontal_range():
    c     = Character(100, 300)
    stars = [(100 + STAR_COLLECT_RX - 1, 300)]
    c._collect_stars(stars)
    assert c.stars_collected == 1

def test_no_collect_star_outside_horizontal_range():
    c     = Character(100, 300)
    stars = [(100 + STAR_COLLECT_RX + 1, 300)]
    c._collect_stars(stars)
    assert c.stars_collected == 0
    assert stars != []

def test_no_collect_star_outside_vertical_range():
    c     = Character(100, 300)
    stars = [(100, 300 + STAR_COLLECT_RY + 1)]
    c._collect_stars(stars)
    assert c.stars_collected == 0

def test_collect_multiple_stars():
    c     = Character(100, 300)
    stars = [(100, 300), (102, 298)]
    c._collect_stars(stars)
    assert c.stars_collected == 2
    assert stars == []


# ── terrain collision ─────────────────────────────────────────────────────────

def test_character_lands_on_flat_line():
    """
    Character falling onto a flat SpringLine should snap to line y and
    set on_ground=True.
    """
    line_y = 300
    sl = SpringLine(0, line_y, 500, line_y)
    c  = Character(250, line_y - 5)
    c.vy = 5.0   # falling downward

    prev_y = c._apply_physics(grav_sign=1)
    c._resolve_terrain_collision([sl], prev_y, was_on_ground=False, grav_sign=1)

    assert c.on_ground is True
    assert c.y == pytest.approx(line_y, abs=1.0)
    assert 'land' in c.events

def test_character_does_not_land_when_moving_upward():
    line_y = 300
    sl = SpringLine(0, line_y, 500, line_y)
    c  = Character(250, line_y + 2)
    c.vy = -10.0  # moving up through the line

    prev_y = c.y
    c.y   -= 15   # simulate having moved upward past the line
    c._resolve_terrain_collision([sl], prev_y, was_on_ground=False, grav_sign=1)

    assert c.on_ground is False


# ── wall collision ────────────────────────────────────────────────────────────

def test_wall_pushes_character_back():
    c  = Character(100, 300)
    c.vx = 5.0
    # Wall at x=110, width=20, tall enough to overlap character
    wall = (110, 250, 20, 100)
    c._handle_wall_collision([wall])
    # Character should have been pushed left of the wall's left edge
    assert c.x + c.CHAR_W <= 110 + 1  # small tolerance
    assert c.vx == 0
