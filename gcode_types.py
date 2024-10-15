import math
import json



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



def float_nullable(input):
    if input is not None: return float(input)
    return input



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
        operation: lambda
        
        on_a_none, on_b_none: any to skip None checking ; 'a', 'b', None, float to return
        
        on_none: number|None
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
        """Return Vector with non-null dimensions from other Vector"""
        valid = lambda a, b: a
        return self.vector_op(other, valid, on_a_none=None, on_b_none=None)


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


    def apply_move(self, move):
        if type(move) is not Move or not move.position: return Vector()
        if self.abs_xyz:
            self.position.set(move.position.xyz())
            self.position.add(self.offset.xyz())
        else:
            self.position.add(move.position.xyz())
        
        if self.abs_e:
            self.position.set(move.position.e())
            self.position.add(self.offset.e())
        else:
            self.position.add(move.position.e())
        
        if move.speed is not None:
            self.speed = move.speed
        
        return self.position


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

    def __init__(self, coords: CoordSystem, config: Config, position = Vector(), speed: float|None = None):
        self.position = position.copy()
        """The end vector of Move"""
        self.coords = coords.copy()
        """Coords hold position, which is the beginning vector of Move"""
        self.speed = speed
        
        self.config = config


    def from_params(self, params: dict[str, str]):
        self.speed = float_nullable(params.get('F', self.speed))
        self.position.from_params(params)
        return self


    def distance(self):
        distance = lambda x, y: x - y
        return self.position.vector_op(self.coords.position, distance, on_a_none=0, on_b_none=0, on_none=0)


    def float_distance(self, distance: Vector):
        return math.sqrt(distance.X^2 + distance.Y^2 + distance.Z^2)


    def subdivide(self, step = None) -> list[Vector]:
        if step is None: step = self.config.step
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
        if distance < self.config.step: return None
        return dist_vec.e() / distance


    def set_flowrate(self, flowrate: float):
        """Sets flowrate (mm in E over mm in XYZ). Returns None if no XYZ movement, otherwise returns E mm"""
        dist_vec = self.distance()
        distance = self.float_distance(dist_vec)
        if distance < self.config.step: return None
        flow = distance * flowrate
        self.position.E = self.coords.position.E + flow
        return flow


    def to_str(self, last_move = None):
        nullable = lambda param, a, b: '' if a is None or b is None else f' {param}{round(a - b, self.config.precision)}'
        
        out = ''
        
        offset = Vector.zero()
        if not self.coords.abs_xyz:
            offset.set(self.coords.position.xyz())
        if not self.coords.abs_e:
            offset.set(self.coords.position.e())
        
        if self.position.X != self.coords.position.X: out += nullable('X', self.position.X, offset.X)
        if self.position.Y != self.coords.position.Y: out += nullable('Y', self.position.Y, offset.Y)
        if self.position.Z != self.coords.position.Z: out += nullable('Z', self.position.Z, offset.Z)
        if self.position.E != self.coords.position.E: out += nullable('E', self.position.E, offset.E)
        if self.speed is not None: out += nullable('F', self.speed, 0)
        
        if out != '': out = 'G1' + out
        coord_str = self.coords.to_str(last_move.coords if type(last_move) == Move else None)
        
        return coord_str + out


    def to_dict(self):
        return {'Current' : self.position.to_dict(), "Previous" : self.coords.position.to_dict()}


    def copy(self):
        """Create a deep copy"""
        return Move(self.coords.copy(), self.config, self.position.copy(), self.speed)



class Arc():
    def __init__(self, dir: int, move: Move, I: float|None = None, J: float|None = None, K: float|None = None):
        """direction 2=CW, 3=CCW"""
        self.dir = dir
        self.move = move
        self.I = I
        self.J = J
        self.K = K


    def from_params(self, params: dict[str, str]):
        self.I = float_nullable(params.get('I', self.I))
        self.J = float_nullable(params.get('J', self.J))
        self.K = float_nullable(params.get('K', self.K))
        if params.get('R', None) is not None: raise NotImplementedError('"R" arc moves are not supported!')
        
        if params['0'] == 'G2': self.dir=2
        if params['0'] == 'G3': self.dir=3
        
        self.move.from_params(params)
        return self


    def subdivide(self, step=None) -> list[Move]:
        if step is None: step = self.move.config.step
        
        center = Vector(self.I, self.J, self.K) + self.move.coords.position.xyz()
        radius = math.sqrt((self.I or 0)**2 + (self.J or 0)**2)

        start_angle = math.atan2(-(self.J or 0), -(self.I or 0))
        end_angle = math.atan2(self.move.position.Y - center.Y, self.move.position.X - center.X)

        if self.dir == 3:
            if end_angle < start_angle:
                end_angle += 2 * math.pi
        else:
            if end_angle > start_angle:
                end_angle -= 2 * math.pi

        total_angle = end_angle - start_angle

        num_steps = max(1, math.ceil(abs(total_angle) * radius / step))

        moves = []

        for i in range(num_steps):
            t = i / (num_steps - 1) if num_steps > 1 else 0
            angle = start_angle + t * total_angle
            x = center.X + radius * math.cos(angle)
            y = center.Y + radius * math.sin(angle)

            z = self.move.coords.position.Z + t * (self.move.position.Z - self.move.coords.position.Z)
            e = (self.move.position.E - self.move.coords.position.E) / num_steps + self.move.coords.position.E

            new_move = Move(
                coords=self.move.coords.copy(),
                position=Vector(x, y, z, e),
                speed=self.move.speed
            )
            moves.append(new_move)

        return moves


    def to_str(self, last_move = None):
        nullable = lambda param, a, b: '' if a is None or b is None else f' {param}{round(a - b, self.move.config.precision)}'
        
        out = ''
        
        offset = Vector.zero()
        if not self.move.coords.abs_xyz:
            offset.set(self.move.coords.position.xyz())
        if not self.move.coords.abs_e:
            offset.set(self.move.coords.position.e())
        
        if self.move.position.X != self.move.coords.position.X: out += nullable('X', self.move.position.X, offset.X)
        if self.move.position.Y != self.move.coords.position.Y: out += nullable('Y', self.move.position.Y, offset.Y)
        if self.move.position.Z != self.move.coords.position.Z: out += nullable('Z', self.move.position.Z, offset.Z)
        if self.move.position.E != self.move.coords.position.E: out += nullable('E', self.move.position.E, offset.E)
        out += nullable('I', self.I, 0)
        out += nullable('J', self.J, 0)
        out += nullable('K', self.K, 0)
        if self.move.speed is not None: out += nullable('F', self.move.speed, 0)
        
        if out != '': out = f'G{self.dir}' + out
        coord_str = self.move.coords.to_str(last_move.coords if type(last_move) == Move else None)
        
        return coord_str + out


    def to_dict(self):
        return {'I': self.I, 'J': self.J, 'K': self.K, 'dir': self.dir, 'move': self.move.to_dict()}


    def copy(self):
        """Create a deep copy of this Arc instance."""
        return Arc(I=self.I, J=self.J, K=self.K, dir=self.dir, move=self.move.copy())



class Block:
    
    def __init__(self, move: Move|Arc, command: str | None = None, emit_command = True, meta: dict = {}):
        
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


    def g_add(self, gcode: Block|str, index: int = -1):
        """Appends gcode block to Gcode.\n\ngcode: Block or gcode str.\n\ndefault index -1: append to the end"""
        
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
            
            gcode_obj = Block(move.copy(), gcode)
        else:
            gcode_obj = gcode
        if idx == -1:
            self.append(gcode_obj)
            return
        self.insert(index, gcode_obj)


    # def to_dict(self):
    #     return [block.to_dict() for block in self]

