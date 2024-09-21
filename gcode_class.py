from gcode_types import *
from tqdm import tqdm


TRIM_GCODES = ['M73', 'EXCLUDE_OBJECT_DEFINE', 'EXCLUDE_OBJECT_START', 'EXCLUDE_OBJECT_END']

DEBUG_GCODE_LINES = True



class Gcode:
    
    def __init__(self):
        
        self.gcode = ''
        self.coord_system = CoordSystem()
        self.gcode_blocks:list[GcodeBlock] = []


    def from_str(self, gcode_str):
        self.gcode = gcode_str
        self.generate_moves()
        return self
    
    
    def from_file(self, filename: str):
        with open(filename, 'r') as f:
            self.from_str(f.read())
        return self


    def write_str(self):
        out_str = ''
        last_move = None

        # for block in self.gcode_blocks:
        for block in tqdm(self.gcode_blocks, desc="Writing G-code", unit="line"):
            command = block.command
            if command is None or command.startswith('; CMD: ') or len(command) == 0:
                
                # if block.arc is not None:
                #     newline = block.arc.to_str()
                    # positions = block.arc.subdivide(step=0.5)
                    # for pos in positions:
                    #     out_str += pos.to_str() + '\n'
                # elif last_pos is None:
                out_str += block.move.to_str(last_move)
                
                last_move = block.move.copy()
                
                # if newline is not None: out_str += newline
                # last_pos = block.move
            out_str += command
            out_str += '\n'
        return out_str


    def write_file(self, filename: str):
        with open(filename, 'w') as f:
            f.write(self.write_str())


    def line_to_dict(self, line):
        params = ['', []]
        line_parts = line.split(';')[0].split(' ')  
        if line_parts:
            params[0] = line_parts[0]

            for param in line_parts[1:]:
                
                if not param: continue
                params[1].append(param)
        
        return params


    def generate_moves(self):
        
        self.coord_system = CoordSystem()
        self.gcode_blocks:list[GcodeBlock] = []
        
        meta = {'object': None, 'type': None, 'line_no': 0}
        
        gcode_lines = list(filter(str.strip, self.gcode.split('\n')))
        for id, line in enumerate(tqdm(gcode_lines, 'Generating moves', unit='line')):
        # for id, line in enumerate(filter(str.strip, self.gcode.split('\n'))):
            meta['line_no'] = id
            command = None
            arc = None
            line_skipped = False
            
            line_dict = self.line_to_dict(line)
            move = Move(self.coord_system)
            
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
                move = Move(self.coord_system.copy()).from_params(line_dict)
            
            elif line_dict[0] in ['G2', 'G3']:
                move = Move(self.coord_system.copy()).from_params(line_dict)
                
                # arc = Arc(plane=self.coord_system.arc_plane).from_params(line_dict, self.coord_system).copy()
                # move = Position().from_params(line_dict)
            
            elif line_dict[0] == Static.ABSOLUTE_COORDS:
                self.coord_system.set_xyz_coords(True)
            elif line_dict[0] == Static.RELATIVE_COORDS:
                self.coord_system.set_xyz_coords(False)

            elif line_dict[0] == Static.ABSOLUTE_EXTRUDER:
                self.coord_system.set_e_coords(True)
            elif line_dict[0] == Static.RELATIVE_EXTRUDER:
                self.coord_system.set_e_coords(False)
            
            elif line_dict[0] == Static.SET_POSITION:
                # move = Position().from_params(line_dict)
                # move = self.line_to_position(line_dict).copy()
                self.coord_system.set_offset(move.position)
            
            elif line_dict[0] == Static.ARC_PLANE_XY:
                self.coord_system.arc_plane = 17
            elif line_dict[0] == Static.ARC_PLANE_XZ:
                self.coord_system.arc_plane = 18
            elif line_dict[0] == Static.ARC_PLANE_YZ:
                self.coord_system.arc_plane = 19
            
            elif line_dict[0] in TRIM_GCODES:
                pass
            
            else:
                command = line.strip()
                line_skipped = True
            
            if DEBUG_GCODE_LINES and not line_skipped:
                command = '; CMD: ' + line.strip()
            
            new_pos = self.coord_system.apply_move(move.copy())
            move.position.set(new_pos)
            gcode_block = GcodeBlock(move.copy(), command=command, meta=meta)
            
            self.gcode_blocks.append(gcode_block)
        
        # self.gcode_blocks.append(GcodeBlock(Move(), command=command, meta=meta))

