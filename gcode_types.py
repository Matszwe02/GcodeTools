import math
import json



class Config:
    """G-Code configuration"""
    precision = 5
    """N decimal digits"""
    
    speed = 600
    """Default speed in mm/min"""
    
    step = 0.1
    """Step over which maths iterate"""



class Static:
    """G-Code command definitions"""
    ABSOLUTE_COORDS = 'G90'
    RELATIVE_COORDS = 'G91'
    
    ABSOLUTE_EXTRUDER = 'M82'
    RELATIVE_EXTRUDER = 'M83'

    SET_POSITION = 'G92'

    ARC_PLANE_XY = 'G17'
    ARC_PLANE_XZ = 'G18'
    ARC_PLANE_YZ = 'G19'

    ARC_PLANES = {'G17': 17, 'G18' : 18, 'G19': 19}


    ABSOLUTE_COORDS_DESC = 'G90; Absolute Coordinates'
    RELATIVE_COORDS_DESC = 'G91; Relative Coordinates'
    ABSOLUTE_EXTRUDER_DESC = 'M82; Absolute Extruder'
    RELATIVE_EXTRUDER_DESC = 'M83; Relative Extruder'
    ARC_PLANE_XY_DESC = 'G17; Arc Plane XY'
    ARC_PLANE_XZ_DESC = 'G18; Arc Plane XZ'
    ARC_PLANE_YZ_DESC = 'G19; Arc Plane YZ'



class Vector:

    def zero():
        """Vector(0, 0, 0, 0)"""
        return Vector(0, 0, 0, 0)


    def __init__(self, X: float | None = None, Y: float | None = None, Z: float | None = None, E: float | None = None):
        """Vector(None, None, None, None)"""
        self.X = X
        self.Y = Y
        self.Z = Z
        self.E = E


    def from_params(self, params: dict[str, list[str]]):
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
        if type(other) is not Vector: raise TypeError(f'Invalid operation between Vector and {type(other)}')
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
        """Adds Vector's dimensions to other's that are not None"""
        if type(other) is not Vector: raise TypeError('Can only add Vector to Vector')
        if other.X is not None: self.X += other.X
        if other.Y is not None: self.Y += other.Y
        if other.Z is not None: self.Z += other.Z
        if other.E is not None: self.E += other.E


    def set(self, other):
        """Sets Vector's dimensions to other's that are not None"""
        if type(other) is not Vector: raise TypeError('Can only set Vector to Vector')
        if other.X is not None: self.X = other.X
        if other.Y is not None: self.Y = other.Y
        if other.Z is not None: self.Z = other.Z
        if other.E is not None: self.E = other.E


    def copy(self):
        """Create a deep copy"""
        return Vector(self.X, self.Y, self.Z, self.E)


    def to_dict(self):
        return {'X': self.X, 'Y': self.Y, 'Z': self.Z, 'E': self.E}


    def __bool__(self):
        return any(coord is not None for coord in [self.X, self.Y, self.Z, self.E])



class CoordSystem:

    def __init__(self, abs_xyz=True, abs_e=True, speed=Config.speed, arc_plane=Static.ARC_PLANES[Static.ARC_PLANE_XY], position = Vector.zero(), offset = Vector.zero()):
        self.abs_xyz = abs_xyz
        self.abs_e = abs_e
        self.speed = speed
        self.arc_plane = arc_plane
        self.position = position
        self.offset = offset


    def set_abs_xyz(self, abs_xyz=None):
        if abs_xyz is not None:
            self.abs_xyz = abs_xyz


    def set_abs_e(self, abs_e=None):
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
        self.offset.set((self.position - pos).valid(pos))


    def to_dict(self):
        return {'abs_xyz' : self.abs_xyz, "abs_e" : self.abs_e, "speed" : self.speed, "position": self.position, "offset": self.offset}


    def copy(self):
        return CoordSystem(self.abs_xyz, self.abs_e, self.speed, self.arc_plane, self.position.copy(), self.offset.copy())



class Move:

    def __init__(self, coords: CoordSystem, position = Vector(), speed: float|None = None):
        self.position = position.copy()
        """The end vector of Move"""
        self.coords = coords.copy()
        """Coords hold position, which is the beginning vector of Move"""
        self.speed = speed


    def from_params(self, params: dict[str, list[str]]):
        for param in params[1]:
            if param[0] == 'F': self.speed = float(param[1:])
        self.position.from_params(params)
        return self


    def distance(self):
        distance = lambda a, b: self.position.nullable_op(a, b, 0, lambda x, y: x - y)
        return self.position.operation(self.coords.position, distance)


    def float_distance(self, distance: Vector):
        return math.sqrt(distance.X^2 + distance.Y^2 + distance.Z^2)


    def subdivide(self, step = Config.step) -> list[Vector]:
        dist_pos = self.distance()
        dist = self.float_distance(dist_pos)
        pos_list = []
        if dist <= step: return [self]
        stop = round(dist / step)
        for i in range(stop):
            i_normal = i / stop
            pos_list.append(self.coords.position * (1 - i_normal) + self.position * i_normal)
        return pos_list


    def set_coord_system(self, abs_xyz: float|None = None, abs_e: float|None = None):
        if abs_xyz is not None:
            self.coords.set_abs_xyz(abs_xyz)
        if abs_e is not None:
            self.coords.set_abs_e(abs_e)


    def get_flowrate(self):
        """Returns flowrate (mm in E over mm in XYZ). Returns None if no XYZ movement"""
        dist_vec = self.distance()
        distance = self.float_distance(dist_vec)
        if distance < Config.step: return None
        return dist_vec.e() / distance


    def set_flowrate(self, flowrate: float):
        """Sets flowrate (mm in E over mm in XYZ). Returns None if no XYZ movement, otherwise returns E mm"""
        dist_vec = self.distance()
        distance = self.float_distance(dist_vec)
        if distance < Config.step: return None
        flow = distance * flowrate
        self.position.E = self.coords.position.E + flow
        return flow


    def to_str(self, last_move = None):
        nullable = lambda param, a, b: '' if a is None or b is None else f' {param}{round(a - b, Config.precision)}'
        
        out = 'G1'
        cmd = ''
        
        offset = Vector.zero()
        if not self.coords.abs_xyz:
            offset.set(self.coords.position.xyz())
        if not self.coords.abs_e:
            offset.set(self.coords.position.e())
        
        if self.position.X != self.coords.position.X: out += nullable('X', self.position.X, offset.X)
        if self.position.Y != self.coords.position.Y: out += nullable('Y', self.position.Y, offset.Y)
        if self.position.Z != self.coords.position.Z: out += nullable('Z', self.position.Z, offset.Z)
        if self.position.E != self.coords.position.E: out += nullable('E', self.position.E, offset.E)
        
        if self.speed is not None:
            out += nullable('F', self.speed, 0)
        
        if type(last_move) == Move:
            if last_move.coords.abs_xyz != self.coords.abs_xyz:
                cmd = (Static.ABSOLUTE_COORDS_DESC if self.coords.abs_xyz else Static.RELATIVE_COORDS_DESC) + '\n' + cmd
            if last_move.coords.abs_e != self.coords.abs_e:
                cmd = (Static.ABSOLUTE_EXTRUDER_DESC if self.coords.abs_e else Static.RELATIVE_EXTRUDER_DESC) + '\n' + cmd
        else:
            cmd = (Static.ABSOLUTE_COORDS_DESC if self.coords.abs_xyz else Static.RELATIVE_COORDS_DESC) + '\n' + cmd
            cmd = (Static.ABSOLUTE_EXTRUDER_DESC if self.coords.abs_e else Static.RELATIVE_EXTRUDER_DESC) + '\n' + cmd
        
        if len(out) < 4: return cmd
        return cmd + out


    def to_dict(self):
        return {'Current' : self.position, "Previous" : self.coords.position}


    def copy(self):
        """Create a deep copy"""
        return Move(self.coords.copy(), self.position.copy(), self.speed)




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
