import os
# import numpy as np
import re
import json
import time
import math
from tqdm import tqdm
from gcode_types import *
from gcode_loader import *


meta_initial = {'object': None, 'type': None, 'layer': 0.0}

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
    
    LAYER_CHANGE_START = [KW(";LAYER_CHANGE"), KW(";LAYER:", ";TYPE:")]
    LAYER_CHANGE_END = [KW(";TYPE:"), KW(";TYPE:")]
    
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
    
    
    def get_type(line: str):
        string = line.lower()
        if not string.startswith(';type:'): return None
        
        type_assign = {
            'skirt': MoveTypes.SKIRT,
            'external': MoveTypes.EXTERNAL_PERIMETER,
            'overhang': MoveTypes.OVERHANG_PERIMETER,
            'perimeter': MoveTypes.INTERNAL_PERIMETER,
            'inner': MoveTypes.INTERNAL_PERIMETER,
            'outer': MoveTypes.EXTERNAL_PERIMETER,
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


    def fill_meta(gcode: Gcode):
        new_gcode = Gcode()
        meta = meta_initial
        was_start = False
        for id, block in tqdm(enumerate(gcode), desc="Analising G-code", unit="line", total=len(gcode)):
            
            line = block.command
            
            move_type = MoveTypes.get_type(line)
            if move_type is not None: meta['type'] = move_type
            
            move_object = MoveTypes.get_object(id, gcode)
            if move_object == MoveTypes.NO_OBJECT: meta["object"] = None
            elif move_object is not None: meta['object'] = move_object
            
            
            if Keywords.get_keyword_line(id, gcode, Keywords.LAYER_CHANGE_START):
                meta['layer'] = int(meta['layer']) + 0.5
            if meta['layer'] != int(meta['layer']) and Keywords.get_keyword_line(id, gcode, Keywords.LAYER_CHANGE_END):
                meta['layer'] = int(meta['layer']) + 1
            
            if not was_start and Keywords.get_keyword_line(id, gcode, Keywords.GCODE_START):
                meta['type'] = MoveTypes.PRINT_START
                was_start = True
            if Keywords.get_keyword_line(id, gcode, Keywords.GCODE_END):
                meta['type'] = MoveTypes.PRINT_END
            
            new_block = block.copy()
            new_block.meta = json.loads(json.dumps(meta))
            new_gcode.append(new_block)
            
        return new_gcode


    def split(gcode: Gcode) -> tuple[Gcode, Gcode, Gcode, dict[Gcode]]:
        """
        returns (`start_gcode`: Gcode, `end_gcode`: Gcode, `object_gcode`: Gcode, `objects`: dict[Gcode])
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
        Trims G-code from every command that's not handled by GcodeTools.
        
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
    
    
    
    def get_bounding_cube(gcode: Gcode) -> tuple[Vector, Vector]:
        """
        Get bounding cube of gcode. Returns a tuple of (low_corner, high_corner)
        """
        
        low_corner = Vector(None, None, None)
        high_corner = Vector(None, None, None)
        
        lower_bound = lambda a,b: a if a < b else b
        upper_bound = lambda a,b: a if a > b else b
        
        for item in gcode:
            high_corner = high_corner.vector_op(item.move.position, upper_bound)
            low_corner = low_corner.vector_op(item.move.position, lower_bound)
            
        return (low_corner, high_corner)



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

