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

        for block in tqdm(self.gcode_blocks, desc="Writing G-code", unit="line"):
            command = block.command
            if command is None or command.startswith('; CMD: ') or len(command) == 0:
                
                out_str += block.move.to_str(last_move)
                last_move = block.move.copy()
                
            out_str += command + '\n'
        return out_str


    def write_file(self, filename: str):
        with open(filename, 'w') as f:
            f.write(self.write_str())


    def line_to_dict(self, line: str) -> dict[str, list[str]]:
        params = ['', []]
        line_parts = line.split(';')[0].split(' ')  
        if line_parts:
            params[0] = line_parts[0]

            for param in line_parts[1:]:
                if param: params[1].append(param)
        
        return params


    def read_meta(self, line: str, meta: dict):
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
        return meta


    def generate_moves(self):
        
        self.coord_system = CoordSystem()
        self.gcode_blocks:list[GcodeBlock] = []
        
        meta = {'object': None, 'type': None, 'line_no': 0}
        
        gcode_lines = list(filter(str.strip, self.gcode.split('\n')))
        for id, line in enumerate(tqdm(gcode_lines, 'Generating moves', unit='line')):
            meta['line_no'] = id
            command = None
            # arc = None
            line_skipped = False
            
            line_dict = self.line_to_dict(line)
            move = Move(self.coord_system)
            
            if line[0] == ';':
                meta = self.read_meta(line, meta)
            
            if line_dict[0] in ['G1', 'G0']:
                move = Move(self.coord_system.copy()).from_params(line_dict)
            
            elif line_dict[0] in ['G2', 'G3']:
                move = Move(self.coord_system.copy()).from_params(line_dict)
                # arc = Arc(plane=self.coord_system.arc_plane).from_params(line_dict, self.coord_system).copy()
                # move = Position().from_params(line_dict)
            
            elif line_dict[0] in [Static.ABSOLUTE_COORDS, Static.RELATIVE_COORDS]:
                self.coord_system.set_abs_xyz(line_dict[0] == Static.ABSOLUTE_COORDS)

            elif line_dict[0] in [Static.ABSOLUTE_EXTRUDER, Static.RELATIVE_EXTRUDER]:
                self.coord_system.set_abs_e(line_dict[0] == Static.ABSOLUTE_EXTRUDER)

            elif line_dict[0] == Static.SET_POSITION:
                vec = Vector().from_params(line_dict)
                self.coord_system.set_offset(vec)
            
            elif line_dict[0] in Static.ARC_PLANES.keys():
                self.coord_system.arc_plane = Static.ARC_PLANES[line_dict[0]]
            
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

