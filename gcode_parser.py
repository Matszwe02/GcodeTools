from gcode_types import *
from gcode import Gcode


class GcodeParser:

    def from_str(gcode: Gcode, gcode_str: str, progress_callback = None) -> Gcode:
        """
        `gcode`: Gcode or None. When Gcode, uses its config. When None, creates an empty Gcode.
        
        `progress_callback`: function(current: int, total: int)
        """
        return GcodeParser._generate_moves(gcode, gcode_str, progress_callback)


    def from_file(gcode: Gcode, filename: str, progress_callback = None) -> Gcode:
        """
        `gcode`: Gcode or None. When Gcode, uses its config. When None, creates an empty Gcode.
        
        `progress_callback`: function(current: int, total: int)
        """
        with open(filename, 'r') as f:
            return GcodeParser.from_str(gcode, f.read(), progress_callback)


    def write_str(gcode: Gcode, verbose = False, progress_callback = None):
        """
        Write G-Code as a string
        
        `gcode`: Gcode
        
        `verbose`: include Block's metadata for each line.
        Includes object name, line type, layer number, etc.
        Warning: takes up much more time and space
        
        `progress_callback`: function(current: int, total: int)
        """
        # last_block = Block()
        coords = CoordSystem(speed=gcode.config.speed, abs_e=False)
        out_str = coords.to_str()

        len_blocks = len(gcode)

        for i, block in enumerate(gcode):
            
            line_str = block.to_str(verbose)
            
            out_str += line_str
            # last_block = block
            
            if progress_callback:
                progress_callback(i, len_blocks)
        
        
        return out_str


    def write_file(gcode: Gcode, filename: str, verbose = False, progress_callback = None):
        """
        Write G-Code as a string
        
        `gcode`: Gcode
        
        `filename`: str of output path
        
        `verbose`: include Block's metadata for each line. Warning: takes up much more time and space
        
        `progress_callback`: function(current: int, total: int)
        """
        gcode_str = GcodeParser.write_str(gcode, verbose, progress_callback)
        with open(filename, 'w') as f:
            f.write(gcode_str)


    def _line_to_dict(line: str) -> dict[str, str]:
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


    def _generate_moves(gcode: Gcode, gcode_str: str, progress_callback = None) -> Gcode:

        coord_system = CoordSystem(speed = gcode.config.speed)
        move = Move(config = gcode.config, position = coord_system.position)
        data = BlockData.zero()
        
        gcode_lines = list(filter(str.strip, gcode_str.split('\n')))
        
        len_gcode_lines = len(gcode_lines)
        
        for i, line in enumerate(gcode_lines):
            command = None
            arc = None
            emit_command = False
            
            data.clear_wait()
            
            line_dict: dict = GcodeParser._line_to_dict(line)
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
                    block = Block(None, section, line, emit_command, data.copy(), {})
                    gcode.append(block)
            
            else:
                block = Block(None, move, line, emit_command, data.copy(), {})
                gcode.append(block)
                
            if progress_callback:
                progress_callback(i, len_gcode_lines)
        
        return gcode