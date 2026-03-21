"""
Tests for SpringLine physics.

These lock in the spring physics behaviour so refactors can't silently
break terrain collision or deformation.
"""

import pytest
from spring_line import SpringLine


# ── Construction ──────────────────────────────────────────────────────────────

def test_flat_line_has_uniform_rest_y():
    sl = SpringLine(0, 100, 200, 100)
    for ry in sl.ry:
        assert ry == pytest.approx(100.0)

def test_sloped_line_interpolates_rest_y():
    sl = SpringLine(0, 100, 100, 200)
    assert sl.ry[0]  == pytest.approx(100.0)
    assert sl.ry[-1] == pytest.approx(200.0)

def test_from_path_preserves_endpoints():
    pts = [(0, 100), (100, 150), (200, 100)]
    sl  = SpringLine.from_path(pts)
    assert sl.x1 == 0.0
    assert sl.x2 == 200.0
    assert sl.y[0]  == pytest.approx(100.0)
    assert sl.y[-1] == pytest.approx(100.0)

def test_from_path_midpoint_height():
    pts = [(0, 100), (100, 200), (200, 100)]
    sl  = SpringLine.from_path(pts)
    # The peak should be near y=200
    peak = max(sl.ry)
    assert peak == pytest.approx(200.0, abs=1.0)


# ── y_at interpolation ────────────────────────────────────────────────────────

def test_y_at_left_endpoint():
    sl = SpringLine(50, 100, 200, 200)
    assert sl.y_at(50) == pytest.approx(100.0)

def test_y_at_right_endpoint():
    sl = SpringLine(50, 100, 200, 200)
    assert sl.y_at(200) == pytest.approx(200.0)

def test_y_at_midpoint_flat_line():
    sl = SpringLine(0, 100, 200, 100)
    assert sl.y_at(100) == pytest.approx(100.0, abs=1.0)

def test_y_at_clamps_left_of_range():
    sl = SpringLine(50, 100, 150, 100)
    assert sl.y_at(0) == sl.y_at(50)

def test_y_at_clamps_right_of_range():
    sl = SpringLine(50, 100, 150, 100)
    assert sl.y_at(200) == sl.y_at(150)

def test_y_at_interpolates_slope():
    sl  = SpringLine(0, 100, 100, 200)
    mid = sl.y_at(50)
    assert 100.0 < mid < 200.0


# ── contains_x ────────────────────────────────────────────────────────────────

def test_contains_x_left_edge():
    sl = SpringLine(50, 100, 150, 100)
    assert sl.contains_x(50)

def test_contains_x_right_edge():
    sl = SpringLine(50, 100, 150, 100)
    assert sl.contains_x(150)

def test_contains_x_midpoint():
    sl = SpringLine(50, 100, 150, 100)
    assert sl.contains_x(100)

def test_contains_x_outside_left():
    sl = SpringLine(50, 100, 150, 100)
    assert not sl.contains_x(49)

def test_contains_x_outside_right():
    sl = SpringLine(50, 100, 150, 100)
    assert not sl.contains_x(151)


# ── Spring physics ────────────────────────────────────────────────────────────

def test_endpoints_stay_pinned_after_force_and_update():
    sl = SpringLine(0, 100, 200, 200)
    sl.apply_force(100, 50)
    for _ in range(20):
        sl.update()
    assert sl.y[0]  == pytest.approx(100.0)
    assert sl.y[-1] == pytest.approx(200.0)

def test_apply_force_displaces_nearby_nodes():
    sl = SpringLine(0, 100, 400, 100)
    centre_y_before = sl.y_at(200)
    sl.apply_force(200, 50)
    centre_y_after = sl.y_at(200)
    assert centre_y_after > centre_y_before  # pushed downward

def test_spring_settles_back_to_rest():
    sl = SpringLine(0, 100, 400, 100)
    sl.apply_force(200, 80)
    for _ in range(600):
        sl.update()
    assert sl.y_at(200) == pytest.approx(100.0, abs=0.5)

def test_force_has_bell_curve_falloff():
    sl = SpringLine(0, 100, 400, 100)
    sl.apply_force(200, 50, radius=40)
    # Node right at centre should be displaced more than a node near the edge of radius
    disp_centre = sl.y_at(200) - 100
    disp_edge   = sl.y_at(239) - 100   # just inside radius=40
    assert disp_centre > disp_edge > 0

def test_no_force_no_displacement():
    sl = SpringLine(0, 100, 200, 100)
    for _ in range(10):
        sl.update()
    for y in sl.y:
        assert y == pytest.approx(100.0)
