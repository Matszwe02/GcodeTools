import os
# import numpy as np
import re
import json
import time
import math


DEBUG_GCODE_LINES = True

ABSOLUTE_COORDS = 'G90'
RELATIVE_COORDS = 'G91'

ABSOLUTE_EXTRUDER = 'M82'
RELATIVE_EXTRUDER = 'M83'

SET_POSITION = 'G92'

ARC_PLANE_XY = 'G17'
ARC_PLANE_XZ = 'G18'
ARC_PLANE_YZ = 'G19'

TRIM_GCODES = ['M73', 'EXCLUDE_OBJECT_DEFINE', 'EXCLUDE_OBJECT_START', 'EXCLUDE_OBJECT_END']



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
    
    def nullable_add(a: float | None, b: float | None) -> float | None:
        if a is None: return b
        if b is None: return a
        return a + b
    
    def nullable_subtr(a: float | None, b: float | None) -> float | None:
        if a is None: return b
        if b is None: return a
        return a - b
    
    def zeroable_add(a: float | None, b: float | None) -> float:
        if a is None and b is None: return 0
        if a is None: return b
        if b is None: return a
        return a + b
    
    def zeroable_subtr(a: float | None, b: float | None) -> float:
        if a is None and b is None: return 0
        if a is None: return b
        if b is None: return a
        return a - b
    
    def oneable_mul(a: float | None, b: float | None) -> float | None:
        if a is None or b is None: return a
        return a * b
    
    def __add__(self, other):
        X = self.nullable_add(self.X, other.X)
        Y = self.nullable_add(self.Y, other.Y)
        Z = self.nullable_add(self.Z, other.Z)
        E = self.nullable_add(self.E, other.E)
        F = self.nullable_add(self.F, other.F)
        return Position(X, Y, Z, E, F)

    def __sub__(self, other):
        X = self.nullable_subtr(self.X, other.X)
        Y = self.nullable_subtr(self.Y, other.Y)
        Z = self.nullable_subtr(self.Z, other.Z)
        E = self.nullable_subtr(self.E, other.E)
        F = self.nullable_subtr(self.F, other.F)
        return Position(X, Y, Z, E, F)
    
    def __mul__(self, other):
        if not isinstance(other, Position): other = Position(other, other, other, other, other)
        X = self.oneable_mul(self.X, other.X)
        Y = self.oneable_mul(self.Y, other.Y)
        Z = self.oneable_mul(self.Z, other.Z)
        E = self.oneable_mul(self.E, other.E)
        F = self.oneable_mul(self.F, other.F)
        return Position(X, Y, Z, E, F)

    def valid(self, other):
        """Return Vector of self, with valid dimensions from other"""
        X = self.X if other.X is not None else None
        Y = self.Y if other.Y is not None else None
        Z = self.Z if other.Z is not None else None
        E = self.E if other.E is not None else None
        F = self.F if other.F is not None else None
        return Position(X, Y, Z, E, F)
    
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
        X = self.zeroable_subtr(self.X, other.X)
        Y = self.zeroable_subtr(self.Y, other.Y)
        Z = self.zeroable_subtr(self.Z, other.Z)
        E = self.zeroable_subtr(self.E, other.E)
        return X, Y, Z, E
    
    def combined_distance(self, other):
        X, Y, Z, E = self.distance(other)
        return X, Y, Z, E, math.sqrt(X^2 + Y^2 + Z^2)
    
    def subdivide(self, next, step = 0.1):
        dist_x, dist_y, dist_z, dist_e, dist = self.combined_distance(next)
        pos_list = []
        if dist <= step: return [self]
        
        for i in range(dist // step):
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



class Gcode:
    
    def __init__(self, gcode_str: str = ""):
        
        self.gcode = ''
        self.coord_system = CoordSystem()
        self.gcode_blocks:list[GcodeBlock] = []
        
        if gcode_str != "":
            self.read_gcode(gcode_str)



    def read_gcode(self, gcode_str):
        
        self.gcode = gcode_str
        self.generate_moves()



    def line_to_dict(self, line):
        params = ['', []]
        line_parts = line.split(';')[0].split(' ')  
        if line_parts:
            params[0] = line_parts[0]

            for param in line_parts[1:]:
                
                if not param: continue
                params[1].append(param)
        
        return params


    def line_to_position(self, line):
        
        X, Y, Z, E, F = None, None, None, None, None
        
        for param in line[1]:
            if param[0] == 'X': X = float(param[1:])
            if param[0] == 'Y': Y = float(param[1:])
            if param[0] == 'Z': Z = float(param[1:])
            if param[0] == 'E': E = float(param[1:])
            if param[0] == 'F': F = float(param[1:])
        
        return Position(X, Y, Z, E, F)
    
    
    def line_to_arc(self, line):
        
        I, J, K, dir = None, None, None, 0
        
        for param in line[1]:
            if param[0] == 'I': I = float(param[1:])
            if param[0] == 'J': J = float(param[1:])
            if param[0] == 'K': K = float(param[1:])
        
        if line[0] == 'G2': dir=2
        if line[0] == 'G3': dir=3
        
        return Arc(I, J, K, dir=dir)


    def generate_moves(self):
        
        self.coord_system = CoordSystem()
        self.gcode_blocks:list[GcodeBlock] = []
        # blocks.append(GcodeBlock(Position(0, 0, 0, 0, 600), Position(0, 0, 0, 0)))
        # self.coord_system.apply_position(Position(0, 0, 0, 0, 600))
        
        meta = {'object': None, 'type': None, 'line_no': 0}
        
        for id, line in enumerate(filter(str.strip, self.gcode.split('\n'))):
            meta['line_no'] = id
            command = None
            arc = None
            line_skipped = False
            
            line_dict = self.line_to_dict(line)
            raw_pos = Position()
            
            if line[0] == ';':
                if line.startswith('; printing object'):
                    meta['object'] = line.removeprefix('; printing object').strip().replace(' ', '_')
                if line.startswith('; stop printing'):
                    meta['object'] = None
                if line.startswith(';TYPE:'):
                    meta['type'] = line.removeprefix(';TYPE:').strip().replace(' ', '_')
                if line == ';WIPE_START':
                    meta['type'] = 'Wipe'
                if line == ';WIPE_END':
                    meta['type'] = None
            
            if line_dict[0] in ['G1', 'G0']:
                raw_pos = self.line_to_position(line_dict)
            
            elif line_dict[0] in ['G2', 'G3']:
                arc = self.line_to_arc(line_dict)
                arc.plane = self.coord_system.arc_plane
                raw_pos = self.line_to_position(line_dict)
            
            elif line_dict[0] == ABSOLUTE_COORDS:
                self.coord_system.set_coords(True)
            elif line_dict[0] == RELATIVE_COORDS:
                self.coord_system.set_coords(False)

            elif line_dict[0] == ABSOLUTE_EXTRUDER:
                self.coord_system.set_extruder(True)
            elif line_dict[0] == RELATIVE_EXTRUDER:
                self.coord_system.set_extruder(False)
            
            elif line_dict[0] == SET_POSITION:
                raw_pos = self.line_to_position(line_dict).copy()
                self.coord_system.set_offset(raw_pos)
            
            elif line_dict[0] == ARC_PLANE_XY:
                self.coord_system.arc_plane = 17
            elif line_dict[0] == ARC_PLANE_XZ:
                self.coord_system.arc_plane = 18
            elif line_dict[0] == ARC_PLANE_YZ:
                self.coord_system.arc_plane = 19
            
            elif line_dict[0] in TRIM_GCODES:
                pass
            
            else:
                command = line.strip()
                line_skipped = True
            
            if DEBUG_GCODE_LINES and not line_skipped:
                command = '; CMD: ' + line.strip()
            
            new_pos = self.coord_system.apply_position(raw_pos)
            gcode_block = GcodeBlock(new_pos, self.coord_system.offset, arc=arc, command=command, meta=meta)
            
            self.gcode_blocks.append(gcode_block)
        
        self.gcode_blocks.append(GcodeBlock(Position(), Position(), command=command, meta=meta))



class GcodeTools:
    
    def __init__(self, gcode: list[GcodeBlock] | str = None):
        self.gcode = None
        
        self.start_gcode = None
        self.end_gcode = None
        self.object_gcode = None
        
        if type(gcode) == str:
            self.gcode = Gcode(gcode).gcode_blocks
        elif type(gcode) == list[GcodeBlock]:
            self.gcode = gcode
        
        self.precision = 0.02



    def read_metadata(self):
        self.metadata = {}
        start_id, end_id = -1, -1
        for id, block in enumerate(self.gcode):
            if block.command == "; CONFIG_BLOCK_START":
                start_id = id
            if block.command == "; CONFIG_BLOCK_END":
                end_id = id
                
        for gcode in self.gcode[start_id + 1 : end_id]:
            line = gcode.command
            key = line[1:line.find('=')].strip()
            value = line[line.find('=') + 1:].strip()
            self.metadata[key] = value
        return self.metadata



    def split(self):
        gcode = self.gcode
        object_gcode = []
        start_gcode = []
        end_gcode = []
        layers = []
        objects_layers = {}
        
        start_id, end_id = -1, -1
        
        for id, block in enumerate(gcode):
            if block.command == "; EXECUTABLE_BLOCK_START":
                start_id = id + 1
            if block.command == "; EXECUTABLE_BLOCK_END":
                end_id = id
            if start_id > 0 and end_id > 0:
                gcode = gcode[start_id:end_id]
                break
        
        start_id, end_id = -1, -1
        for id, block in enumerate(gcode):
            if ";WIDTH:" in block.command and start_id == -1:
                start_id = id + 1
            if block.command == "; filament end gcode":
                end_id = id
            if start_id > 0 and end_id > 0:
                object_gcode = gcode[start_id:end_id]
                
            
        start_id, end_id = -1, -1
        for id, block in enumerate(gcode):
            if block.command == "; filament end gcode":
                end_id = id
            if block.command == "; Filament gcode":
                start_id = id + 1
            if start_id > 0 and end_id > 0:
                start_gcode = gcode[:start_id]
                end_gcode = gcode[end_id:]
            
                
        layer = []
        objects_layer = {}
        for block in object_gcode:
            if block.command == ";BEFORE_LAYER_CHANGE":
                layers.append(layer)
                # objects_layers.append(objects_layer)
                
                for id in objects_layer.keys():
                    if id not in objects_layers:
                        objects_layers[id] = []
                    objects_layers[id].append(objects_layer[id])
                
            elif block.command == ";AFTER_LAYER_CHANGE":
                layer = []
                objects_layer = {}
            else:
                layer.append(block)
                
                objects_key = block.meta['object'] or 'Travel'
                if objects_key not in objects_layer:
                    objects_layer[objects_key] = []
                objects_layer[objects_key].append(block)
        
        
        layers.append(layer)
        
        self.start_gcode = start_gcode
        self.end_gcode = end_gcode
        self.layers = layers
        self.objects_layers = objects_layers



    def log_json(self, path='.'):
        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, 'to_dict'):
                    return obj.to_dict()
                return super().default(obj)

        with open(os.path.join(path, 'gcode.json'), 'w') as f:
            f.write(json.dumps(self.gcode, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'objects_layers.json'), 'w') as f:
            f.write(json.dumps(self.objects_layers, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'start_gcode.json'), 'w') as f:
            f.write(json.dumps(self.start_gcode, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'end_gcode.json'), 'w') as f:
            f.write(json.dumps(self.end_gcode, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'metadata.json'), 'w') as f:
            f.write(json.dumps(self.metadata, indent=4))



def main():

    with open('cube.gcode', 'r') as f:
        gcode_file = f.read()
    tools = GcodeTools(gcode_file)
    tools.read_metadata()
    tools.split()
    tools.log_json()



if __name__ == '__main__':
        
    main()
    