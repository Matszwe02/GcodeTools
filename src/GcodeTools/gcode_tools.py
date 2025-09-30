import json
from GcodeTools.gcode_types import *
from GcodeTools.gcode import Gcode
import base64
import textwrap
import re


meta_initial = {'object': None, 'type': None, 'layer': 0}

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



class Tools:


    @staticmethod
    def get_slicer_name(gcode: Gcode) -> tuple[str, str]:
        """
        Get (`slicer_name`, `slicer_version`)
        """
        for line in gcode[:20]:
            cmd = line.command
            if 'bambustudio' in cmd.lower():
                slicer = 'BambuStudio'
                version = cmd.split('BambuStudio')[1].trim()
                return (slicer, version)
            if 'generated' in cmd.lower():
                line = cmd.split('by')[-1].split('with')[-1].replace('Version', '').replace('(R)', '').split()
                slicer = line[0]
                version = line[1]
                return (slicer, version)


    @staticmethod
    def read_config(gcode: Gcode):
        """
        Read slicer's config from `Gcode`
        """
        metadata = {}
        start_id, end_id = -1, -1
        for id, block in enumerate(gcode):
        
            if start_id == -1 and Keywords.get_keyword_line(id, gcode, Keywords.CONFIG_START): start_id = id
            if end_id == -1 and start_id != -1 and Keywords.get_keyword_line(id, gcode, Keywords.CONFIG_END): end_id = id
        
        if start_id == -1 or end_id - start_id > 1000: return None
        print(f'{start_id=}, {end_id=}')
        
        for block in gcode[start_id + 1 : end_id]:
            line = block.command
            delimeter = line.find('=')
            if delimeter < 0: delimeter = line.find(',')
            key = line[1:delimeter].strip()
            value = line[delimeter + 1:].strip()
            metadata[key] = value
        
        return metadata


    @staticmethod
    def generate_config_files(gcode: Gcode) -> dict[str, str]:
        """
        Generate configuration file(s) for slicer which generated the gcode.

        Returns:
            {`filename`, `contents`}
        """
        slicer, version = Tools.get_slicer_name(gcode)
        config = Tools.read_config(gcode)
        if slicer.lower() in ['cura']:
            print(f'{slicer.lower()} doesn\'t generate configuration')
            return {}
        elif slicer.lower() in ['orcaslicer', 'bambustudio']:
            machine = config.copy()
            process = config.copy()
            filament = {}

            filament_fields = ['filament', 'fan_', 'temp', 'nozzle', 'slow', 'air_']
            for key in config.keys():
                if any(field in key for field in filament_fields):
                    filament[key] = config[key]

            try:
                inherit_groups = config['inherits_group'].split(';')
                if inherit_groups[0]:
                    process['inherits'] = inherit_groups[0]
                if inherit_groups[1]:
                    filament['inherits'] = inherit_groups[1]
                if inherit_groups[2]:
                    machine['inherits'] = inherit_groups[2]
                    process['compatible_printers'] = [inherit_groups[2]]
                    filament['compatible_printers'] = [inherit_groups[2]]
            except KeyError:
                pass

            filament['from'] = 'User'
            filament['type'] = 'filament'
            filament['is_custom_defined'] = '0'
            filament['version'] = version
            filament['name'] = config['filament_settings_id']

            machine['from'] = 'User'
            machine['type'] = 'machine'
            machine['is_custom_defined'] = '0'
            machine['version'] = version
            machine['name'] = config['printer_settings_id']

            process['from'] = 'User'
            process['type'] = 'process'
            process['is_custom_defined'] = '0'
            process['version'] = version
            process['name'] = config['print_settings_id']

            filament_str = json.dumps(filament, indent=4)
            machine_str = json.dumps(machine, indent=4)
            process_str = json.dumps(process, indent=4)

            return {'filament.json': filament_str, 'machine.json': machine_str, 'process.json': process_str}

        else:
            if slicer.lower() not in ['prusaslicer', 'slic3r', 'superslicer']:
                print('Unsupported slicer: trying generating slic3r config')
            output = ''
            for key in config.keys():
                output += key + ' = ' + config[key] + '\n'
            return {'config.ini': output}


    @staticmethod
    def fill_meta(gcode: Gcode, progress_callback: typing.Callable|None = None):
        """
        Args:
            progress_callback: `Callable(current: int, total: int)`
        passed `Gcode` gets modified so meta is added into it
        """
        meta = meta_initial.copy()
        was_start = False
        
        len_gcode = len(gcode)
        
        for id, block in enumerate(gcode):
            
            line = block.command
            
            move_type = MoveTypes.get_type(line)
            if move_type is not None: meta['type'] = move_type
            
            move_object = MoveTypes.get_object(id, gcode)
            if move_object == MoveTypes.NO_OBJECT: meta["object"] = None
            elif move_object is not None: meta['object'] = move_object
            
            if Keywords.get_keyword_line(id, gcode, Keywords.LAYER_CHANGE):
                meta['layer'] += 1
            
            if not was_start and Keywords.get_keyword_line(id, gcode, Keywords.GCODE_START):
                meta['type'] = MoveTypes.PRINT_START
                was_start = True
            if Keywords.get_keyword_line(id, gcode, Keywords.GCODE_END):
                meta['type'] = MoveTypes.PRINT_END
            
            block.meta = json.loads(json.dumps(meta))
            
            if progress_callback:
                progress_callback(id, len_gcode)


    @staticmethod
    def get_by_meta(gcode: Gcode, meta: str, value = None, value_check: typing.Callable[[typing.Any], bool]|None = None, break_on = lambda x: False):
        """
        Args:
            meta: `str` - meta's key which needs to be compared
            value: `Any` - the value that is compared
            value_check: `Callable` - comparison method
                for example `lambda x: x == 'inner'`
            break_on: `Callable` - stop further checking
                inactive until first `Block` is added
        """
        gcode_new = gcode.new()
        is_none = True
        for i in gcode:
            i_meta = i.meta.get(meta, None)
            
            if value_check is None:
                if i_meta == value:
                    gcode_new.append(i)
                    is_none = False
            else:
                if value_check(i_meta):
                    gcode_new.append(i)
                    is_none = False
            
            if len(gcode_new) > 0 and break_on(i_meta):
                break
        
        if is_none:
            return None
        return gcode_new


    @staticmethod
    def split(gcode: Gcode) -> tuple[Gcode, Gcode, Gcode, dict[Gcode]]:
        """
        Splits `Gcode` into:
            start_gcode, object_gcode, end_gcode, where object_gcode is everything between start and end gcodes
            objects: `dict` of individual objects' `Gcode`s
        
        
        Returns:
            `tuple`: (`start_gcode`: Gcode, `end_gcode`: Gcode, `object_gcode`: Gcode, `objects`: dict[Gcode])
        """
        object_gcode = gcode.new()
        start_gcode = gcode.new()
        end_gcode = gcode.new()
        objects: dict[Gcode] = {}
        
        for block in gcode:
            
            if block.meta.get('type') == MoveTypes.PRINT_START:
                start_gcode.append(block)
            elif block.meta.get('type') == MoveTypes.PRINT_END:
                end_gcode.append(block)
            else:
                object_gcode.append(block)
            
            object = block.meta.get('object')
            if object not in objects.keys():
                objects[object] = gcode.new()
            
            objects[object].append(block)
        
        return (start_gcode, end_gcode, object_gcode, objects)


    @staticmethod
    def trim(gcode: Gcode):
        """
        Trims G-code from every command that's not handled by GcodeTools
        
        Warning: some commands that aren't handled, may be important for the G-code!
        """
        
        gcode_new = gcode.new()
        pos = gcode[0].move
        for item in gcode:
            if item.move != pos:
                pos = item.move
                it = item.copy()
                it.emit_command = False
                it.command = ''
                gcode_new.append(it)
        return gcode_new


    @staticmethod
    def set_flowrate(gcode: Gcode, flowrate: float, force_extrusion = False) -> Gcode:
        """
        Sets flowrate (mm in E over mm in XYZ)
        
        Args:
            flowrate: `float` - desired flowrate
            force_extrusion: `bool` - on `True` forces flowrate even on non-extrusion moves
        """
        gcode_new = gcode.copy()
        for i in gcode_new:
            if force_extrusion or (i.move.position.E and i.move.position.E > 0):
                i.move.set_flowrate(flowrate)
        return gcode_new


    @staticmethod
    def translate(gcode: Gcode, vector: Vector) -> Gcode:
        gcode_new = gcode.copy()
        for i in gcode_new:
            i.move.translate(vector)
        gcode_new.order()
        return gcode_new


    @staticmethod
    def rotate(gcode: Gcode, deg: int) -> Gcode:
        gcode_new = gcode.copy()
        for i in gcode_new:
            i.move.rotate(deg)
        return gcode_new


    @staticmethod
    def scale(gcode: Gcode, scale: int|Vector) -> Gcode:
        gcode_new = gcode.copy()
        for i in gcode_new:
            i.move.scale(scale)
        return gcode_new


    @staticmethod
    def center(gcode: Gcode) -> Vector:
        """
        Get center of bounding box of gcode
        """
        vec1, vec2 = Tools.get_bounding_box(gcode)
        return (vec1 + vec2) / 2


    @staticmethod
    def get_bounding_box(gcode: Gcode) -> tuple[Vector, Vector]:
        """
        Get bounding box of gcode
        
        Returns:
            `tuple` of (low_corner, high_corner)
        """
        
        low_corner = Vector(None, None, None)
        high_corner = Vector(None, None, None)
        
        lower_bound = lambda a,b: a if a < b else b
        upper_bound = lambda a,b: a if a > b else b
        
        for item in gcode:
            high_corner = high_corner.vector_op(item.move.position, upper_bound)
            low_corner = low_corner.vector_op(item.move.position, lower_bound)
            
        return (low_corner.xyz(), high_corner.xyz())


    @staticmethod
    def center_of_mass(gcode: Gcode) -> Vector:
        """
        Calculate the center of mass of the model
        """
        
        total_volume = 0
        sum = Vector.zero()
        sum_e = 0
        
        for block in gcode:
            move = block.move
            sum_e += move.position.E or 0
            if sum_e > 0:
                volume = (move.position.E or 0) + sum_e
                total_volume += volume
                
                sum += move.position * volume
        
        if total_volume < gcode.config.step:
            return Vector()
        
        return (sum / total_volume).xyz()


    # TODO: regenerate_travels:
    # - ensure clean travel trimming
    # FIXME: correct travel begin/end
    @staticmethod
    def regenerate_travels(gcode: Gcode, move_speed = 0):
        
        out_gcode = gcode.new()
        past_item = None
        is_first = True
        e_add = 0
        for item in gcode:
            if is_first:
                out_gcode.append(item.copy())
                if item.meta.get("object") != None:
                    is_first = False
                continue
            
            if item.meta.get("object") == None:
                if past_item is None:
                    out_gcode.append('G10; retract')
                past_item = item.copy()
                e_add += past_item.move.position.E
                past_item.move.position.E = 0
            else:
                if past_item is not None:
                    if move_speed > 0:
                        past_item.move.speed = move_speed
                    out_gcode.append(past_item.copy())
                    past_item.move.position.E = e_add
                    out_gcode.append(past_item.copy())
                    out_gcode.append('G11; unretract')
                    e_add = 0
                past_item = None
                
                out_gcode.append(item.copy())
        if is_first:
            print('Cannot regenerate travels: no objects present in metadata')
        return out_gcode


    @staticmethod
    def add_layer_tags(gcode: Gcode) -> Gcode:
        
        new_gcode = gcode.new()
        
        tag = ';LAYER_CHANGE'
        layer = 0
        for i in gcode:
            meta_layer = i.meta.get('layer', -1)
            if meta_layer != -1 and meta_layer != layer and meta_layer == int(meta_layer):
                layer = meta_layer
                new_gcode.append(tag)
            new_gcode.append(i)
        return new_gcode


    @staticmethod
    def add_move_type_tags(gcode: Gcode) -> Gcode:
                
        new_gcode = gcode.new()
        
        move_type = ''
        for i in gcode:
            meta_type = i.meta.get('type', '')
            if meta_type != move_type:
                move_type = meta_type
                new_gcode.append(MoveTypes.pprint_type.get(meta_type, MoveTypes.pprint_type['']))
            new_gcode.append(i)
        return new_gcode


    @staticmethod
    def remove_thumbnails(gcode: Gcode) -> Gcode:
        """
        Remove embedded thumbnails from gcode
        """
        new_gcode = gcode.new()
        start = -1
        for idx, i in enumerate(gcode):
            if start > -1:
                if i.command == '; THUMBNAIL_BLOCK_END':
                    start = -1
            elif i.command == '; THUMBNAIL_BLOCK_START':
                start = idx
            else:
                new_gcode.append(i)
        
        return new_gcode


    @staticmethod
    def read_thumbnails(gcode: Gcode) -> list[bytes]:
        """
        Get all thumbnails from `Gcode`, ordered as appearing in `Gcode`. For now only `png` format is supported
        
        Example implementation:
        ```
        for idx, thumb in enumerate(Tools.get_thumbnails(gcode)):
            with open(f'thumb{idx}.png', 'wb') as f:
                f.write(thumb)
        ```
        """
        start = -1
        image_text = ''
        images = []
        for idx, i in enumerate(gcode):
            if start > -1:
                if i.command == '; THUMBNAIL_BLOCK_END':
                    start = -1
                    images.append(base64.b64decode(image_text))
                
                text = i.command.removeprefix(';').strip()
                if 'thumbnail end' in text or 'thumbnail begin' in text or len(text) == 0: continue
                image_text += text
            
            if i.command == '; THUMBNAIL_BLOCK_START':
                start = idx
                image_text = ''
        
        return images


    @staticmethod
    def write_thumbnail(gcode: Gcode, data: bytes, width: int, height: int, textwidth = None) -> Gcode:
        """
        Args:
            data: `bytes` - raw png data
            width: `int` - width in pixels
            height: `int` - height in pixels
            textwidth: `int` - custom wrapping width of thumbnail text
                Defaults to 80 below 10kB, otherwise 160
        """
        new = gcode.copy()
        
        THUMB_BLOCK = '\n'\
        '; thumbnail begin {0}x{1} {2}\n'\
        '{3}\n'\
        '; thumbnail end\n'\
        
        text = base64.b64encode(data)
        len_text = len(text)
        if not textwidth: textwidth = 80 if len_text < 10000 else 160
        text = textwrap.indent(textwrap.fill(text.decode('utf-8'), textwidth - 2), '; ')

        thumb = THUMB_BLOCK.format(width, height, len_text, text)
        header_line = Keywords.get_keyword_lineno(20, new, Keywords.KW(r'Slicer\s(.*)\son'))
        if header_line is None:
            new = Tools.write_slicer_header(new)
        new.insert(header_line or 0, thumb)
        return new


    @staticmethod
    def write_slicer_header(gcode: Gcode):
        gcode.insert(0, '; Moonraker requires typing PrusaSlicer - on here')