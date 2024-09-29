from gcode_types import *
from tqdm import tqdm
import re



class Gcode:

    def __init__(self, blocks: BlockList|None = None):
        
        self.gcode = ''
        self.coord_system = CoordSystem()
        
        if blocks is not None:
            self.blocks = blocks
        else:
            self.blocks = BlockList()


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
        i = 0

        for block in tqdm(self.blocks, desc="Writing G-code", unit="line"):
            i += 1
            command = block.command
            line_str = ''
            
            line_str += block.move.to_str(last_move)
            last_move = block.move.copy()
            
            if line_str != '': line_str += '\n'
            
            if block.emit_command:
                line_str += command + '\n'
            
            out_str += line_str
        return out_str


    def write_file(self, filename: str):
        with open(filename, 'w') as f:
            f.write(self.write_str())


    def line_to_dict(self, line: str) -> dict[str, str]:
        line_parts = line.split(';')[0].split()
        if not line_parts:
            return {'0': ''}

        command = line_parts[0]
        params = {'0': command}

        for param in line_parts[1:]:
            if '=' in param:
                key, value = param.split('=')
                params[key] = value
            else:
                params[param[0]] = param[1:]

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
        self.blocks:list[GcodeBlock] = []
        
        meta = {'object': None, 'type': None, 'line_no': 0}
        
        gcode_lines = list(filter(str.strip, self.gcode.split('\n')))
        for id, line in enumerate(tqdm(gcode_lines, 'Generating moves', unit='line')):
            meta['line_no'] = id
            command = None
            # arc = None
            emit_command = False
            
            line_dict = self.line_to_dict(line)
            command = line_dict['0']
            move = Move(self.coord_system)
            
            if command in ['G1', 'G0']:
                move = Move(self.coord_system.copy()).from_params(line_dict)
            
            elif command in ['G2', 'G3']:
                move = Move(self.coord_system.copy()).from_params(line_dict)
                # arc = Arc(plane=self.coord_system.arc_plane).from_params(line_dict, self.coord_system).copy()
                # move = Position().from_params(line_dict)
            
            elif command in [Static.ABSOLUTE_COORDS, Static.RELATIVE_COORDS]:
                self.coord_system.set_abs_xyz(command == Static.ABSOLUTE_COORDS)

            elif command in [Static.ABSOLUTE_EXTRUDER, Static.RELATIVE_EXTRUDER]:
                self.coord_system.set_abs_e(command == Static.ABSOLUTE_EXTRUDER)

            elif command == Static.SET_POSITION:
                vec = Vector().from_params(line_dict)
                self.coord_system.set_offset(vec)
            
            elif command == Static.FAN_SPEED:
                self.coord_system.set_fan(line_dict.get('S', None))
            
            elif command == Static.FAN_OFF:
                self.coord_system.fan = 0
            
            elif command in Static.ARC_PLANES.keys():
                self.coord_system.arc_plane = Static.ARC_PLANES[command]
            
            elif command in Config.trim_gcodes:
                pass
            
            else:
                emit_command = True
            
            command = line.strip()
            
            new_pos = self.coord_system.apply_move(move.copy())
            move.position.set(new_pos)
            gcode_block = GcodeBlock(move.copy(), command=command, emit_command=emit_command)
            
            self.blocks.append(gcode_block)
