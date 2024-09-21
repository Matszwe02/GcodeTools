import math
import json



class Static:
    ABSOLUTE_COORDS = 'G90'
    RELATIVE_COORDS = 'G91'

    ABSOLUTE_EXTRUDER = 'M82'
    RELATIVE_EXTRUDER = 'M83'

    SET_POSITION = 'G92'

    ARC_PLANE_XY = 'G17'
    ARC_PLANE_XZ = 'G18'
    ARC_PLANE_YZ = 'G19'



class Vector:

    def zero():
        return Vector(0, 0, 0, 0)


    def __init__(self, X: float | None = None, Y: float | None = None, Z: float | None = None, E: float | None = None):
        self.X = X
        self.Y = Y
        self.Z = Z
        self.E = E


    def from_params(self, params: list[list[str]]):
        for param in params[1]:
            if param[0] == 'X': self.X = float(param[1:])
            if param[0] == 'Y': self.Y = float(param[1:])
            if param[0] == 'Z': self.Z = float(param[1:])
            if param[0] == 'E': self.E = float(param[1:])
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
        return Vector(X, Y, Z, E)


    def __add__(self, other):
        add = lambda a, b: self.nullable_op(a, b, None, lambda x, y: x + y)
        return self.operation(other, add)


    def __sub__(self, other):
        subtr = lambda a, b: self.nullable_op(a, b, None, lambda x, y: x - y)
        return self.operation(other, subtr)


    def __mul__(self, other):
        if not isinstance(other, Vector): other = Vector(other, other, other, other, other)
        scale = lambda a,b: a if a is None or b is None else a * b
        return self.operation(other, scale)


    def valid(self, other):
        """Return Vector with non-null dimensions from other Vector"""
        valid = lambda a, b: a if b is not None else None
        return self.operation(other, valid)


    def xyz(self):
        return Vector(X=self.X, Y=self.Y, Z=self.Z)


    def e(self):
        return Vector(E=self.E)


    def add(self, other):
        if other.X is not None: self.X += other.X
        if other.Y is not None: self.Y += other.Y
        if other.Z is not None: self.Z += other.Z
        if other.E is not None: self.E += other.E


    def set(self, other):
        if other.X is not None: self.X = other.X
        if other.Y is not None: self.Y = other.Y
        if other.Z is not None: self.Z = other.Z
        if other.E is not None: self.E = other.E


    def distance(self, other):
        subtr = lambda a, b: self.nullable_op(a, b, 0, lambda x, y: x - y)
        return self.operation(other, subtr)


    def copy(self):
        """Create a deep copy"""
        return Vector(X=self.X, Y=self.Y, Z=self.Z, E=self.E)


    def to_dict(self):
        return {'X': self.X, 'Y': self.Y, 'Z': self.Z, 'E': self.E}


    def __bool__(self):
        return any(coord is not None for coord in [self.X, self.Y, self.Z, self.E])



class CoordSystem:

    def __init__(self, abs_xyz=True, abs_e=True, speed=600, arc_plane=17, position = Vector.zero(), offset = Vector.zero()):
        self.abs_xyz = abs_xyz
        self.abs_e = abs_e
        self.speed = speed
        self.arc_plane = arc_plane
        self.position = position
        self.offset = offset


    def set_xyz_coords(self, abs_xyz=None):
        if abs_xyz is not None:
            self.abs_xyz = abs_xyz


    def set_e_coords(self, abs_e=None):
        if abs_e is not None:
            self.abs_e = abs_e


    def apply_move(self, move):
        if type(move) is not Move or not move.position: return Vector()
        if self.abs_xyz:
            self.position.set(move.position.xyz() + self.offset.xyz())
        else:
            self.position.add(move.position.xyz())
        
        if self.abs_e:
            self.position.set(move.position.e() + self.offset.e())
        else:
            self.position.add(move.position.e())
        
        if move.speed is not None:
            self.speed = move.speed
        
        return self.position


    def set_offset(self, pos: Vector):
        self.offset = (self.position - pos).valid(pos)


    def to_dict(self):
        return {'abs_xyz' : self.abs_xyz, "abs_e" : self.abs_e, "speed" : self.speed, "position": self.position.to_dict()}


    def copy(self):
        return CoordSystem(abs_xyz=self.abs_xyz, abs_e=self.abs_e, speed=self.speed, arc_plane=self.arc_plane, position=self.position.copy(), offset=self.offset.copy())



class Move:

    def __init__(self, coords: CoordSystem, position = Vector(), speed: float|None = None):
        self.position = position.copy()
        self.speed = speed
        self.coords = coords.copy()


    def from_params(self, params: list[list[str]]):
        for param in params[1]:
            if param[0] == 'F': self.speed = float(param[1:])
        self.position.from_params(params)
        return self


    def distance(self) -> Vector:
        distance = lambda a, b: self.position.nullable_op(a, b, 0, lambda x, y: x - y)
        return self.position.operation(self.coords.position, distance)


    def float_distance(self, distance: Vector):
        return math.sqrt(distance.X^2 + distance.Y^2 + distance.Z^2)


    def subdivide(self, step = 0.1) -> list[Vector]:
        dist_pos = self.distance()
        dist = self.float_distance(dist_pos)
        pos_list = []
        if dist <= step: return [self]
        stop = round(dist / step)
        for i in range(stop):
            i_normal = i / stop
            pos_list.append(self.coords.position * (1 - i_normal) + self.position * i_normal)
        return pos_list


    def to_str(self, last_move = None):
        nullable = lambda param, a, b: '' if a is None or b is None else f' {param}{round(a - b, 5)}'
        
        out = ''
        cmd = 'G0'
        
        if self.position.X != self.coords.position.X: out += nullable('X', self.position.X, 0 if self.coords.abs_xyz else self.coords.position.X)
        if self.position.Y != self.coords.position.Y: out += nullable('Y', self.position.Y, 0 if self.coords.abs_xyz else self.coords.position.Y)
        if self.position.Z != self.coords.position.Z: out += nullable('Z', self.position.Z, 0 if self.coords.abs_xyz else self.coords.position.Z)
        if self.position.E != self.coords.position.E: 
            cmd = 'G1'
            out += nullable('E', self.position.E, 0 if self.coords.abs_e else self.coords.position.E)
        
        if self.speed is not None:
            out += nullable('F', self.speed, 0)
        
        if type(last_move) == Move:
            if last_move.coords.abs_xyz != self.coords.abs_xyz:
                cmd = (Static.ABSOLUTE_COORDS if self.coords.abs_xyz else Static.RELATIVE_COORDS) + '\n' + cmd
            if last_move.coords.abs_e != self.coords.abs_e:
                cmd = (Static.ABSOLUTE_EXTRUDER if self.coords.abs_e else Static.RELATIVE_EXTRUDER) + '\n' + cmd
                
        
        if len(out) < 4: return ''
        return cmd + out


    def to_dict(self):
        return {'Current' : self.position, "Previous" : self.coords.position}


    def copy(self):
        """Create a deep copy"""
        return Move(position=self.position.copy(), speed=self.speed, coords=self.coords.copy())




# TODO: arc support
# class Arc:
#     def __init__(self, I=None, J=None, K=None, dir=0, plane=0, next_pos: Position = Position(), prev_pos: Position = Position()):
#         """I, J, K optional; direction 2=CW, 3=CCW; plane 17=XY, 18=XZ, 19=YZ"""
#         self.I = I
#         self.J = J
#         self.K = K
#         self.dir = dir
#         self.plane=plane
#         self.next_pos = next_pos
#         self.prev_pos = prev_pos


#     def from_params(self, params: list[list[str]], coords: CoordSystem):
        
#         for param in params[1]:
#             if param[0] == 'I': self.I = float(param[1:])
#             if param[0] == 'J': self.J = float(param[1:])
#             if param[0] == 'K': self.K = float(param[1:])
        
#         if params[0] == 'G2': self.dir=2
#         if params[0] == 'G3': self.dir=3
        
#         self.next_pos = Position().from_params(params).copy()
#         self.prev_pos = coords.position.copy()
        
#         return self

#     def to_str(self):        
#         append_nullable = lambda param, value: '' if value is None else f'{param}{round(value, 5)} '
        
#         command = "G2" if self.dir == 2 else "G3"
        
#         out = f"{command} "
        
#         out += append_nullable('I', self.I)
#         out += append_nullable('J', self.J)
#         out += append_nullable('K', self.K)
        
#         out += (self.next_pos - self.prev_pos).to_str()[3:]

#         return out.removesuffix(" ")


#     def to_dict(self):
#         return {'I': self.I, 'J': self.J, 'K': self.K, 'dir': self.dir, 'plane': self.plane}


#     def copy(self):
#         """Create a deep copy of this Arc instance."""
#         return Arc(I=self.I, J=self.J, K=self.K, dir=self.dir, plane=self.plane, next_pos=self.next_pos.copy(), prev_pos=self.prev_pos.copy())



class GcodeBlock:
    
    def __init__(self, move: Move, command: str | None = None, meta = {}):
        
        self.move = move.copy()
        self.arc = None
        # if arc is not None:
        #     self.arc = arc.copy()
        self.command = command
        self.meta = json.loads(json.dumps(meta))


    def to_dict(self):
        return_dict = {
                'command': self.command,
                'move': self.move.__dict__,
                'meta': self.meta
            }
        return return_dict
