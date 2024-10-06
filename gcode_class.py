from gcode_types import *
from tqdm import tqdm
import re



class Gcode:

    def from_str(gcode_str):
        return Gcode.generate_moves(gcode_str)
    
    
    def from_file(filename: str):
        with open(filename, 'r') as f:
            return Gcode.from_str(f.read())


    def write_str(gcode: BlockList):
        out_str = ''
        last_move = None
        i = 0

        for block in tqdm(gcode, desc="Writing G-code", unit="line"):
            i += 1
            command = block.command
            line_str = ''
            
            if type(block.move) == Move:
                line_str += block.move.to_str(last_move)
                last_move = block.move.copy()
            else:
                line_str += block.move.to_str(last_move)
                last_move = block.move.move.copy()
            
            if line_str != '': line_str += '\n'
            
            if block.emit_command:
                line_str += command + '\n'
            
            out_str += line_str
        return out_str


    def write_file(gcode: BlockList, filename: str):
        with open(filename, 'w') as f:
            f.write(Gcode.write_str(gcode))
    
    
    def log_json(object, filename: str):
        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, 'to_dict'):
                    return obj.to_dict()
                return super().default(obj)
        
        print('Logging json...')
        with open(filename, 'w') as f:
            f.write(json.dumps(object, indent=4, cls=CustomEncoder))


    def line_to_dict(line: str) -> dict[str, str]:
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


    def read_meta(line: str, meta: dict):
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


    def generate_moves(gcode_str: str):

        coord_system = CoordSystem()
        blocks:list[Block] = []
        
        meta = {'object': None, 'type': None, 'line_no': 0}
        
        gcode_lines = list(filter(str.strip, gcode_str.split('\n')))
        for id, line in enumerate(tqdm(gcode_lines, 'Generating moves', unit='line')):
            meta['line_no'] = id
            meta = Gcode.read_meta(line, meta)
            command = None
            arc = None
            emit_command = False
            
            line_dict = Gcode.line_to_dict(line)
            command = line_dict['0']
            move = Move(coord_system)
            
            if command in ['G0', 'G1', 'G2', 'G3']:
                move = Move(coord_system.copy()).from_params(line_dict)
                
                if command in ['G2', 'G3']:
                    arc = Arc(dir = int(command[1]), move=move).from_params(line_dict)
            
            elif command in [Static.ABSOLUTE_COORDS, Static.RELATIVE_COORDS]:
                coord_system.set_abs_xyz(command == Static.ABSOLUTE_COORDS)

            elif command in [Static.ABSOLUTE_EXTRUDER, Static.RELATIVE_EXTRUDER]:
                coord_system.set_abs_e(command == Static.ABSOLUTE_EXTRUDER)

            elif command == Static.SET_POSITION:
                vec = Vector().from_params(line_dict)
                coord_system.set_offset(vec)
            
            elif command == Static.FAN_SPEED:
                coord_system.set_fan(line_dict.get('S', None))
            
            elif command == Static.FAN_OFF:
                coord_system.fan = 0
            
            elif command in Static.ARC_PLANES.keys():
                coord_system.arc_plane = Static.ARC_PLANES[command]
            
            else:
                emit_command = True
            
            command = line.strip()
            
            new_pos = coord_system.apply_move(move.copy())
            move.position.set(new_pos)
            
            if arc is not None:
                gcode_block = Block(arc.copy(), command=command, emit_command=emit_command, meta=meta)
            else:
                gcode_block = Block(move.copy(), command=command, emit_command=emit_command, meta=meta)
            
            blocks.append(gcode_block)
        
        return blocks