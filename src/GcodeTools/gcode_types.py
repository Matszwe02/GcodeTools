import math
import json
import typing



def float_or_none(input):
    if input is not None: return float(input)
    return input


class Coords:
    def __init__(self, params: dict[str, str]):
        self.X = float_or_none(params.get('X'))
        self.Y = float_or_none(params.get('Y'))
        self.Z = float_or_none(params.get('Z'))
        self.E = float_or_none(params.get('E'))
        self.F = float_or_none(params.get('F'))
        self.I = float_or_none(params.get('I'))
        self.J = float_or_none(params.get('J'))
        self.K = float_or_none(params.get('K'))


def remove_chars(string: str, chars: str)->str:
    outstr = string
    for char in chars:
        outstr = outstr.replace(char, '')
    return outstr


def dict_to_pretty_str(d: dict) -> str:
    """Converts a dictionary to a pretty string format: key=value, key2=value2"""
    return ", ".join(f"{k}={v}" for k, v in d.items())


def check_null_except(obj, obj_type, on_none: typing.Callable|Exception|None = Exception, alert="Can only use {0}, not {1}"):
    """
    Check wrong object, with optional object creation on None
    
    checks if `obj` is instance of `obj_type`, otherwise raises `TypeError` with `alert`
    
    Args:
        obj: `Object`
        obj_type: `class`
        on_none: 
            None: to automatically set with `obj_type` constructor
            Exception: to except on None
            Object's constructor method: to construct `Object`
        alert: `str`
    """
    if not isinstance(obj, obj_type):
        if obj is None and on_none is not Exception:
            obj = on_none if on_none is not set else obj_type()
        else:
            raise TypeError(alert.format(obj_type, type(obj)))


class Config:
    """G-Code configuration"""
    
    def __init__(self):
        self.precision = 5
        """N decimal digits"""
        
        self.speed = 1200
        """Default speed in mm/min"""
        
        self.step = 0.1
        """Step over which maths iterate"""

        self.enable_exclude_object = True



class Static:
    """G-Code command definitions"""
    ABSOLUTE_COORDS = 'G90'
    RELATIVE_COORDS = 'G91'
    
    ABSOLUTE_EXTRUDER = 'M82'
    RELATIVE_EXTRUDER = 'M83'

    SET_POSITION = 'G92'
    
    HOME = 'G28'

    ARC_PLANES = {'G17': 17, 'G18' : 18, 'G19': 19, 'XY' : 17, 'XZ': 18, 'YZ': 19}

    FAN_SPEED = 'M106'
    FAN_OFF = 'M107'
    E_TEMP = 'M104'
    BED_TEMP = 'M140'
    E_TEMP_WAIT = 'M104'
    BED_TEMP_WAIT = 'M140'
    TOOL_CHANGE = 'T'

    ABSOLUTE_COORDS_DESC = 'G90; Absolute Coordinates'
    RELATIVE_COORDS_DESC = 'G91; Relative Coordinates'
    ABSOLUTE_EXTRUDER_DESC = 'M82; Absolute Extruder'
    RELATIVE_EXTRUDER_DESC = 'M83; Relative Extruder'
    HOME_DESC = 'G28; Home all axes'
    E_TEMP_DESC = 'M104 S{0}; Set Extruder Temperature'
    BED_TEMP_DESC = 'M140 S{0}; Set Bed Temperature'
    E_TEMP_WAIT_DESC = 'M109 S{0}; Set Extruder Temperature and Wait'
    BED_TEMP_WAIT_DESC = 'M190 S{0}; Set Bed Temperature and Wait'
    FAN_SPEED_DESC = 'M106 S{0}; Set Fan Speed'
    TOOL_CHANGE_DESC = 'T{0}; Change Tool'
    
    ARC_PLANES_DESC = {17: 'G17; Arc Plane XY', 18: 'G18; Arc Plane XZ', 19: 'G19; Arc Plane YZ'}

    PRINT_START = 0
    PRINT_END = 1
    SKIRT = 2
    EXTERNAL_PERIMETER = 3
    INTERNAL_PERIMETER = 4
    OVERHANG_PERIMETER = 5
    SOLID_INFILL = 6
    TOP_SOLID_INFILL = 7
    SPARSE_INFILL = 8
    BRIDGE = 9
    SUPPORT = 10
    NO_OBJECT = -1

    MOVE_TYPES = {4: 'Perimeter', 3: 'External perimeter', 2: 'Skirt/Brim', 6: 'Solid infill', 8: 'Internal infill', 9: 'Bridge infill', 7: 'Top solid infill', 5: 'Overhang perimeter', 10: 'Support material', -1: 'Custom'}



class Vector:

    @staticmethod
    def one(with_e = False):
        """Vector(1, 1, 1, 1)"""
        return Vector(1, 1, 1, 1 if with_e else 0)


    def __init__(self, X: float = 0, Y: float = 0, Z: float = 0, E: float = 0, F: float = 0):
        """Vector(0, 0, 0, 0)"""
        self.X = X
        self.Y = Y
        self.Z = Z
        self.E = E
        self.F = F


    def from_params(self, params: dict[str, str]):
        c = Coords(params)
        self.set_value(c.X, c.Y, c.Z, c.E, c.F)
        return self


    def vector_op(self, other: 'Vector', operation = lambda x, y: x + y):
        """
        Returns a new `Vector` object, does not affect `self` or `other`
        
        Args:
            `operation`: Callable
        """

        check_null_except(other, Vector, Exception, 'Can only operate on {0}, not {1}')

        X = operation(self.X, other.X)
        Y = operation(self.Y, other.Y)
        Z = operation(self.Z, other.Z)
        E = operation(self.E, other.E)
        F = operation(self.F, other.F)
        return Vector(X, Y, Z, E, F)


    def __add__(self, other: 'Vector') -> 'Vector':
        return self.vector_op(other, lambda x, y: x + y)


    def __sub__(self, other: 'Vector') -> 'Vector':
        return self.vector_op(other, lambda x, y: x - y)


    def __mul__(self, other: 'Vector|float') -> 'Vector':
        if not isinstance(other, Vector): other = Vector(other, other, other, other, other)
        return self.vector_op(other, lambda a,b: a * b)


    def __truediv__(self, other: 'Vector|float') -> 'Vector':
        if not isinstance(other, Vector): other = Vector(other, other, other, other, other)
        return self.vector_op(other, lambda a,b: a / b)


    def __neg__(self) -> 'Vector':
        return self.vector_op(Vector(), lambda x, y: y - x)


    def cross(self, other: 'Vector') -> 'Vector':
        return Vector(
            self.Y * other.Z - self.Z * other.Y,
            self.Z * other.X - self.X * other.Z,
            self.X * other.Y - self.Y * other.X
        )


    def dot(self, other: 'Vector') -> 'Vector':
        return self.X * other.X + self.Y * other.Y + self.Z * other.Z


    def normalized(self) -> 'Vector':
        len = float(self)
        if len == 0:
            return Vector()
        return self * (1.0 / len)


    def rotate(self, deg: int):
        """Rotate around Z axis with a given angle"""
        angle_rad = math.radians(deg)
        if not (self.X and self.Y): return self
        x = self.X * math.cos(angle_rad) - self.Y * math.sin(angle_rad)
        y = self.X * math.sin(angle_rad) + self.Y * math.cos(angle_rad)
        
        self.set_value(x, y)
        return self 


    def get_flowrate(self, config: Config, filament_offset = 0.0):
        """
        Returns flowrate (mm in E over mm in XYZ). Returns None if no XYZ movement
        
        Args:
            filament_offset: `float` - amount of filament already extruding or that's retracted
        """
        
        distance = float(self)
        if distance < config.step: return None
        return (self.E - filament_offset) / distance


    def set_flowrate(self, config: Config, flowrate: float):
        """Sets flowrate (mm in E over mm in XYZ). Returns None if no XYZ movement, otherwise returns E mm"""
        
        distance = float(self)
        if distance < config.step: return None
        flow = distance * flowrate
        self.E = flow
        return flow


    def duration(self):
        dist = float(self)
        if dist == 0: dist = abs(self.E)
        return dist * 60 / self.F


    def x(self) -> 'Vector':
        return Vector(X = self.X)


    def y(self) -> 'Vector':
        return Vector(Y = self.Y)


    def z(self) -> 'Vector':
        return Vector(Z = self.Z)


    def xy(self) -> 'Vector':
        return Vector(self.X, self.Y)


    def xyz(self) -> 'Vector':
        return Vector(self.X, self.Y, self.Z)


    def xyze(self) -> 'Vector':
        return Vector(self.X, self.Y, self.Z, self.E)


    def e(self) -> 'Vector':
        return Vector(E=self.E)


    def f(self) -> 'Vector':
        return Vector(F=self.F)


    def add_value(self, X = None, Y = None, Z = None, E = None, F = None):
        if X: self.X += X
        if Y: self.Y += Y
        if Z: self.Z += Z
        if E: self.E += E
        if F: self.F += F


    def set_value(self, X = None, Y = None, Z = None, E = None, F = None):
        if X: self.X = X
        if Y: self.Y = Y
        if Z: self.Z = Z
        if E: self.E = E
        if F: self.F = F


    def copy(self):
        """Create a deep copy"""
        return Vector(self.X, self.Y, self.Z, self.E, self.F)


    def __float__(self):
        """Returns the magnitude of `Vector`"""
        return math.sqrt(math.pow(self.X, 2) + math.pow(self.Y, 2) + math.pow(self.Z, 2))


    def __list__(self):
        return [ self.X, self.Y, self.Z, self.E, self.F ]


    def __str__(self):
        return f'X={self.X}, Y={self.Y}, Z={self.Z}, E={self.E}, F={self.F}'


    def to_dict(self):
        return {'X': self.X, 'Y': self.Y, 'Z': self.Z, 'E': self.E, 'F': self.F}


    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector): return False
        return self.to_dict() == other.to_dict()


    def __getitem__(self, key):
        data = [self.X, self.Y, self.Z, self.E, self.F]
        return data[key]


class CoordSystem:
    def __init__(self, abs_xyz = True, abs_e = True, arc_plane = Static.ARC_PLANES['XY'], position = Vector(), offset = Vector(), abs_position_e = 0.0):
        if position.F is None:
            print('Warning: speed parameter is unset! Defaultnig to 1200 mm/min')
            position.set_value(F=1200)
        
        self.abs_xyz = abs_xyz
        self.abs_e = abs_e
        self.arc_plane = arc_plane
        self.position = position
        self.offset = offset
        self.abs_position_e = abs_position_e

    def __str__(self):
        return dict_to_pretty_str(self.to_dict())


    def set_abs_xyz(self, abs_xyz=None):
        if abs_xyz is not None:
            self.abs_xyz = abs_xyz

    def set_abs_e(self, abs_e=None):
        if abs_e is not None:
            self.abs_e = abs_e
    
    def set_arc_plane(self, plane=None):
        if plane is not None:
            self.arc_plane = int(plane)


    def apply_move(self, params: dict[str, str]):
        c = Coords(params)

        self.position.set_value(F = c.F)
        
        if self.abs_xyz:
            if c.X: c.X += self.offset.X
            if c.Y: c.Y += self.offset.Y
            if c.Z: c.Z += self.offset.Z
            self.position.set_value(c.X, c.Y, c.Z)
        else:
            self.position.add_value(c.X, c.Y, c.Z)
        
        if self.abs_e:
            if c.E is not None:
                self.position.E = (c.E - self.abs_position_e)
                self.abs_position_e = c.E
            else:
                self.position.E = 0
        else:
            self.position.E = c.E or 0
        
        return self.position.copy()


    def set_offset(self, X = None, Y = None, Z = None, E = None):
        if X: self.offset.X = self.position.X - X
        if Y: self.offset.Y = self.position.Y - Y
        if Z: self.offset.Z = self.position.Z - Z
        if E: self.offset.E = self.position.E - E
        if self.abs_e:
            self.abs_position_e += self.offset.E


    def to_str(self, last_coords: 'CoordSystem|None' = None):
        """Returns gcode string of `CoordSystem`"""
        out = ''
        
        if isinstance(last_coords, CoordSystem):
            if last_coords.abs_xyz != self.abs_xyz:
                out += (Static.ABSOLUTE_COORDS_DESC if self.abs_xyz else Static.RELATIVE_COORDS_DESC) + '\n'
            if last_coords.abs_e != self.abs_e:
                out += (Static.ABSOLUTE_EXTRUDER_DESC if self.abs_e else Static.RELATIVE_EXTRUDER_DESC) + '\n'
            if last_coords.arc_plane != self.arc_plane:
                out += Static.ARC_PLANES_DESC[self.arc_plane] + '\n'
        
        else:
            out += (Static.ABSOLUTE_COORDS_DESC if self.abs_xyz else Static.RELATIVE_COORDS_DESC) + '\n'
            out += (Static.ABSOLUTE_EXTRUDER_DESC if self.abs_e else Static.RELATIVE_EXTRUDER_DESC) + '\n'
            out += Static.ARC_PLANES_DESC[self.arc_plane] + '\n'
        
        return out


    def to_dict(self):
        return {'abs_xyz' : self.abs_xyz, "abs_e" : self.abs_e, "position": self.position, "offset": self.offset}


    def copy(self):
        return CoordSystem(self.abs_xyz, self.abs_e, self.arc_plane, self.position.copy(), self.offset.copy(), self.abs_position_e)




class Arc:
    
    def __init__(self, position: Vector, dir = 0, ijk = Vector()):
        """
        Args:
            dir: `int` - 2=CW, 3=CCW
            move: `Move` - start position of the arc. End position is to be supplied in `subdivide()`
            ijk: `Vector` with respectful dimensions
        It is not possible to perform any operations on arc moves, only subdivision is possible
        """
        self.position = position
        self.dir = dir
        self.ijk = ijk.vector_op(Vector())


    def from_params(self, params: dict[str, str]):
        c = Coords(params)
        self.ijk.set_value(c.I, c.J, c.K)
        if params.get('R') is not None: raise NotImplementedError('"R" arc moves are not supported!')
        
        if params['0'] == 'G2': self.dir=2
        if params['0'] == 'G3': self.dir=3
        
        return self


    def subdivide(self, next: Vector, step: float) -> list[Vector]:
        
        center = self.ijk + self.position.xyz()
        radius = math.sqrt((self.ijk.X or 0)**2 + (self.ijk.Y or 0)**2)

        start_angle = math.atan2(-(self.ijk.Y or 0), -(self.ijk.X or 0))
        end_angle = math.atan2(next.Y - center.Y, next.X - center.X)

        if self.dir == 3:
            if end_angle < start_angle:
                end_angle += 2 * math.pi
        else:
            if end_angle > start_angle:
                end_angle -= 2 * math.pi

        total_angle = end_angle - start_angle
        total_angle_normal = abs(total_angle / (2 * math.pi))

        num_steps = max(math.ceil(min(max(8, (abs(total_angle) * radius / step)), 360 * total_angle_normal)), 1)

        vectors = []
        e = (next.E) / num_steps

        for i in range(num_steps):
            t = i / (num_steps - 1) if num_steps > 1 else 0
            angle = start_angle + t * total_angle
            x = center.X + radius * math.cos(angle)
            y = center.Y + radius * math.sin(angle)
            z = self.position.Z + t * (next.Z - self.position.Z)

            new_vector = Vector(x, y, z, e, self.position.F)
            vectors.append(new_vector)

        return vectors



class Block:
    
    def __init__(self, command: str | None = None, emit_command = True, config: Config = None, position=Vector(), e_temp=None, e_wait=None, bed_temp=None, bed_wait=None, fan=None, T=None, object=-1, move_type=None, layer=0):
        
        self.command = command
        self.emit_command = emit_command
        self.config = config
        self.e_temp = e_temp
        self.e_wait = e_wait
        self.bed_temp = bed_temp
        self.bed_wait = bed_wait
        self.fan = fan
        self.T = T
        self.object = object
        self.move_type = move_type
        self.layer = layer
        self.position = position


    def copy(self):
        return Block(self.command, self.emit_command, self.config, self.position.copy(), self.e_temp, self.e_wait, self.bed_temp, self.bed_wait, self.fan, self.T, self.object, self.move_type, self.layer)
