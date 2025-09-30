import math
import json
import typing


def float_nullable(input):
    if input is not None: return float(input)
    return input


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



class Vector:

    @staticmethod
    def zero():
        """Vector(0, 0, 0, 0)"""
        return Vector(0, 0, 0, 0)

    @staticmethod
    def one(with_e = False):
        """Vector(0, 0, 0, 0)"""
        return Vector(1, 1, 1, 1 if with_e else None)


    def __init__(self, X: float | None = None, Y: float | None = None, Z: float | None = None, E: float | None = None):
        """Vector(None, None, None, None)"""
        self.X = X
        self.Y = Y
        self.Z = Z
        self.E = E


    def from_params(self, params: dict[str, str]):
        self.X = float_nullable(params.get('X', self.X))
        self.Y = float_nullable(params.get('Y', self.Y))
        self.Z = float_nullable(params.get('Z', self.Z))
        self.E = float_nullable(params.get('E', self.E))
        return self


    def vector_op(self, other: 'Vector', operation = lambda x, y: x + y, on_a_none: str|float|None = 'b', on_b_none: str|float|None = 'a', on_none: float|None = None):
        """
        Returns a new `Vector` object, does not affect `self` or `other`
        
        Args:
            `operation`: lambda
            `on_a_none`, `on_b_none`: `''` to skip None checking ; `'a'`, `'b'`, `None`, `float` to return that value
            `on_none`: float|None if both `a` and `b` are none
        """
        
        def nullable_op(a: float | None, b: float | None):
            if a is None and b is None: return on_none
            if a is None and on_a_none != '':
                if on_a_none == 'a': return a
                if on_a_none == 'b': return b
                return on_a_none
            if b is None and on_b_none != '':
                if on_b_none == 'a': return a
                if on_b_none == 'b': return b
                return on_b_none
            
            return operation(a, b)
        
        check_null_except(other, Vector, Exception, 'Can only operate on {0}, not {1}')
        
        X = nullable_op(self.X, other.X)
        Y = nullable_op(self.Y, other.Y)
        Z = nullable_op(self.Z, other.Z)
        E = nullable_op(self.E, other.E)
        return Vector(X, Y, Z, E)


    def __add__(self, other: 'Vector') -> 'Vector':
        add = lambda x, y: x + y
        return self.vector_op(other, add)


    def __sub__(self, other: 'Vector') -> 'Vector':
        subtr = lambda x, y: x - y
        return self.vector_op(other, subtr)


    def __mul__(self, other: 'Vector|float') -> 'Vector':
        if not isinstance(other, Vector): other = Vector(other, other, other, other)
        scale = lambda a,b: a * b
        return self.vector_op(other, scale, on_a_none='a', on_b_none='a')


    def __truediv__(self, other: 'Vector|float') -> 'Vector':
        if not isinstance(other, Vector): other = Vector(other, other, other, other)
        scale = lambda a,b: a / b
        return self.vector_op(other, scale, on_a_none='a', on_b_none='a')


    def __neg__(self) -> 'Vector':
        subtr = lambda x, y: y - x
        return self.vector_op(Vector.zero(), subtr, on_a_none=None)


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
    

    def valid(self, other: 'Vector') -> 'Vector':
        """Return `Vector` with non-null dimensions from `other` vector"""
        valid = lambda a, b: a
        return self.vector_op(other, valid, on_a_none=None, on_b_none=None)


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


    def e(self) -> 'Vector':
        return Vector(E=self.E)


    def add(self, other: 'Vector'):
        """Adds `Vector`'s dimensions to `other`'s that are not None"""
        check_null_except(other, Vector, Exception, 'Can only add {0} to {0}, not {1}')
        add_op = lambda a, b: a + b
        new_vec = self.vector_op(other, add_op, None, 'a')
        self.set(new_vec)


    def set(self, other: 'Vector'):
        """Sets `Vector`'s dimensions to `other`'s that are not None"""
        check_null_except(other, Vector, Exception, 'Can only set {0} to {0}, not {1}')
        if other.X is not None: self.X = other.X
        if other.Y is not None: self.Y = other.Y
        if other.Z is not None: self.Z = other.Z
        if other.E is not None: self.E = other.E


    def copy(self):
        """Create a deep copy"""
        return Vector(self.X, self.Y, self.Z, self.E)


    def __str__(self):
        if self.E is None:
            if self.Z is None:
                if self.Y is None and self.X is None:
                    return f'XYZE={None}'
                return f'X={self.X}, Y={self.Y}'
            return f'X={self.X}, Y={self.Y}, Z={self.Z}'
        return f'X={self.X}, Y={self.Y}, Z={self.Z}, E={self.E}'


    def is_none(self, with_e = True):
        """Returns `True` when any of `Vector`'s coordinates is `None`"""
        if with_e:
            return any(coord is None for coord in [self.X, self.Y, self.Z, self.E])
        return any(coord is None for coord in [self.X, self.Y, self.Z])


    def to_dict(self):
        return {'X': self.X, 'Y': self.Y, 'Z': self.Z, 'E': self.E}


    def __bool__(self):
        return any(coord is not None for coord in [self.X, self.Y, self.Z, self.E])


    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector): return False
        return all(coord == coord2 for coord, coord2 in zip([self.X, self.Y, self.Z, self.E or 0], [other.X, other.Y, other.Z, other.E or 0]))

    def to_list(self, with_e = True):
        """Returns the vector as a list [X, Y, Z] or [X, Y, Z, E], defaulting None to 0.0"""
        if with_e:
            return [ self.X or 0.0, self.Y or 0.0, self.Z or 0.0, self.E or 0.0 ]
        return [ self.X or 0.0, self.Y or 0.0, self.Z or 0.0 ]

    def __float__(self):
        """Returns the magnitude of `Vector`"""
        x = self.X or 0.0
        y = self.Y or 0.0
        z = self.Z or 0.0
        return math.sqrt(x**2 + y**2 + z**2)

    def __getitem__(self, key):
        data = [self.X, self.Y, self.Z, self.E]
        return data[key]


class CoordSystem:
    def __init__(self, abs_xyz = True, abs_e = True, speed = None, arc_plane = Static.ARC_PLANES['XY'], position = Vector(), offset = Vector.zero(), abs_position_e = 0.0):
        if speed is None:
            print('Warning: speed parameter is unset! Defaultnig to 1200 mm/min')
            speed = 1200
        
        self.abs_xyz = abs_xyz
        self.abs_e = abs_e
        self.speed = speed
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
        self.speed = float_nullable(params.get('F', self.speed))
        pos = Vector().from_params(params)
        
        if self.abs_xyz:
            self.position.set(pos.xyz())
            self.position.add(self.offset.xyz().valid(pos))
        else:
            self.position.add(pos.xyz())
        
        if self.abs_e:
            if pos.E is not None:
                self.position.E = (pos.E - self.abs_position_e)
                self.abs_position_e = pos.E
            else:
                self.position.E = 0
        else:
            self.position.E = pos.E or 0
        
        return self.position.copy()


    def set_offset(self, pos: Vector):
        self.offset.set((self.position - pos).valid(pos))
        if self.abs_e:
            self.abs_position_e += (self.offset.E or 0)


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
        return {'abs_xyz' : self.abs_xyz, "abs_e" : self.abs_e, "speed" : self.speed, "position": self.position, "offset": self.offset}


    def copy(self):
        return CoordSystem(self.abs_xyz, self.abs_e, self.speed, self.arc_plane, self.position.copy(), self.offset.copy(), self.abs_position_e)



class Move:

    def __init__(self, block_ref:'Block|None' = None, config = Config(), position = Vector(), speed: float|None = None):
        
        self.block_ref = block_ref
        self.position = position.copy()
        """The end vector of Move\n\n`XYZ` is always absolute\n\n`E` is always relative\n\nEvery logic is performend regarding to that"""
        self.speed = speed
        self.config = config
        self.origin = Vector()


    def duplicate(self):
        """
        Use in consecutive `Block`. Used to duplicate `Block`
        """
        move = self.copy()
        move.position.E = 0
        return move


    def from_params(self, params: dict[str, str]):
        self.speed = float_nullable(params.get('F', self.speed))
        return self


    def translate(self, vec: Vector):
        """
        Translates `Move` with `Vector`\n
        `Gcode.order()` will add travel moves for these translations\n
        Use `Gcode.unlink()` to cancel travel move generation on `order`
        """
        self.position.add(vec)
        self.origin.add(vec.xyz())
        return self


    def rotate(self, deg: int):        
        angle_rad = math.radians(deg)
        if not (self.position.X and self.position.Y): return self
        x = self.position.X * math.cos(angle_rad) - self.position.Y * math.sin(angle_rad)
        y = self.position.X * math.sin(angle_rad) + self.position.Y * math.cos(angle_rad)
        
        self.position.set(Vector(x, y))
        return self 


    def scale(self, scale: int|Vector):
        self.position *= scale
        return self


    def distance(self):
        prev = self.get_prev()
        
        distance = lambda x, y: x - y
        return self.position.vector_op(prev.position, distance, on_a_none=0, on_b_none=0, on_none=0)


    def float_distance(self, distance: Vector|None = None):
        """
        Float distance of current move or between self and a Vector
        """
        
        if isinstance(distance, Vector):
            return math.sqrt(math.pow(distance.X or 0, 2) + math.pow(distance.Y or 0, 2) + math.pow(distance.Z or 0, 2))
        
        return self.float_distance(distance = self.distance())


    def subdivide(self, step = None) -> list[Vector]:
        prev = self.get_prev()
        step = step or self.config.step
        
        dist = self.float_distance()
        pos_list = []
        if dist <= step: return [self]
        stop = round(dist / step)
        for i in range(stop):
            i_normal = i / stop
            pos_list.append(prev.position * (1 - i_normal) + self.position * i_normal)
        return pos_list


    def get_flowrate(self, filament_offset = 0.0):
        """
        Returns flowrate (mm in E over mm in XYZ). Returns None if no XYZ movement
        
        Args:
            filament_offset: `float` - amount of filament already extruding or that's retracted
        """
        
        distance = self.float_distance()
        if distance < self.config.step: return None
        return (self.position.E - filament_offset) / distance


    def set_flowrate(self, flowrate: float):
        """Sets flowrate (mm in E over mm in XYZ). Returns None if no XYZ movement, otherwise returns E mm"""
        
        distance = self.float_distance()
        if distance < self.config.step: return None
        flow = distance * flowrate
        self.position.E = flow
        return flow


    def duration(self):
        dist = self.float_distance()
        if dist == 0: dist = abs(self.position.E or 0)
        return dist * 60 / (self.speed or self.config.speed)


    def get_prev(self) -> 'Move':
        return getattr(getattr(self.block_ref, 'prev', None), 'move', Move())


    def update_origin(self):
        self.origin = self.get_prev().position.xyz()


    def to_str(self):
        """Returns gcode string of `Move`"""
        
        prev = self.get_prev()
        nullable = lambda param, a: '' if a is None else f' {param}{a:.{self.config.precision}f}'.rstrip('0').rstrip('.')
        
        out = ''
        
        if self.position.X != self.origin.X: out += nullable('X', self.position.X)
        if self.position.Y != self.origin.Y: out += nullable('Y', self.position.Y)
        if self.position.Z != self.origin.Z: out += nullable('Z', self.position.Z)
        if self.position.E != 0: out += nullable('E', self.position.E)
        if self.speed != prev.speed: out += nullable('F', self.speed)
        
        if out != '': out = 'G1' + out + '\n'
        
        if self.position != Vector() and self.origin == Vector(): out = Static.HOME_DESC + '\n' + out
        
        return out


    def to_dict(self):
        return {'Pos' : self.position.to_dict(), 'Speed' : self.speed}


    def copy(self):
        """Create a deep copy"""
        return Move(None, self.config, self.position.copy(), self.speed)

    def __str__(self):
        return dict_to_pretty_str(self.to_dict())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Move): return False
        if self.position != other.position: return False
        if self.speed != other.speed: return False
        return True



class Arc:
    
    def __init__(self, move = Move(), dir = 0, ijk = Vector()):
        """
        Args:
            dir: `int` - 2=CW, 3=CCW
            move: `Move` - start position of the arc. End position is to be supplied in `subdivide()`
            ijk: `Vector` with respectful dimensions
        It is not possible to perform any operations on arc moves, only subdivision is possible
        """
        self.move = move
        self.dir = dir
        self.ijk = ijk.vector_op(Vector.zero(), on_a_none='b')


    def from_params(self, params: dict[str, str]):
        self.ijk.X = float_nullable(params.get('I', self.ijk.X))
        self.ijk.Y = float_nullable(params.get('J', self.ijk.Y))
        self.ijk.Z = float_nullable(params.get('K', self.ijk.Z))
        if params.get('R', None) is not None: raise NotImplementedError('"R" arc moves are not supported!')
        
        if params['0'] == 'G2': self.dir=2
        if params['0'] == 'G3': self.dir=3
        
        return self


    def subdivide(self, next: Move, step: float|None=None) -> list[Move]:
        if step is None: step = self.move.config.step
        
        center = self.ijk + self.move.position.xyz()
        radius = math.sqrt((self.ijk.X or 0)**2 + (self.ijk.Y or 0)**2)

        start_angle = math.atan2(-(self.ijk.Y or 0), -(self.ijk.X or 0))
        end_angle = math.atan2(next.position.Y - center.Y, next.position.X - center.X)

        if self.dir == 3:
            if end_angle < start_angle:
                end_angle += 2 * math.pi
        else:
            if end_angle > start_angle:
                end_angle -= 2 * math.pi

        total_angle = end_angle - start_angle
        total_angle_normal = abs(total_angle / (2 * math.pi))

        num_steps = max(math.ceil(min(max(8, (abs(total_angle) * radius / step)), 360 * total_angle_normal)), 1)

        moves = []
        e = (next.position.E) / num_steps

        for i in range(num_steps):
            t = i / (num_steps - 1) if num_steps > 1 else 0
            angle = start_angle + t * total_angle
            x = center.X + radius * math.cos(angle)
            y = center.Y + radius * math.sin(angle)

            if next.position.Z is None:
                z = None
            elif self.move.position.Z is None:
                z = next.position.Z
            else:
                z = self.move.position.Z + t * (next.position.Z - self.move.position.Z)

            new_move = Move(None, self.move.config, Vector(x, y, z, e), self.move.speed)
            moves.append(new_move)

        return moves



class BlockData:

    @staticmethod
    def zero():
        return BlockData(None, 0, False, 0, False, 0, 0)


    def __init__(self, block_ref: 'Block|None' = None, e_temp=None, e_wait=None, bed_temp=None, bed_wait=None, fan=None, T=None):
        
        self.block_ref = block_ref
        self.e_temp = e_temp
        self.e_wait = e_wait
        self.bed_temp = bed_temp
        self.bed_wait = bed_wait
        self.fan = fan
        self.T = T
    
    
    def set_fan(self, fan: int):
        """
        Set fan with index to desired speed.
        
        Args:
            fan: `int` - speed in range 0..255
        """
        
        if type(fan) == int and fan in range(256):
            self.fan = fan


    def set_e_temp(self, temp: int, wait=False):
        if temp is not None:
            self.e_temp = temp
        self.e_wait = wait


    def set_bed_temp(self, temp: int, wait=False):
        if temp is not None:
            self.bed_temp = temp
        self.bed_wait = wait


    def clear_wait(self):
        self.e_wait = False
        self.bed_wait = False


    def set_tool(self, tool: int):
        if tool is not None and tool in range(10):
            self.T = tool


    def get_prev(self) -> 'BlockData':
        return getattr(getattr(self.block_ref, 'prev', None), 'block_data', BlockData())


    def to_str(self):
        """Returns gcode string of `BlockData`"""
        prev = self.get_prev()
        
        out = ''
        if self.e_temp != prev.e_temp and self.e_temp is not None:
            out += f'{Static.E_TEMP_DESC.format(self.e_temp)}\n'
        if self.bed_temp != prev.bed_temp and self.bed_temp is not None:
            out += f'{Static.BED_TEMP_DESC.format(self.bed_temp)}\n'
        
        if self.e_temp != prev.e_temp and self.e_temp is not None and self.e_wait:
            out += f'{Static.E_TEMP_WAIT_DESC.format(self.e_temp)}\n'
        if self.bed_temp != prev.bed_temp and self.bed_temp is not None and self.bed_wait:
            out += f'{Static.BED_TEMP_WAIT_DESC.format(self.bed_temp)}\n'
        
        if self.fan != prev.fan and self.fan is not None:
            out += f'{Static.FAN_SPEED_DESC.format(self.fan)}\n'
        if self.T != prev.T and self.T is not None:
            out += f'{Static.TOOL_CHANGE_DESC.format(self.T)}\n'
        
        return out


    def to_dict(self):
        return {
                'e_temp': self.e_temp,
                'bed_temp': self.bed_temp,
                'fan': self.fan,
                'T': self.T
            }


    def copy(self):
        return BlockData(self.block_ref, self.e_temp, self.e_wait, self.bed_temp, self.bed_wait, self.fan, self.T)

    def __str__(self):
        return dict_to_pretty_str(self.to_dict())



class Block:
    
    def __init__(self, prev:'Block|None' = None, move: Move = Move(), command: str | None = None, emit_command = True, block_data = BlockData(), meta: dict = {}):
        
        self.prev = prev
        self.move = move.copy()
        self.command = command
        self.emit_command = emit_command
        self.block_data = block_data.copy()
        self.meta: dict = json.loads(json.dumps(meta))


    def as_origin(self):
        """
        Treat as origin to the next `Block`
        
        Used to ensure that move path is deterministic, when splitting `Gcode`
        """
        new = Block(None, self.move.copy(), block_data=self.block_data.copy(), meta=self.meta)
        new.move.position.E = 0
        new.move.speed = 0
        return new
    

    def sync(self):
        """
        Sync objects inside `Block` to refer to it
        """
        self.move.block_ref = self
        self.block_data.block_ref = self
        self.move.update_origin()
        return self


    def unlink(self):
        """
        Inverse of `sync`. Used to make object serializable
        """
        self.move.block_ref = None
        self.move.origin = Vector()
        self.block_data.block_ref = None
        self.prev = None
        return self


    def to_dict(self):
        return {
                'command': self.command,
                'move': self.move.to_dict(),
                'emit_command': self.emit_command,
                'data': self.block_data.to_dict(),
                'meta': self.meta
            }


    def to_str(self, verbose=False):
        """Returns gcode string of `Block`"""
        
        line_str = ''
        
        line_str += self.block_data.to_str()
        line_str += self.move.to_str()
        
        if self.emit_command and self.command:
            line_str += self.command + '\n'
        
        if line_str != '':
            if verbose:
                line_str += '; '
                if self.meta is not None and self.meta != {}:
                    line_str += remove_chars(json.dumps(self.meta), '{} "').replace(",", " ") + ', '
                line_str += remove_chars(json.dumps(self.block_data.to_dict()), '{} \"').replace(",", " ")
                line_str += f', duration:{self.move.duration():.3f}s\n'
        
        return line_str


    def copy(self):
        return Block(self.prev, self.move, self.command, self.emit_command, self.block_data, self.meta)

    def __str__(self):
        return dict_to_pretty_str(self.to_dict())
