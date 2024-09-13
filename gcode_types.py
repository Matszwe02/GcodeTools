import math



class Arc:
    def __init__(self, I=None, J=None, K=None, dir=0, plane=0):
        """I, J, K optional; direction 2=CW, 3=CCW; plane 17=XY, 18=XZ, 19=YZ"""
        self.I = I
        self.J = J
        self.K = K
        self.dir = dir
        self.plane=plane


    def subdivide(self): # TODO: 
        raise NotImplementedError()


    def to_dict(self):
        return {'I': self.I, 'J': self.J, 'K': self.K, 'dir': self.dir, 'plane': self.plane}


    def copy(self):
        """Create a deep copy of this Arc instance."""
        return Arc(I=self.I, J=self.J, K=self.K, dir=self.dir, plane=self.plane)



class Position:
    def __init__(self, X: float | None = None, Y: float | None = None, Z: float | None = None, E: float | None = None, F: float | None = None):
        self.X = X
        self.Y = Y
        self.Z = Z
        self.E = E
        self.F = F


    def nullable_op(a: float | None, b: float | None, on_none = None, operation = lambda x, y: x + y):
        if a is None and b is None: return on_none
        if a is None: return b
        if b is None: return a
        return operation(a, b)


    def operation(self, other, operation: function):
        X = operation(self.X, other.X)
        Y = operation(self.Y, other.Y)
        Z = operation(self.Z, other.Z)
        E = operation(self.E, other.E)
        F = operation(self.F, other.F)
        return Position(X, Y, Z, E, F)


    def __add__(self, other):
        add = lambda a, b: self.nullable_op(a, b, None, lambda x, y: x + y)
        return self.operation(other, add)


    def __sub__(self, other):
        subtr = lambda a, b: self.nullable_op(a, b, None, lambda x, y: x - y)
        return self.operation(other, subtr)


    def __mul__(self, other):
        if not isinstance(other, Position): other = Position(other, other, other, other, other)
        scale = lambda a,b: a if a is None or b is None else a * b
        return self.operation(other, scale)


    def valid(self, other):
        """Return Vector of self, with valid dimensions from other"""
        valid = lambda a, b: a if b is not None else None
        return self.operation(other, valid)


    def xyz(self):
        return Position(X=self.X, Y=self.Y, Z=self.Z)


    def e(self):
        return Position(E=self.E)


    def f(self):
        return Position(F=self.F)


    def add(self, other):
        if other.X is not None: self.X += other.X
        if other.Y is not None: self.Y += other.Y
        if other.Z is not None: self.Z += other.Z
        if other.E is not None: self.E += other.E
        if other.F is not None: self.F = other.F


    def set(self, other):
        if other.X is not None: self.X = other.X
        if other.Y is not None: self.Y = other.Y
        if other.Z is not None: self.Z = other.Z
        if other.E is not None: self.E = other.E
        if other.F is not None: self.F = other.F


    def distance(self, other) -> tuple[float, float, float, float]:
        subtr = lambda a, b: self.nullable_op(a, b, 0, lambda x, y: x - y)
        return self.operation(other, subtr)


    def combined_distance(self, other):
        dist = self.distance(other)
        return dist, math.sqrt(dist.X^2 + dist.Y^2 + dist.Z^2)


    def subdivide(self, next, step = 0.1):
        dist_x, dist_y, dist_z, dist_e, dist = self.combined_distance(next)
        pos_list = []
        if dist <= step: return [self]
        
        for i in range(round(dist / step)):
            pos_list.append(self + Position(dist_x, dist_y, dist_z, dist_e) * i)
        return pos_list


    def to_dict(self):
        return {'X': self.X, 'Y': self.Y, 'Z': self.Z, 'E': self.E, 'F': self.F}


    def copy(self):
        """Create a deep copy of this Position instance."""
        return Position(X=self.X, Y=self.Y, Z=self.Z, E=self.E, F=self.F)



class CoordSystem:
    def __init__(self, absolute_coords=True, absolute_extruder=True, speed=600, arc_plane=17):
        self.absolute_coords = absolute_coords
        self.absolute_extruder = absolute_extruder
        self.arc_plane = arc_plane
        self.speed = speed
        self.position = Position(0, 0, 0, 0)
        self.offset = Position(0, 0, 0, 0)


    def set_coords(self, absolute_coords=None):
        if absolute_coords is not None:
            self.absolute_coords = absolute_coords


    def set_extruder(self, absolute_extruder=None):
        if absolute_extruder is not None:
            self.absolute_extruder = absolute_extruder


    def apply_position(self, position:Position):
        if self.absolute_coords:
            self.position.set(position.xyz() + self.offset.xyz())
        else:
            self.position.add(position.xyz())
        
        if self.absolute_extruder:
            self.position.set(position.e() + self.offset.e())
        else:
            self.position.add(position.e())
        
        self.position.set(position.f())
        return self.position


    def set_offset(self, pos: Position):
        self.offset = (self.position - pos).valid(pos)


class GcodeBlock:
    
    def __init__(self, position:Position, offset:Position, arc:Arc=None, command=None, meta={}):
        
        self.position = position.copy()
        self.offset = offset.copy()
        self.arc = None
        if arc is not None:
            self.arc = arc.copy()
        self.command = command
        self.meta = json.loads(json.dumps(meta))


    def to_dict(self):
        return_dict = {
                'command': self.command,
                'position': self.position.__dict__,
                'offset': self.offset.__dict__,
                'meta': self.meta,
                'arc': None
            }
        if self.arc is not None: return_dict['arc'] = self.arc.__dict__
        return return_dict
