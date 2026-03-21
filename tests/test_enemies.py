"""
Tests for Enemy logic.

Covers hit detection, stomp detection, and hit-cooldown — the rules that
determine gameplay outcomes when the player interacts with an enemy.
"""

import pytest
from enemies import Enemy


def _enemy_at(x=200, y=300):
    return Enemy(x, y)


# ── hits_player ───────────────────────────────────────────────────────────────

def test_hits_player_when_overlapping():
    e = _enemy_at(200, 300)
    assert e.hits_player(200, 300) is True

def test_hits_player_just_within_horizontal_range():
    e = _enemy_at(200, 300)
    assert e.hits_player(200 + Enemy._HIT_RANGE - 1, 300) is True

def test_no_hit_outside_horizontal_range():
    e = _enemy_at(200, 300)
    assert e.hits_player(200 + Enemy._HIT_RANGE + 1, 300) is False

def test_no_hit_outside_vertical_range():
    e = _enemy_at(200, 300)
    assert e.hits_player(200, 300 + 45) is False

def test_no_hit_when_dead():
    e = _enemy_at(200, 300)
    e.alive = False
    assert e.hits_player(200, 300) is False


# ── stomped_by ────────────────────────────────────────────────────────────────

def test_stomp_from_directly_above():
    e = _enemy_at(200, 300)
    # Player just above enemy, falling down
    assert e.stomped_by(200, 308, pvy=5.0) is True

def test_no_stomp_when_moving_upward():
    e = _enemy_at(200, 300)
    assert e.stomped_by(200, 308, pvy=-1.0) is False

def test_no_stomp_when_too_far_above():
    e = _enemy_at(200, 300)
    # py - e.y must be in [0, 18]; here py < e.y
    assert e.stomped_by(200, 280, pvy=5.0) is False

def test_no_stomp_when_too_far_below():
    e = _enemy_at(200, 300)
    assert e.stomped_by(200, 320, pvy=5.0) is False

def test_no_stomp_outside_horizontal_range():
    e = _enemy_at(200, 300)
    assert e.stomped_by(230, 308, pvy=5.0) is False

def test_no_stomp_when_dead():
    e = _enemy_at(200, 300)
    e.alive = False
    assert e.stomped_by(200, 308, pvy=5.0) is False


# ── hit cooldown ──────────────────────────────────────────────────────────────

def test_can_hit_initially():
    e = _enemy_at()
    assert e.can_hit() is True

def test_cannot_hit_immediately_after_register():
    e = _enemy_at()
    e.register_hit()
    assert e.can_hit() is False

def test_can_hit_again_after_cooldown_expires():
    e = _enemy_at()
    e.register_hit()
    # Tick the cooldown down manually via update (no segments, player far away)
    for _ in range(Enemy._HIT_COOLDOWN):
        e.update(player_x=9999, player_y=300, segments=[])
    assert e.can_hit() is True
