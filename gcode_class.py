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
        last_move = None
        coords = CoordSystem()
        coords.abs_e = False
        out_str = coords.to_str()
        i = 0
        

        for block in tqdm(gcode, desc="Writing G-code", unit="line"):
            i += 1
            command = block.command
            line_str = ''
            
            line_str += block.move.to_str(last_move)
            
            if line_str != '':
                if verbose and block.meta is not None:
                    params_str = json.dumps(block.meta).replace("{", "").replace("}", "").replace(" ", "").replace('"', "").replace(',', '\n; ')
                    line_str += f'\n; duration:{block.move.duration(last_move):.2f}'
                    line_str += f'\n; {params_str}'
                line_str += '\n'
            
            if block.emit_command:
                line_str += command + '\n'
            
            out_str += line_str
            last_move = block.move.copy()
            
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
                params[key] = value
            else:
                params[param[0]] = param[1:]

        return params


    def generate_moves(gcode_str: str, config = Config()):

        blocks = Gcode()
        blocks.config = config
        coord_system = CoordSystem(speed = blocks.config.speed)
        move = Move(blocks.config, coord_system.position)
        
        gcode_lines = list(filter(str.strip, gcode_str.split('\n')))
        for line in tqdm(gcode_lines, 'Generating moves', unit='line'):
            command = None
            arc = None
            emit_command = False
            
            line_dict: dict = GcodeLoader.line_to_dict(line)
            command = line_dict['0']
            
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
                coord_system.set_fan(line_dict.get('S', None))
            
            elif command == Static.FAN_OFF:
                coord_system.fan = 0
            
            elif command in Static.ARC_PLANES.keys():
                coord_system.arc_plane = Static.ARC_PLANES[command]
            
            else:
                emit_command = True
            
            command = line.strip()
            
            if arc is not None:
                for section in arc.subdivide(move, 1):
                    gcode_block = Block(section.copy(), command=line, emit_command=emit_command)
                    blocks.append(gcode_block)
                    command = None
                    
            else:
                gcode_block = Block(move.copy(), command=line, emit_command=emit_command)
                blocks.append(gcode_block)
        
        return blocks