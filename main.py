import os
import numpy as np
import re
import json


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

    def to_dict(self):
        return {'I': self.I, 'J': self.J, 'K': self.K, 'dir': self.dir, 'plane': self.plane}
    
    def copy(self):
        """Create a deep copy of this Arc instance."""
        return Arc(I=self.I, J=self.J, K=self.K, dir=self.dir, plane=self.plane)



class Position:
    def __init__(self, X=None, Y=None, Z=None, E=None, F=None):
        self.X = X
        self.Y = Y
        self.Z = Z
        self.E = E
        self.F = F
    
    def __add__(self, other):
        X = self.X + other.X if self.X is not None and other.X is not None else self.X or other.X
        Y = self.Y + other.Y if self.Y is not None and other.Y is not None else self.Y or other.Y
        Z = self.Z + other.Z if self.Z is not None and other.Z is not None else self.Z or other.Z
        E = self.E + other.E if self.E is not None and other.E is not None else self.E or other.E
        F = self.F + other.F if self.F is not None and other.F is not None else self.F or other.F
        return Position(X, Y, Z, E, F)

    def __sub__(self, other):
        X = self.X - other.X if self.X is not None and other.X is not None else self.X or other.X
        Y = self.Y - other.Y if self.Y is not None and other.Y is not None else self.Y or other.Y
        Z = self.Z - other.Z if self.Z is not None and other.Z is not None else self.Z or other.Z
        E = self.E - other.E if self.E is not None and other.E is not None else self.E or other.E
        F = self.F - other.F if self.F is not None and other.F is not None else self.F or other.F
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
    
    def __init__(self, position:Position, offset:Position, arc:Arc=None, command=None):
        
        self.position = position.copy()
        self.offset = offset.copy()
        self.arc = None
        if arc is not None:
            self.arc = arc.copy()
        self.command = command


    def to_dict(self):
        if self.arc is None:
            return {
                'command': self.command,
                'position': self.position.__dict__,
                'offset': self.offset.__dict__,
                'arc': None
            }
        return {
            'commands': self.command,
            'position': self.position.__dict__,
            'offset': self.offset.__dict__,
            'arc': self.arc.__dict__
        }



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
        if len(line_parts) > 0:
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
        blocks:list[GcodeBlock] = []
        blocks.append(GcodeBlock(Position(0, 0, 0, 0, 600), Position(0, 0, 0, 0)))
        appended_lines = []
        
        for line in self.gcode.split('\n'):
            
            command = None
            handle_movement = False
            arc = None
            line_skipped = False
            
            line_dict = self.line_to_dict(line)
            
            if line_dict[0] == ABSOLUTE_COORDS:
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
            
            elif line_dict[0] in ['G2', 'G3']:
                arc = self.line_to_arc(line_dict)
                arc.plane = self.coord_system.arc_plane
                handle_movement = True

            elif line_dict[0] in ['G1', 'G0']:
                handle_movement = True
            
            elif line_dict[0] in TRIM_GCODES:
                pass
            
            else:
                # appended_lines.append(line)
                command = line.strip()
                line_skipped = True
            
            if DEBUG_GCODE_LINES and not line_skipped:
                # appended_lines.append('; CMD: ' + line)
                command = '; CMD: ' + line.strip()
                
            
            raw_pos = Position()
            if handle_movement:
                raw_pos = self.line_to_position(line_dict)
            new_pos = self.coord_system.apply_position(raw_pos)
            gcode_block = GcodeBlock(new_pos, self.coord_system.offset, arc=arc, command=command)
            
            blocks.append(gcode_block)
            # appended_lines = []
        
        
        blocks.append(GcodeBlock(Position(), Position(), command=command))
        self.gcode_blocks = blocks




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
            if block.command == "; Filament gcode":
                end_id = id
            if block.command == "; filament end gcode":
                start_id = id + 1
            if start_id > 0 and end_id > 0:
                start_gcode = gcode[:start_id]
                end_gcode = gcode[end_id:]
            
                
        layer = []
        for block in object_gcode:
            if block.command == ";BEFORE_LAYER_CHANGE":
                layers.append(layer)
            elif block.command == ";AFTER_LAYER_CHANGE":
                layer = []
            else:
                layer.append(block)
        
        layers.append(layer)
        
        self.start_gcode = start_gcode
        self.end_gcode = end_gcode
        self.layers = layers



    def log_json(self, path='.'):
        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, 'to_dict'):
                    return obj.to_dict()
                return super().default(obj)

        with open(os.path.join(path, 'gcode.json'), 'w') as f:
            f.write(json.dumps(self.gcode, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'layers.json'), 'w') as f:
            f.write(json.dumps(self.layers, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'metadata.json'), 'w') as f:
            f.write(json.dumps(self.metadata, indent=4))



with open('dsa.gcode', 'r') as f:
    gcode_file = f.read()


# gcode = Gcode()
# gcode.read_gcode(gcode_file)
# gcode.generate_moves()

tools = GcodeTools(gcode_file)
tools.read_metadata()
tools.split()
tools.log_json()

# gcode_tools = GcodeTools()

# gcode_tools.read_gcode(gcode_file)
# gcode_tools.split_layers()

# print(gcode_tools.layers[1])
