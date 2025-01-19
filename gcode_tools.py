import json
from gcode_types import *
from gcode import Gcode
import base64
import textwrap

meta_initial = {'object': None, 'type': None, 'layer': 0}

class Keywords:
    """
    Each `keyword` is a list of possible commands. Each `command` is treated as a prefix, so G1 will match any move command, etc.
    """

    class KW:
        def __init__(self, command: str, allow_command = None, block_command = None, offset = 0):
            """
            `Offset` = -1: offset at `allow_command`
            """
            self.command = command
            self.allow_command = allow_command
            self.block_command = block_command
            self.offset = offset
    
    
    CONFIG_START = [KW("; CONFIG_BLOCK_START")]
    CONFIG_END = [KW("; CONFIG_BLOCK_END")]
    
    HEADER_START = [KW("; HEADER_BLOCK_START")]
    HEADER_END = [KW("; HEADER_BLOCK_END")]
    
    EXECUTABLE_START = [KW("; EXECUTABLE_BLOCK_START"), KW(";TYPE:"), KW(";Generated with Cura_SteamEngine")]
    EXECUTABLE_END = [KW("; EXECUTABLE_BLOCK_END")]
    
    LAYER_CHANGE = [KW(";LAYER_CHANGE"), KW(";LAYER:", ";TYPE:")]
    
    GCODE_START = [KW(";TYPE:"), KW(";Generated with Cura_SteamEngine")]
    GCODE_END = [KW("EXCLUDE_OBJECT_END", "; EXECUTABLE_BLOCK_END"), KW(";TIME_ELAPSED:", ";End of Gcode", ";TIME_ELAPSED:"), KW(";TYPE:Custom", "; filament used")]
    
    OBJECT_START = [KW("; printing object", None, "EXCLUDE_OBJECT_START NAME="), KW("EXCLUDE_OBJECT_START NAME=", ";WIDTH:", None, -1), KW(";MESH:"), KW("M486 S")]
    OBJECT_END = [KW("; stop printing object", None, "EXCLUDE_OBJECT_END"), KW("EXCLUDE_OBJECT_END"), KW(";MESH:NONMESH"), KW("M486 S-1")]
    # FIXME: Edge case scenarios, split travel moves perfectly
    # TODO: travel trimming, recalculation, preserve last travel vector at object
    
    
    def get_keyword_arg(line_no: int, gcode: Gcode, keyword: list[KW], seek_limit = 20):
        
        pass
    
        for offset in range(seek_limit):
            line = line_no - offset
            
            for option in keyword:
                if option.offset != offset and option.offset != -1:
                    continue
                if gcode[line].command.startswith(option.command):
                    
                    if option.allow_command is None and option.block_command is None:
                            return gcode[line].command.removeprefix(option.command)
                    
                    for id, nextline in enumerate(gcode[line + 1 : line + seek_limit]):
                        if option.block_command is not None and nextline.command.startswith(option.block_command):
                            return None
                        if option.allow_command is not None and nextline.command.startswith(option.allow_command):
                            if option.offset == offset or (option.offset == -1 and offset == id):
                                return gcode[line].command.removeprefix(option.command)
                            
                    if option.allow_command is None:
                            return gcode[line].command.removeprefix(option.command)
                
        return None


    def get_keyword_line(line_no: int, gcode: Gcode, keyword: list[KW], seek_limit = 20) -> bool:
        expr = Keywords.get_keyword_arg(line_no, gcode, keyword, seek_limit)
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
    
    # TODO: wipe meta
    WIPE = 'wipe'
    END_WIPE = 'no_wipe'
    
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
    
    
    def get_type(line: str):
        string = line.lower()
        # if not string.startswith(';type:'): return None
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
            # 'wipe_end': MoveTypes.END_WIPE,
            # 'wipe': MoveTypes.WIPE,
            }
        
        for test in type_assign.keys():
            if test in string: return type_assign[test]
        return None
    
    def get_object(id: int, gcode: Gcode):
        
        def sanitize(name: str):
            return ''.join(c if c.isalnum() else '_' for c in name).strip('_')
        
        is_end = Keywords.get_keyword_line(id, gcode, Keywords.OBJECT_END)
        if is_end:
            return MoveTypes.NO_OBJECT
        
        name = Keywords.get_keyword_arg(id, gcode, Keywords.OBJECT_START)
        if name is not None:
            return sanitize(name)

        return None
        


class GcodeTools:

    def read_config(gcode: Gcode):
        """
        Read slicer's config from `Gcode`
        """
        metadata = {}
        start_id, end_id = -1, -1
        for id, block in enumerate(gcode):
        
            if start_id == -1 and Keywords.get_keyword_line(id, gcode, Keywords.CONFIG_START): start_id = id
            if end_id == -1 and Keywords.get_keyword_line(id, gcode, Keywords.CONFIG_END): end_id = id
        
        if start_id == -1 or end_id == -1: return None
        
        for block in gcode[start_id + 1 : end_id]:
            line = block.command
            key = line[1:line.find('=')].strip()
            value = line[line.find('=') + 1:].strip()
            metadata[key] = value
        
        return metadata


    def fill_meta(gcode: Gcode, progress_callback: typing.Callable|None = None):
        """
        Args:
            progress_callback: `Callable(current: int, total: int)`
        passed `Gcode` gets modified so meta is added into it
        """
        meta = meta_initial
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


    def translate(gcode: Gcode, vector: Vector) -> Gcode:
        gcode_new = gcode.copy()
        for i in gcode_new:
            i.move.translate(vector)
        return gcode_new


    def rotate(gcode: Gcode, deg: int) -> Gcode:
        gcode_new = gcode.copy()
        for i in gcode_new:
            i.move.rotate(deg)
        return gcode_new


    def scale(gcode: Gcode, scale: int|Vector) -> Gcode:
        gcode_new = gcode.copy()
        for i in gcode_new:
            i.move.scale(scale)
        return gcode_new


    def center(gcode: Gcode) -> Vector:
        """
        Get center of bounding cube of gcode
        """
        vec1, vec2 = GcodeTools.get_bounding_cube(gcode)
        return (vec1 + vec2) / 2


    def get_bounding_cube(gcode: Gcode) -> tuple[Vector, Vector]:
        """
        Get bounding cube of gcode
        
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
            
        return (low_corner, high_corner)


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
                    out_gcode.g_add('G10; retract')
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
                    out_gcode.g_add('G11; unretract')
                    e_add = 0
                past_item = None
                
                out_gcode.append(item.copy())
        if is_first:
            print('Cannot regenerate travels: no objects present in metadata')
        return out_gcode


    def add_layer_tags(gcode: Gcode) -> Gcode:
        
        new_gcode = gcode.new()
        
        tag = ';LAYER_CHANGE'
        layer = 0
        for i in gcode:
            meta_layer = i.meta.get('layer', -1)
            if meta_layer != -1 and meta_layer != layer and meta_layer == int(meta_layer):
                layer = meta_layer
                new_gcode.g_add(tag)
            new_gcode.g_add(i)
        return new_gcode


    def add_move_type_tags(gcode: Gcode) -> Gcode:
                
        new_gcode = gcode.new()
        
        move_type = ''
        for i in gcode:
            meta_type = i.meta.get('type', '')
            if meta_type != move_type:
                move_type = meta_type
                new_gcode.g_add(MoveTypes.pprint_type.get(meta_type, MoveTypes.pprint_type['']))
            new_gcode.g_add(i)
        return new_gcode


    def get_thumbnails(gcode: Gcode) -> list[bytes]:
        """
        Get all thumbnails from `Gcode`, ordered as appearing in `Gcode`. For now only `png` format is supported
        
        Example implementation:
        ```py
        for idx, thumb in enumerate(GcodeTools.get_thumbnails(gcode)):
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


    def generate_thumbnail(gcode: Gcode, data: bytes, width: int, height: int, textwidth = 80) -> Gcode:
        """
        Args:
            data: `bytes` - raw png data
            width: `int` - width in pixels
            height: `int` - height in pixels
            textwidth: `int` - custom wrapping width of thumbnail text
                Recommended to set `>=160` on large thumbnails
        """
        new = gcode.copy()
        
        THUMB_BLOCK = '\n'\
        '; THUMBNAIL_BLOCK_START\n'\
        '; thumbnail begin {0}x{1} {2}\n'\
        '{3}\n'\
        '; thumbnail end\n'\
        '; THUMBNAIL_BLOCK_END\n'
        
        text = base64.b64encode(data)
        len_text = len(text)
        text = textwrap.indent(textwrap.fill(text.decode('utf-8'), textwidth - 2), '; ')

        thumb = THUMB_BLOCK.format(width, height, len_text, text)
        block = Block(command=thumb, emit_command=True)
        new.g_add(block, 0)
        return new