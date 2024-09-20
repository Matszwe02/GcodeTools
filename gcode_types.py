import math
import json



class Position:
    def __init__(self, X: float | None = None, Y: float | None = None, Z: float | None = None, E: float | None = None, F: float | None = None):
        self.X = X
        self.Y = Y
        self.Z = Z
        self.E = E
        self.F = F


    def from_params(self, params: list[list[str]]):
        for param in params[1]:
            if param[0] == 'X': self.X = float(param[1:])
            if param[0] == 'Y': self.Y = float(param[1:])
            if param[0] == 'Z': self.Z = float(param[1:])
            if param[0] == 'E': self.E = float(param[1:])
            if param[0] == 'F': self.F = float(param[1:])
        return self


    def nullable_op(self, a: float | None, b: float | None, on_none = None, operation = lambda x, y: x + y):
        if a is None and b is None: return on_none
        if a is None: return b
        if b is None: return a
        return operation(a, b)


    def operation(self, other, operation):
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


    def distance(self, other):
        subtr = lambda a, b: self.nullable_op(a, b, 0, lambda x, y: x - y)
        return self.operation(other, subtr)


    def combined_distance(self, other):
        dist = self.distance(other)
        return dist, math.sqrt(dist.X^2 + dist.Y^2 + dist.Z^2)


    def subdivide(self, next, step = 0.1):
        dist_pos, dist = self.combined_distance(next)
        pos_list = []
        if dist <= step: return [self]
        
        for i in range(round(dist / step)):
            pos_list.append(self + dist_pos * i)
        return pos_list


    def to_str(self, previous = None, rel_e = False):
        append_nullable = lambda param, value: '' if value is None else f'{param}{value:.4f} '
        
        out = 'G1 '
        if previous is None:
            out += append_nullable('X', self.X)
            out += append_nullable('Y', self.Y)
            out += append_nullable('Z', self.Z)
            out += append_nullable('E', self.E)
            out += append_nullable('F', self.F)
            return out
        
        if self.X != previous.X: out += append_nullable('X', self.X)
        if self.Y != previous.Y: out += append_nullable('Y', self.Y)
        if self.Z != previous.Z: out += append_nullable('Z', self.Z)
        if self.E != previous.E and self.E is not None: out += f"E{self.E - previous.E:.4f} "
        if self.F != previous.F: out += append_nullable('F', self.F)
        
        if len(out) < 4: return ''
        return out.removesuffix(" ")


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



class Arc:
    def __init__(self, I=None, J=None, K=None, dir=0, plane=0, next_pos: Position = Position(), prev_pos: Position = Position()):
        """I, J, K optional; direction 2=CW, 3=CCW; plane 17=XY, 18=XZ, 19=YZ"""
        self.I = I
        self.J = J
        self.K = K
        self.dir = dir
        self.plane=plane
        self.next_pos = next_pos
        self.prev_pos = prev_pos


    def from_params(self, params: list[list[str]], coords: CoordSystem):
        
        for param in params[1]:
            if param[0] == 'I': self.I = float(param[1:])
            if param[0] == 'J': self.J = float(param[1:])
            if param[0] == 'K': self.K = float(param[1:])
        
        if params[0] == 'G2': self.dir=2
        if params[0] == 'G3': self.dir=3
        
        self.next_pos = Position().from_params(params).copy()
        self.prev_pos = coords.position.copy()
        
        return self

# FIXME: check calculations
    def subdivide(self, step=0.1) -> list[Position]:
        def interpolate(t):
            t = max(0, min(1, t))
            # return Position(
            #     X=self.prev_pos.X + (self.next_pos.X - self.prev_pos.X) * t,
            #     Y=self.prev_pos.Y + (self.next_pos.Y - self.prev_pos.Y) * t,
            #     Z=self.prev_pos.Z + (self.next_pos.Z - self.prev_pos.Z) * t,
            #     E=self.prev_pos.E + (self.next_pos.E - self.prev_pos.E) * t,
            #     F=self.next_pos.F
            # )
            return self.prev_pos + (self.next_pos - self.prev_pos) * t

        def arc_length(theta):
            radius = math.sqrt(self.I**2 + self.J**2)
            return abs(radius * theta)

        def angle_to_t(angle):
            full_angle = 2 * math.pi if self.dir == 2 else -2 * math.pi
            return angle / full_angle

        positions = []
        total_length = arc_length(2 * math.pi)
        
        if total_length <= step:
            positions.append(self.prev_pos)
            positions.append(self.next_pos)
            return positions

        angle_step = step / (total_length / (2 * math.pi))
        current_angle = 0
        
        while current_angle < 2 * math.pi:
            t = angle_to_t(current_angle)
            new_position = interpolate(t)
            
            if self.dir == 2:  # CW
                new_position.X += self.I - self.I * math.cos(current_angle) + self.J * math.sin(current_angle)
                new_position.Y += self.J - self.I * math.sin(current_angle) - self.J * math.cos(current_angle)
            else:  # CCW
                new_position.X += self.I - self.I * math.cos(-current_angle) + self.J * math.sin(-current_angle)
                new_position.Y += self.J - self.I * math.sin(-current_angle) - self.J * math.cos(-current_angle)
            
            positions.append(new_position)
            current_angle += angle_step
        
        positions.append(self.next_pos)
        
        return positions


    def to_str(self):        
        append_nullable = lambda param, value: '' if value is None else f'{param}{value:.4f} '
        
        command = "G2" if self.dir == 2 else "G3"
        
        out = f"{command} "
        
        out += append_nullable('I', self.I)
        out += append_nullable('J', self.J)
        out += append_nullable('K', self.K)

        return out.removesuffix(" ")


    def to_dict(self):
        return {'I': self.I, 'J': self.J, 'K': self.K, 'dir': self.dir, 'plane': self.plane}


    def copy(self):
        """Create a deep copy of this Arc instance."""
        return Arc(I=self.I, J=self.J, K=self.K, dir=self.dir, plane=self.plane, next_pos=self.next_pos.copy(), prev_pos=self.prev_pos.copy())



class GcodeBlock:
    
    def __init__(self, position: Position, offset: Position, arc: Arc = None, command: str | None = None, meta = {}):
        
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
