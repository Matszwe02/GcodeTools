from gcode_types import *
from tqdm import tqdm
import re



class GcodeLoader:

    def from_str(gcode_str):
        return GcodeLoader.generate_moves(gcode_str)
    
    
    def from_file(filename: str):
        with open(filename, 'r') as f:
            return GcodeLoader.from_str(f.read())


    def write_str(gcode: Gcode, verbose = False):
        """
        Write G-Code as a string
        
        `gcode`: Gcode
        
        `verbose`: include Block's metadata for each line.
        Includes object name, line type, layer number, etc.
        Warning: takes up much more time and space
        """
        last_block = Block(Move())
        coords = CoordSystem(abs_e=False)
        out_str = coords.to_str()
        

        for block in tqdm(gcode, desc="Writing G-code", unit="line"):
            
            line_str = block.to_str(last_block, verbose)
            
            out_str += line_str
            last_block = block
            
        return out_str


    def write_file(gcode: Gcode, filename: str, verbose = False):
        """
        Write G-Code as a string
        
        `gcode`: Gcode
        
        `filename`: str of output path
        
        `verbose`: include Block's metadata for each line. Warning: takes up much more time and space
        """
        gcode_str = GcodeLoader.write_str(gcode, verbose = verbose)
        with open(filename, 'w') as f:
            f.write(gcode_str)
    
    
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
                try:
                    params[key] = int(value)
                except Exception:
                    params[key] = value
            else:
                try:
                    params[param[0]] = int(param[1:])
                except Exception:
                    params[param[0]] = param[1:]

        return params


    def generate_moves(gcode_str: str, config = Config()):

        gcode = Gcode()
        gcode.config = config
        coord_system = CoordSystem(speed = gcode.config.speed)
        move = Move(gcode.config, coord_system.position)
        data = BlockData.zero()
        
        gcode_lines = list(filter(str.strip, gcode_str.split('\n')))
        for line in tqdm(gcode_lines, 'Generating moves', unit='line'):
            command = None
            arc = None
            emit_command = False
            
            data.clear_wait()
            
            line_dict: dict = GcodeLoader.line_to_dict(line)
            command: str = line_dict['0']
            
            if command in ['G0', 'G1', 'G2', 'G3']:
                if command in ['G2', 'G3']:
                    arc = Arc(move.copy(), int(command[1])).from_params(line_dict)
                    
                move.position = coord_system.apply_move(line_dict)
                move.from_params(line_dict)
            
            elif command in [Static.ABSOLUTE_COORDS, Static.RELATIVE_COORDS]:
                coord_system.set_abs_xyz(command == Static.ABSOLUTE_COORDS)

            elif command in [Static.ABSOLUTE_EXTRUDER, Static.RELATIVE_EXTRUDER]:
                coord_system.set_abs_e(command == Static.ABSOLUTE_EXTRUDER)

            elif command == Static.SET_POSITION:
                vec = Vector().from_params(line_dict)
                coord_system.set_offset(vec)
            
            elif command == Static.FAN_SPEED:
                data.set_fan(line_dict.get('S', None))
            
            elif command == Static.FAN_OFF:
                data.set_fan(0)
            
            elif command == Static.E_TEMP or command == Static.E_TEMP_WAIT:
                data.set_e_temp(line_dict.get('S', None), (command == Static.E_TEMP_WAIT))
            
            elif command == Static.BED_TEMP or command == Static.BED_TEMP_WAIT:
                data.set_bed_temp(line_dict.get('S', None), (command == Static.BED_TEMP_WAIT))
            
            elif command.startswith(Static.TOOL_CHANGE) and command[1:].isdigit():
                data.set_tool(int(command[1:]))
            
            elif command in Static.ARC_PLANES.keys():
                coord_system.arc_plane = Static.ARC_PLANES[command]
            
            else:
                emit_command = True
            
            command = line.strip()
            
            if arc is not None:
                for section in arc.subdivide(move, 1): # TODO: improve default step size
                    block = Block(section, line, emit_command, data.copy(), {})
                    gcode.append(block)
            
            else:
                block = Block(move, line, emit_command, data.copy(), {})
                gcode.append(block)
        return gcode