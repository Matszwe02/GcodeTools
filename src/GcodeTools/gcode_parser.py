from GcodeTools.gcode_types import *
from GcodeTools.gcode import Gcode
import re



class Keywords:
    """
    Each `keyword` is a list of `KW` which matches specific command.

    Keywords match slicer-specific scenatios, like object change, feature change...
    """

    class KW:
        def __init__(self, command: str, allow_command = None, block_command = None, offset = 0):
            """
            Keyword class for matching specific types of commands
            Uses regex for allow_command and block_command

            Args:
                command: str - string that is going to be matched
                allow_command: str - match only if following command is found
                block_command: str - don't match if following command is found
                offset: int - returning that line number instead
                    - `offset` = -1: offset at `allow_command`
            """
            self.command = re.compile(command)
            self.allow_command = re.compile(allow_command) if allow_command else None
            self.block_command = re.compile(block_command) if block_command else None
            self.offset = offset
    
    
    CONFIG_START = [KW("^; CONFIG_BLOCK_START"), KW("_config = begin"), KW("^; Settings Summary"), KW("^; total filament cost =", None, "_config = begin")]
    CONFIG_END = [KW("^; CONFIG_BLOCK_END"), KW("_config = end"), KW("^G"), KW("^M")]
    
    HEADER_START = [KW("^; HEADER_BLOCK_START")]
    HEADER_END = [KW("^; HEADER_BLOCK_END")]
    
    EXECUTABLE_START = [KW("^; EXECUTABLE_BLOCK_START"), KW("^;TYPE:"), KW("^;Generated with Cura_SteamEngine")]
    EXECUTABLE_END = [KW("^; EXECUTABLE_BLOCK_END")]
    
    LAYER_CHANGE = [KW("^;LAYER_CHANGE"), KW("^;LAYER:", "^;TYPE:")]
    
    GCODE_START = [KW("^;TYPE:"), KW("^;Generated with Cura_SteamEngine")]
    GCODE_END = [KW("^EXCLUDE_OBJECT_END", "^; EXECUTABLE_BLOCK_END"), KW("^;TIME_ELAPSED:", "^;End of Gcode", "^;TIME_ELAPSED:"), KW("^;TYPE:Custom", "^; filament used")]
    
    OBJECT_START = [KW("^; printing object", None, "^EXCLUDE_OBJECT_START NAME="), KW("^EXCLUDE_OBJECT_START NAME=", "^;WIDTH:", None, -1), KW("^EXCLUDE_OBJECT_START NAME=", "^G1.*E", None, -1), KW("^;MESH:"), KW("^M486 S"), KW("^M624")]
    OBJECT_END = [KW("^; stop printing object", None, "^EXCLUDE_OBJECT_END"), KW("^EXCLUDE_OBJECT_END"), KW("^;MESH:NONMESH"), KW("^M486 S-1"), KW("^M625")]
    # FIXME: Edge case scenarios, split travel moves perfectly
    # TODO: travel trimming, recalculation, preserve last travel vector at object


    @staticmethod
    def get_keyword_arg(line_no: int, gcode: Gcode, keyword: list[KW], seek_limit = 20):
        
        for offset in range(seek_limit):
            line_content = gcode[line_no - offset].command
            
            for option in keyword:
                if option.offset != offset and option.offset != -1:
                    continue
                
                match = option.command.search(line_content)
                if match:
                    if option.allow_command is None and option.block_command is None:
                        return (line_no - offset, line_content[match.end():])
                    
                    for id, nextline in enumerate(gcode[line_no - offset + 1 : line_no - offset + seek_limit + 1]):
                        if option.block_command is not None and option.block_command.search(nextline.command):
                            return (None, None)
                        if option.allow_command is not None and option.allow_command.search(nextline.command):
                            if option.offset == offset or (option.offset == -1 and offset == id):
                                return (line_no - offset, line_content[match.end():])
                            
                    if option.allow_command is None:
                        return (line_no - offset, line_content[match.end():])
                
        return (None, None)


    @staticmethod
    def get_keyword_lineno(line_no: int, gcode: Gcode, keyword: list[KW], seek_limit = 20) -> bool:
        line_no, _ = Keywords.get_keyword_arg(line_no, gcode, keyword, seek_limit)
        return _


    @staticmethod
    def get_keyword_line(line_no: int, gcode: Gcode, keyword: list[KW], seek_limit = 20) -> bool:
        _, expr = Keywords.get_keyword_arg(line_no, gcode, keyword, seek_limit)
        return expr is not None



class MoveTypes:

    PRINT_START = 'start'
    PRINT_END = 'end'
    SKIRT = 'skirt'
    EXTERNAL_PERIMETER = 'outer'
    INTERNAL_PERIMETER = 'inner'
    OVERHANG_PERIMETER = 'overhang'
    SOLID_INFILL = 'solid'
    TOP_SOLID_INFILL = 'top'
    SPARSE_INFILL = 'sparse'
    BRIDGE = 'bridge'
    NO_OBJECT = -1

    pprint_type = {
        'inner' : ';TYPE:Perimeter',
        'outer' : ';TYPE:External perimeter',
        'skirt' : ';TYPE:Skirt/Brim',
        'solid' : ';TYPE:Solid infill',
        'sparse' : ';TYPE:Internal infill',
        'bridge' : ';TYPE:Bridge infill',
        'top' : ';TYPE:Top solid infill',
        'overhang' : ';TYPE:Overhang perimeter',
        '': ';TYPE:Custom'
        }


    @staticmethod
    def get_type(line: str):
        string = line.lower()
        if not string.startswith(';'): return None
        
        type_assign = {
            'skirt': MoveTypes.SKIRT,
            'external': MoveTypes.EXTERNAL_PERIMETER,
            'overhang': MoveTypes.OVERHANG_PERIMETER,
            'outer': MoveTypes.EXTERNAL_PERIMETER,
            'perimeter': MoveTypes.INTERNAL_PERIMETER,
            'inner': MoveTypes.INTERNAL_PERIMETER,
            'bridge': MoveTypes.BRIDGE,
            'top': MoveTypes.TOP_SOLID_INFILL,
            'solid': MoveTypes.SOLID_INFILL,
            'internal': MoveTypes.SPARSE_INFILL,
            'sparse': MoveTypes.SPARSE_INFILL,
            'fill': MoveTypes.SPARSE_INFILL,
            'skin': MoveTypes.SOLID_INFILL,
            'bottom': MoveTypes.SOLID_INFILL,
            }
        
        for test in type_assign.keys():
            if test in string: return type_assign[test]
        return None


    @staticmethod
    def get_object(id: int, gcode: Gcode):
        
        def sanitize(name: str):
            return ''.join(c if c.isalnum() else '_' for c in name).strip('_')
        
        is_end = Keywords.get_keyword_line(id, gcode, Keywords.OBJECT_END)
        if is_end:
            return MoveTypes.NO_OBJECT
        
        _, name = Keywords.get_keyword_arg(id, gcode, Keywords.OBJECT_START)
        if name is not None:
            return sanitize(name)

        return None



class GcodeParser:


    @staticmethod
    def fill_meta(gcode: Gcode, progress_callback: typing.Callable|None = None):
        """
        Args:
            progress_callback: `Callable(current: int, total: int)`
        passed `Gcode` gets modified so meta is added into it
        """
        was_start = False
        
        len_gcode = len(gcode)
        
        for id, block in enumerate(gcode):
            
            line = block.command
            
            move_type = MoveTypes.get_type(line)
            if move_type is not None: block.block_data.move_type = move_type
            
            move_object = MoveTypes.get_object(id, gcode)
            if move_object == MoveTypes.NO_OBJECT: block.block_data.object = None
            elif move_object is not None: block.block_data.object = move_object
            
            if Keywords.get_keyword_line(id, gcode, Keywords.LAYER_CHANGE):
                block.block_data.layer += 1
            
            if not was_start and Keywords.get_keyword_line(id, gcode, Keywords.GCODE_START):
                block.block_data.move_type = MoveTypes.PRINT_START
                was_start = True
            if Keywords.get_keyword_line(id, gcode, Keywords.GCODE_END):
                block.block_data.move_type = MoveTypes.PRINT_END
                        
            if progress_callback:
                progress_callback(id, len_gcode)


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
        coords = CoordSystem(position=Vector(F=gcode.config.speed), abs_e=False)
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
        coords = CoordSystem(position=Vector(F=gcode.config.speed), abs_e=False)
        
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
        
        elif command in [Static.ABSOLUTE_COORDS, Static.RELATIVE_COORDS]:
            pd.coord_system.set_abs_xyz(command == Static.ABSOLUTE_COORDS)

        elif command in [Static.ABSOLUTE_EXTRUDER, Static.RELATIVE_EXTRUDER]:
            pd.coord_system.set_abs_e(command == Static.ABSOLUTE_EXTRUDER)

        elif command == Static.SET_POSITION:
            X, Y, Z, E, F = get_coords(line_dict)
            pd.coord_system.set_offset(X, Y, Z, E)
        
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
            pd.coord_system.position = Vector()
        
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

        coord_system = CoordSystem(position=Vector(F=gcode.config.speed))
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