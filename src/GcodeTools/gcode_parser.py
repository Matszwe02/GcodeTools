from GcodeTools.gcode_types import *
from GcodeTools.gcode import Gcode
import re



class MetaParser:
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
    OBJECT_NAME_DEFINE = [KW("^M486 A"), KW("^; object:{\"name\":\"")]
    # FIXME: Edge case scenarios, split travel moves perfectly
    # TODO: travel trimming, recalculation, preserve last travel vector at object


    @staticmethod
    def get_keyword_arg(line_no: int, gcode: Gcode, keyword: list[KW], seek_limit = 20):
        
        for offset in range(seek_limit):
            if line_no - offset < 0: continue
            if line_no - offset >= len(gcode): continue
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
        line_no, _ = MetaParser.get_keyword_arg(line_no, gcode, keyword, seek_limit)
        return _


    @staticmethod
    def get_keyword_line(line_no: int, gcode: Gcode, keyword: list[KW], seek_limit = 20) -> bool:
        _, expr = MetaParser.get_keyword_arg(line_no, gcode, keyword, seek_limit)
        return expr is not None


    @staticmethod
    def get_type(line: str):
        if not line.startswith(';'): return None
        string = line.lower()
        if 'object' in string: return None
        if 'fan' in string: return None
        if 'start' in string: return None
        if 'stop' in string: return None

        type_assign = {
            'support': Static.SUPPORT,
            'skirt': Static.SKIRT,
            'external': Static.EXTERNAL_PERIMETER,
            'overhang': Static.OVERHANG_PERIMETER,
            'outer': Static.EXTERNAL_PERIMETER,
            'perimeter': Static.INTERNAL_PERIMETER,
            'inner': Static.INTERNAL_PERIMETER,
            'bridge': Static.BRIDGE,
            'top': Static.TOP_SOLID_INFILL,
            'solid': Static.SOLID_INFILL,
            'internal': Static.SPARSE_INFILL,
            'sparse': Static.SPARSE_INFILL,
            'fill': Static.SPARSE_INFILL,
            'skin': Static.SOLID_INFILL,
            'bottom': Static.SOLID_INFILL,
            }
        
        for test in type_assign.keys():
            if test in string: return type_assign[test]
        return None


    # @staticmethod
    # def update_object_map(id: int, gcode: Gcode, current_object: str, object_map: dict):
    #     _, namedef = MetaParser.get_keyword_arg(id, gcode, MetaParser.OBJECT_NAME_DEFINE, seek_limit=1)
    #     if namedef is not None:
    #         if '"' in namedef: # SuperSlicer naming
    #             namedef = namedef.split('"')[0]
    #             current_object = str(len(object_map.keys()))
    #         object_map[current_object] = namedef
    #         print(f'meta: Putting {namedef} to meta as {current_object}')
    #         print(f'Current object map: {object_map}')
    #     return object_map


    @staticmethod
    def get_object(id: int, gcode: Gcode):
        
        def sanitize(name: str):
            return ''.join(c if c.isalnum() else '_' for c in name).strip('_')
        
        is_end = MetaParser.get_keyword_line(id, gcode, MetaParser.OBJECT_END)
        if is_end:
            return Static.NO_OBJECT
        
        _, name = MetaParser.get_keyword_arg(id, gcode, MetaParser.OBJECT_START)
        if name is not None:
            return sanitize(name)

        return None


    @staticmethod
    def fill_meta(gcode: Gcode, progress_callback: typing.Callable|None = None):
        """
        Args:
            progress_callback: `Callable(current: int, total: int)`
        passed `Gcode` gets modified so meta is added into it
        """
        was_start = False
        layer = 0
        move_type = -1
        move_object = ''
        len_gcode = len(gcode)
        # object_map = {}
        gcode.objects = []
        
        for id, block in enumerate(gcode):
                        
            move_type = MetaParser.get_type(block.command) or move_type
            move_object = MetaParser.get_object(id, gcode) or move_object
            # object_map = MetaParser.update_object_map(id, gcode, move_object, object_map)
            
            if MetaParser.get_keyword_line(id, gcode, MetaParser.LAYER_CHANGE):
                layer += 1
            
            if not was_start and MetaParser.get_keyword_line(id, gcode, MetaParser.GCODE_START):
                move_type = Static.PRINT_START
                was_start = True
            if MetaParser.get_keyword_line(id, gcode, MetaParser.GCODE_END):
                move_type = Static.PRINT_END
            
            block.move_type = move_type
            if move_object and isinstance(move_object, str) and not move_object.isdigit() and move_object not in gcode.objects:
                gcode.objects.append(move_object)
            try:
                block.object = gcode.objects.index(move_object)
            except ValueError:
                block.object = -1

            # block.object = object_map.get(move_object, move_object) if move_object != -1 else ''
            block.layer = layer
            
            if progress_callback:
                progress_callback(id, len_gcode)
        return gcode



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
    def from_str(gcode: Gcode, gcode_str: str, block = Block(), progress_callback: typing.Callable|None = None) -> Gcode:
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            gcode_str: `str` - string that will be parsed into `Gcode`
            block: `Block` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
        """
        return GcodeParser._generate_moves(gcode, gcode_str, block, progress_callback)


    @staticmethod
    def from_file(gcode: Gcode, filename: str, block = Block(), progress_callback: typing.Callable|None = None) -> Gcode:
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            filename: `str` - filename containing g-code to be parsed
            block: `Block` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
        """
        with open(filename, 'r') as f:
            return GcodeParser.from_str(gcode, f.read(), block, progress_callback)


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
        out_str = gcode.header + '\n' + coords.to_str()

        len_blocks = len(gcode)

        for i, block in enumerate(gcode):
            
            line_str = block.to_str(verbose)
            
            out_str += line_str
            
            if progress_callback:
                progress_callback(i, len_blocks)
        
        
        return out_str + '\n' + gcode.footer


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
            f.write(gcode.header + '\n' + coords.to_str())

            len_blocks = len(gcode)

            for i, block in enumerate(gcode):
                
                line_str = block.to_str(verbose)
                
                f.write(line_str)
                
                if progress_callback:
                    progress_callback(i, len_blocks)

            f.write('\n' + gcode.footer)


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
        
        pd.block.clear_wait()
        
        line_dict: dict = GcodeParser._line_to_dict(pd.block.command)
        command: str = line_dict['0']
        
        if command in ['G0', 'G1', 'G2', 'G3']:
            if command in ['G2', 'G3']:
                arc = Arc(pd.block.position.copy(), int(command[1])).from_params(line_dict)
                pass
                
            pd.block.position = pd.coord_system.apply_move(line_dict)
        
        elif command in [Static.ABSOLUTE_COORDS, Static.RELATIVE_COORDS]:
            pd.coord_system.set_abs_xyz(command == Static.ABSOLUTE_COORDS)

        elif command in [Static.ABSOLUTE_EXTRUDER, Static.RELATIVE_EXTRUDER]:
            pd.coord_system.set_abs_e(command == Static.ABSOLUTE_EXTRUDER)

        elif command == Static.SET_POSITION:
            c = Coords(line_dict)
            pd.coord_system.set_offset(c.X, c.Y, c.Z, c.E)
        
        elif command == Static.FAN_SPEED:
            pd.block.set_fan(line_dict.get('S', None))
        
        elif command == Static.FAN_OFF:
            pd.block.set_fan(0)
        
        elif command == Static.E_TEMP or command == Static.E_TEMP_WAIT:
            pd.block.set_e_temp(line_dict.get('S', None), (command == Static.E_TEMP_WAIT))
        
        elif command == Static.BED_TEMP or command == Static.BED_TEMP_WAIT:
            pd.block.set_bed_temp(line_dict.get('S', None), (command == Static.BED_TEMP_WAIT))
        
        elif command.startswith(Static.TOOL_CHANGE) and command[1:].isdigit():
            pd.block.set_tool(int(command[1:]))
        
        elif command in Static.ARC_PLANES.keys():
            pd.coord_system.arc_plane = Static.ARC_PLANES[command]
        
        elif command == Static.HOME:
            pd.coord_system.position = Vector()
        
        else:
            emit_command = True
        
        if arc is not None:
            listdata = []
            pd_new = pd.copy()
            for section in arc.subdivide(pd.block.position, pd.block.config.step):
                # block = Block(None, pd.block.command.strip(), emit_command)
                block = pd.block.copy()
                block.prev = None
                block.command = pd.block.command.strip()
                block.emit_command = emit_command
                block.position = section
                pd_new.block = block
                listdata.append(pd_new.copy())
            return listdata
        
        else:
            # pd.block = Block(None, pd.block.command.strip(), emit_command)
            block = pd.block.copy()
            block.prev = None
            block.command = pd.block.command.strip()
            block.emit_command = emit_command
            pd.block = block
            return [pd]


    @staticmethod
    def _generate_moves(gcode: Gcode, gcode_str: str, block = Block(), progress_callback = None) -> Gcode:

        coord_system = CoordSystem(position=Vector(F=gcode.config.speed))
        block = block.copy()
        block.position = coord_system.position
        
        gcode_lines = list(filter(str.strip, gcode_str.split('\n')))
        
        len_gcode_lines = len(gcode_lines)
        
        pd = GcodeParser.ParserData(coord_system, block)
        
        for i, line in enumerate(gcode_lines):
            
            pd.block.command = line
            list_pd:list[GcodeParser.ParserData] = GcodeParser._parse_line(pd)
            
            for num in list_pd:
                num.block.config = gcode.config
                gcode.append(num.block)
            pd = list_pd[-1]
            
            if progress_callback:
                progress_callback(i, len_gcode_lines)
        
        return gcode