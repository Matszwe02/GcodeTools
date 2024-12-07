import math
import json



def float_nullable(input):
    if input is not None: return float(input)
    return input



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

    ARC_PLANES = {'G17': 17, 'G18' : 18, 'G19': 19, 'XY' : 17, 'XZ': 18, 'YZ': 19}

    FAN_SPEED = 'M106'
    FAN_OFF = 'M107'


    ABSOLUTE_COORDS_DESC = 'G90; Absolute Coordinates'
    RELATIVE_COORDS_DESC = 'G91; Relative Coordinates'
    ABSOLUTE_EXTRUDER_DESC = 'M82; Absolute Extruder'
    RELATIVE_EXTRUDER_DESC = 'M83; Relative Extruder'
    FAN_SPEED_DESC = 'M106 S{0}; Set Fan Speed'
    
    ARC_PLANES_DESC = {17: 'G17; Arc Plane XY', 18: 'G18; Arc Plane XZ', 19: 'G19; Arc Plane YZ'}



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


    def from_params(self, params: dict[str, str]):
        self.X = float_nullable(params.get('X', self.X))
        self.Y = float_nullable(params.get('Y', self.Y))
        self.Z = float_nullable(params.get('Z', self.Z))
        self.E = float_nullable(params.get('E', self.E))
        return self


    def vector_op(self, other, operation = lambda x, y: x + y, on_a_none: any = 'b', on_b_none: any = 'a', on_none = None):
        """
        Returns a new `Vector` object, does not affect `self` or `other`
        
        `operation`: lambda
        
        `on_a_none`, `on_b_none`: `any` to skip None checking ; `'a'`, `'b'`, `None`, `float` to return
        
        `on_none`: number|None
        """
        
        def nullable_op(a: float | None, b: float | None):
            if a is None and b is None: return on_none
            if a is None and on_a_none is not any:
                if on_a_none == 'a': return a
                if on_a_none == 'b': return b
                return on_a_none
            if b is None and on_b_none is not any:
                if on_b_none == 'a': return a
                if on_b_none == 'b': return b
                return on_b_none
            
            return operation(a, b)
        
        if type(other) is not Vector: raise TypeError(f'Invalid operation between Vector and {type(other)}')
        X = nullable_op(self.X, other.X)
        Y = nullable_op(self.Y, other.Y)
        Z = nullable_op(self.Z, other.Z)
        E = nullable_op(self.E, other.E)
        return Vector(X, Y, Z, E)


    def __add__(self, other):
        add = lambda x, y: x + y
        return self.vector_op(other, add)


    def __sub__(self, other):
        subtr = lambda x, y: x - y
        return self.vector_op(other, subtr)


    def __mul__(self, other):
        if not isinstance(other, Vector): other = Vector(other, other, other, other)
        scale = lambda a,b: a * b
        return self.vector_op(other, scale, on_a_none='a', on_b_none='a')


    def valid(self, other):
        """Return `Vector` with non-null dimensions from `other` vector"""
        valid = lambda a, b: a
        return self.vector_op(other, valid, on_a_none=None, on_b_none=None)


    def xyz(self):
        return Vector(X=self.X, Y=self.Y, Z=self.Z)


    def e(self):
        return Vector(E=self.E)


    def add(self, other):
        """Adds `Vector`'s dimensions to `other`'s that are not None"""
        if type(other) is not Vector: raise TypeError(f'You can only add Vector to Vector, not {type(other)}')
        add_op = lambda a, b: a + b
        new_vec = self.vector_op(other, add_op, None, 'a')
        self.set(new_vec)


    def set(self, other):
        """Sets `Vector`'s dimensions to `other`'s that are not None"""
        if type(other) is not Vector: raise TypeError(f'You can only set Vector to Vector, not {type(other)}')
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


    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector): return False
        return all(coord == coord2 for coord, coord2 in zip([self.X, self.Y, self.Z, self.E], [other.X, other.Y, other.Z, other.E]))



class CoordSystem:
    def __init__(self, abs_xyz = True, abs_e = True, speed = None, arc_plane = Static.ARC_PLANES['XY'], position = Vector.zero(), offset = Vector.zero(), fan = 0):
        if speed is None:
            print('Warning: speed parameter is unset! Defaultnig to 1200 mm/min')
            speed = 1200
        
        self.abs_xyz = abs_xyz
        self.abs_e = abs_e
        self.speed = speed
        self.arc_plane = arc_plane
        self.position = position
        self.offset = offset
        self.fan = fan


    def set_abs_xyz(self, abs_xyz=None):
        if abs_xyz is not None:
            self.abs_xyz = abs_xyz

    def set_abs_e(self, abs_e=None):
        if abs_e is not None:
            self.abs_e = abs_e
    
    def set_fan(self, fan):
        if fan is not None:
            self.fan = int(float(fan))
    
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
            self.position.set(pos.e() - self.position.e())
            self.position.add(self.offset.e().valid(pos))
        else:
            self.position.set(pos.e())
        
        return self.position.copy()


    def set_offset(self, pos: Vector):
        self.offset.set((self.position - pos).valid(pos))


    def to_str(self, last_coords = None):
        out = ''
        
        if type(last_coords) == CoordSystem:
            if last_coords.abs_xyz != self.abs_xyz:
                out = (Static.ABSOLUTE_COORDS_DESC if self.abs_xyz else Static.RELATIVE_COORDS_DESC) + '\n' + out
            if last_coords.abs_e != self.abs_e:
                out = (Static.ABSOLUTE_EXTRUDER_DESC if self.abs_e else Static.RELATIVE_EXTRUDER_DESC) + '\n' + out
            if last_coords.fan != self.fan:
                out = Static.FAN_SPEED_DESC.format(self.fan) + '\n' + out
            if last_coords.arc_plane != self.arc_plane:
                out = Static.ARC_PLANES_DESC[self.arc_plane] + '\n' + out
        
        else:
            out = (Static.ABSOLUTE_COORDS_DESC if self.abs_xyz else Static.RELATIVE_COORDS_DESC) + '\n' + out
            out = (Static.ABSOLUTE_EXTRUDER_DESC if self.abs_e else Static.RELATIVE_EXTRUDER_DESC) + '\n' + out
            out = Static.FAN_SPEED_DESC.format(self.fan) + '\n' + out
            out = Static.ARC_PLANES_DESC[self.arc_plane] + '\n' + out
        
        return out


    def to_dict(self):
        return {'abs_xyz' : self.abs_xyz, "abs_e" : self.abs_e, "speed" : self.speed, "position": self.position, "offset": self.offset, "fan": self.fan}


    def copy(self):
        return CoordSystem(self.abs_xyz, self.abs_e, self.speed, self.arc_plane, self.position.copy(), self.offset.copy(), self.fan)



class Move:

    def __init__(self, config = Config(), position = Vector(), speed: float|None = None):
        self.position = position.copy()
        """The end vector of Move"""
        self.speed = speed
        self.config = config


    def from_params(self, params: dict[str, str]):
        self.speed = float_nullable(params.get('F', self.speed))
        return self


    def translate(self, vec):
        self.position.add(vec)
        return self


    def rotate(self, deg: int):        
        angle_rad = math.radians(deg)
        
        x = self.position.X * math.cos(angle_rad) - self.position.Y * math.sin(angle_rad)
        y = self.position.X * math.sin(angle_rad) + self.position.Y * math.cos(angle_rad)
        
        self.position.set(Vector(x, y))
        return self 


    def scale(self, scale: int|Vector):
        self.position *= scale
        return self


    def distance(self, prev):
        if not isinstance(prev, Move): prev = Move(self.config)
        distance = lambda x, y: x - y
        return self.position.vector_op(prev.position, distance, on_a_none=0, on_b_none=0, on_none=0)


    def float_distance(self, distance: Vector):
        return math.sqrt(distance.X^2 + distance.Y^2 + distance.Z^2)


    def subdivide(self, prev, step = None) -> list[Vector]:
        if not isinstance(prev, Move): prev = Move(self.config)
        if step is None: step = self.config.step
        dist_pos = self.distance()
        dist = self.float_distance(dist_pos)
        pos_list = []
        if dist <= step: return [self]
        stop = round(dist / step)
        for i in range(stop):
            i_normal = i / stop
            pos_list.append(prev.position * (1 - i_normal) + self.position * i_normal)
        return pos_list


    def get_flowrate(self):
        """Returns flowrate (mm in E over mm in XYZ). Returns None if no XYZ movement"""
        dist_vec = self.distance()
        distance = self.float_distance(dist_vec)
        if distance < self.config.step: return None
        return dist_vec.e() / distance


    def set_flowrate(self, prev, flowrate: float):
        if not isinstance(prev, Move): prev = Move(self.config)
        """Sets flowrate (mm in E over mm in XYZ). Returns None if no XYZ movement, otherwise returns E mm"""
        dist_vec = self.distance()
        distance = self.float_distance(dist_vec)
        if distance < self.config.step: return None
        flow = distance * flowrate
        self.position.E = prev.position.E + flow
        return flow


    def to_str(self, prev):
        if not isinstance(prev, Move): prev = Move(self.config)
        nullable = lambda param, a: '' if a is None else f' {param}{round(a, self.config.precision)}'
        
        out = ''
        
        if self.position.X != prev.position.X: out += nullable('X', self.position.X)
        if self.position.Y != prev.position.Y: out += nullable('Y', self.position.Y)
        if self.position.Z != prev.position.Z: out += nullable('Z', self.position.Z)
        if self.position.E != 0: out += nullable('E', self.position.E)
        if self.speed != prev.speed: out += nullable('F', self.speed)
        
        if out != '': out = 'G1' + out
        
        return out


    def to_dict(self):
        return {'Pos' : self.position.to_dict()}


    def copy(self):
        """Create a deep copy"""
        return Move(self.config, self.position.copy(), self.speed)


    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Move): return False
        if self.position != other.position: return False
        if self.speed != other.speed: return False
        return True



class Arc:
    
    def __init__(self, move = Move(), dir = 0, ijk = Vector()):
        """
        `direction` 2=CW, 3=CCW
        
        `move` is the start position of the arc. End position is to be supplied in `subdivide`.
        
        It is not possible to perform any operations on arc moves, only subdivision is possible.
        """
        self.move = move
        self.dir = dir
        self.ijk = ijk.copy()


    def from_params(self, params: dict[str, str]):
        self.ijk.X = float_nullable(params.get('I', self.ijk.X))
        self.ijk.Y = float_nullable(params.get('J', self.ijk.Y))
        self.ijk.Z = float_nullable(params.get('K', self.ijk.Z))
        if params.get('R', None) is not None: raise NotImplementedError('"R" arc moves are not supported!')
        
        if params['0'] == 'G2': self.dir=2
        if params['0'] == 'G3': self.dir=3
        
        return self


    def subdivide(self, next: Move, step=None) -> list[Move]:
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

        num_steps = math.ceil(min(max(8, (abs(total_angle) * radius / step)), 360 * total_angle_normal))

        moves = []

        for i in range(num_steps):
            t = i / (num_steps - 1) if num_steps > 1 else 0
            angle = start_angle + t * total_angle
            x = center.X + radius * math.cos(angle)
            y = center.Y + radius * math.sin(angle)

            z = self.move.position.Z + t * (next.position.Z - self.move.position.Z)
            e = (next.position.E - self.move.position.E) / num_steps + self.move.position.E

            new_move = Move(self.move.config, Vector(x, y, z, e), self.move.speed)
            moves.append(new_move)

        return moves



class Block:
    
    def __init__(self, move: Move, command: str | None = None, emit_command = True, meta: dict = {}):
        
        self.move = move.copy()
        self.command = command
        self.emit_command = emit_command
        self.meta: dict = json.loads(json.dumps(meta))


    def copy(self):
        return Block(move = self.move.copy(), command=self.command, emit_command=self.emit_command, meta=self.meta.copy())


    def to_dict(self):
        return {
                'command': self.command,
                'move': self.move.__dict__,
                'emit_command': self.emit_command,
                'meta': self.meta
            }



class BlockList(list[Block]):
    
    def __init__(self):
        self.config = Config()
        """
        Configuration of the G-Code computation
        """
        super().__init__()


    def new(self):
        """
        Create an empty G-code list with self's config
        """
        new = BlockList()
        new.config = self.config
        return new


    def g_add(self, gcode: Block|str, index: int = -1, meta: list|None=None):
        """Appends gcode block to Gcode.\n\n`gcode`: Block or gcode str.\n\ndefault `index` -1: append to the end"""
        
        idx = index if index < len(self) else -1
        
        if type(gcode) == str:
            if len(self) == 0: move = Move()
            else:
                if idx > 0:
                    move = self[idx - 1].move
                elif idx == 0:
                    move = self[0].move
                else:
                    move = self[-1].move
            
            gcode_obj = Block(move.copy(), gcode, meta=meta)
        else:
            gcode_obj = gcode
        if idx == -1:
            self.append(gcode_obj)
            return
        self.insert(index, gcode_obj)


    # def to_dict(self):
    #     return [block.to_dict() for block in self]

