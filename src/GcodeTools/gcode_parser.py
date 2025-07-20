from GcodeTools.gcode_types import *
from GcodeTools.gcode import Gcode


class GcodeParser:


    class ParserData:
        """
        Data used to parse g-code. Stores current state of the printer and everything that is needed to generate a new `Block`
        """
        def __init__(self, coord_system: CoordSystem, block: Block):
            self.coord_system = coord_system
            self.block = block


        def copy(self):
            return GcodeParser.ParserData(self.coord_system.copy(), self.block.copy())


    @staticmethod
    def from_str(gcode: Gcode, gcode_str: str, data = BlockData(), progress_callback: typing.Callable|None = None) -> Gcode:
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            gcode_str: `str` - string that will be parsed into `Gcode`
            data: `BlockData` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
        """
        return GcodeParser._generate_moves(gcode, gcode_str, data, progress_callback)


    @staticmethod
    def from_file(gcode: Gcode, filename: str, data = BlockData(), progress_callback: typing.Callable|None = None) -> Gcode:
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            filename: `str` - filename containing g-code to be parsed
            data: `BlockData` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
        """
        with open(filename, 'r') as f:
            return GcodeParser.from_str(gcode, f.read(), data, progress_callback)


    @staticmethod
    def write_str(gcode: Gcode, verbose = False, progress_callback: typing.Callable|None = None):
        """
        Write G-Code as a string
        
        Args:
            gcode: `Gcode`
            verbose: `bool` - include Block's metadata for each line. Warning: takes up much more time and space
            progress_callback: `Callable(current: int, total: int)`
        Returns:
            str
        """
        coords = CoordSystem(speed=gcode.config.speed, abs_e=False)
        out_str = coords.to_str()

        len_blocks = len(gcode)

        for i, block in enumerate(gcode):
            
            line_str = block.to_str(verbose)
            
            out_str += line_str
            
            if progress_callback:
                progress_callback(i, len_blocks)
        
        
        return out_str


    @staticmethod
    def write_file(gcode: Gcode, filename: str, verbose = False, progress_callback: typing.Callable|None = None):
        """
        Write G-Code as a string into a file
        
        Args:
            gcode: `Gcode`
            filename: `str` of output path
            verbose: `bool` - include Block's metadata for each line. Warning: takes up much more time and space
            progress_callback: `Callable(current: int, total: int)`
        """
        coords = CoordSystem(speed=gcode.config.speed, abs_e=False)
        
        with open(filename, 'w') as f:
            f.write(coords.to_str())

            len_blocks = len(gcode)

            for i, block in enumerate(gcode):
                
                line_str = block.to_str(verbose)
                
                f.write(line_str)
                
                if progress_callback:
                    progress_callback(i, len_blocks)


    @staticmethod
    def _line_to_dict(line: str) -> dict[str, str]:
        line_parts = line.split(';')[0].split('(')[0].split()
        if not line_parts:
            return {'0': ''}

        command = line_parts[0]
        while len(command) > 2 and command[0].isalpha() and command[1] == '0':
            command = command[0] + command[2:]
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


    @staticmethod
    def _parse_line(parser_data: 'GcodeParser.ParserData') -> list['GcodeParser.ParserData']:

        pd = parser_data.copy()
        command = None
        arc = None
        emit_command = False
        move = pd.block.move.duplicate()
        
        pd.block.block_data.clear_wait()
        
        line_dict: dict = GcodeParser._line_to_dict(pd.block.command)
        command: str = line_dict['0']
        
        if command in ['G0', 'G1', 'G2', 'G3']:
            if command in ['G2', 'G3']:
                arc = Arc(move.copy(), int(command[1])).from_params(line_dict)
                
            move.position = pd.coord_system.apply_move(line_dict)
            move.from_params(line_dict)
        
        elif command in [Static.ABSOLUTE_COORDS, Static.RELATIVE_COORDS]:
            pd.coord_system.set_abs_xyz(command == Static.ABSOLUTE_COORDS)

        elif command in [Static.ABSOLUTE_EXTRUDER, Static.RELATIVE_EXTRUDER]:
            pd.coord_system.set_abs_e(command == Static.ABSOLUTE_EXTRUDER)

        elif command == Static.SET_POSITION:
            vec = Vector().from_params(line_dict)
            pd.coord_system.set_offset(vec)
        
        elif command == Static.FAN_SPEED:
            pd.block.block_data.set_fan(line_dict.get('S', None))
        
        elif command == Static.FAN_OFF:
            pd.block.block_data.set_fan(0)
        
        elif command == Static.E_TEMP or command == Static.E_TEMP_WAIT:
            pd.block.block_data.set_e_temp(line_dict.get('S', None), (command == Static.E_TEMP_WAIT))
        
        elif command == Static.BED_TEMP or command == Static.BED_TEMP_WAIT:
            pd.block.block_data.set_bed_temp(line_dict.get('S', None), (command == Static.BED_TEMP_WAIT))
        
        elif command.startswith(Static.TOOL_CHANGE) and command[1:].isdigit():
            pd.block.block_data.set_tool(int(command[1:]))
        
        elif command in Static.ARC_PLANES.keys():
            pd.coord_system.arc_plane = Static.ARC_PLANES[command]
        
        elif command == Static.HOME:
            pd.coord_system.position = Vector.zero()
        
        else:
            emit_command = True
        
        if arc is not None:
            listdata = []
            pd_new = pd.copy()
            for section in arc.subdivide(move):
                block = Block(None, section, pd.block.command.strip(), emit_command, pd.block.block_data)
                pd_new.block = block
                listdata.append(pd_new.copy())
            return listdata
        
        else:
            pd.block = Block(None, move, pd.block.command.strip(), emit_command, pd.block.block_data)
            return [pd]


    @staticmethod
    def _generate_moves(gcode: Gcode, gcode_str: str, data = BlockData(), progress_callback = None) -> Gcode:

        coord_system = CoordSystem(speed = gcode.config.speed)
        move = Move(config = gcode.config, position = coord_system.position)
        
        gcode_lines = list(filter(str.strip, gcode_str.split('\n')))
        
        len_gcode_lines = len(gcode_lines)
        
        pd = GcodeParser.ParserData(coord_system, Block(move=move))
        
        for i, line in enumerate(gcode_lines):
            
            pd.block.command = line
            list_pd:list[GcodeParser.ParserData] = GcodeParser._parse_line(pd)
            
            for num in list_pd:
                gcode.append(num.block)
            pd = list_pd[-1]
            
            if progress_callback:
                progress_callback(i, len_gcode_lines)
        
        return gcode