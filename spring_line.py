"""
spring_line.py – SpringLine terrain physics for La Linea.

A SpringLine is a chain of physics nodes that form the game's terrain.
Each node springs back to its rest height and is coupled to its neighbours,
so the line sags under the character's weight and ripples on landing.
"""


class SpringLine:
    NODE_SPACING = 10   # pixels between physics nodes

    # Spring constants
    K_REST    = 0.022   # pull each node back toward its rest height
    K_TENSION = 0.28    # coupling between adjacent nodes (wave speed)
    DAMPING   = 0.89    # velocity multiplier per frame (< 1 = energy loss)

    def __init__(self, x1, y1, x2, y2):
        self.x1 = float(x1)
        self.x2 = float(x2)
        n = max(2, int((x2 - x1) / self.NODE_SPACING) + 1)
        self.nx  = [x1 + i * (x2 - x1) / (n - 1) for i in range(n)]
        self.ry  = [y1 + i * (y2 - y1) / (n - 1) for i in range(n)]
        self.y   = list(self.ry)
        self.vy  = [0.0] * n

    @property
    def y1(self): return self.y[0]
    @property
    def y2(self): return self.y[-1]

    def contains_x(self, x):
        return self.x1 <= x <= self.x2

    def y_at(self, x):
        """Interpolate current (deformed) y at world-x."""
        if x <= self.nx[0]:  return self.y[0]
        if x >= self.nx[-1]: return self.y[-1]
        for i in range(len(self.nx) - 1):
            if self.nx[i] <= x <= self.nx[i + 1]:
                t = (x - self.nx[i]) / (self.nx[i + 1] - self.nx[i])
                return self.y[i] + t * (self.y[i + 1] - self.y[i])
        return self.y[-1]

    def apply_force(self, x, force, radius=28):
        """Push nodes downward at world-x with a bell-curve influence."""
        for i, nx in enumerate(self.nx):
            d = abs(nx - x)
            if d < radius:
                influence = (1.0 - d / radius) ** 2
                self.vy[i] += force * influence

    def update(self):
        """Advance spring physics one timestep."""
        n   = len(self.y)
        acc = [0.0] * n
        for i in range(n):
            acc[i] += self.K_REST * (self.ry[i] - self.y[i])
            if i > 0:
                acc[i] += self.K_TENSION * (self.y[i - 1] - self.y[i])
            if i < n - 1:
                acc[i] += self.K_TENSION * (self.y[i + 1] - self.y[i])
        for i in range(n):
            self.vy[i] = (self.vy[i] + acc[i]) * self.DAMPING
            self.y[i] += self.vy[i]

    @classmethod
    def from_path(cls, points):
        """
        Build one continuous SpringLine from a list of (x, y) waypoints.
        Nodes are distributed at NODE_SPACING intervals; rest-y is
        piecewise-linear through the waypoints so slopes are preserved.
        """
        obj      = cls.__new__(cls)
        obj.x1   = float(points[0][0])
        obj.x2   = float(points[-1][0])
        obj.nx   = []
        obj.ry   = []
        for i in range(len(points) - 1):
            px1, py1 = points[i]
            px2, py2 = points[i + 1]
            dx = px2 - px1
            n  = max(2, int(dx / cls.NODE_SPACING))
            for j in range(n):
                t = j / n
                obj.nx.append(px1 + t * dx)
                obj.ry.append(py1 + t * (py2 - py1))
        obj.nx.append(float(points[-1][0]))
        obj.ry.append(float(points[-1][1]))
        obj.y  = list(obj.ry)
        obj.vy = [0.0] * len(obj.nx)
        return obj
