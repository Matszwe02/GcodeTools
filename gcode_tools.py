import os
# import numpy as np
import re
import json
import time
import math
from tqdm import tqdm
from gcode_types import *
from gcode_class import Gcode



class Keywords:
    """
    Each keyword is a list of possible commands. Each command is treated as a prefix, so G1 will match any move command, etc.
    """

    class KW:
        def __init__(self, command: str, allow_command = None, block_command = None, offset = 0):
            """
            Offset = -1: offset at allow_command
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
    
    
    def get_keyword_arg(line_no: int, blocks: BlockList, keyword: list[KW], seek_limit = 20):
        
        pass
    
        for offset in range(seek_limit):
            line = line_no - offset
            
            for option in keyword:
                if option.offset != offset and option.offset != -1:
                    continue
                if blocks[line].command.startswith(option.command):
                    
                    if option.allow_command is None and option.block_command is None:
                            return blocks[line].command.removeprefix(option.command)
                    
                    for id, nextline in enumerate(blocks[line + 1 : line + seek_limit]):
                        if option.block_command is not None and nextline.command.startswith(option.block_command):
                            return None
                        if option.allow_command is not None and nextline.command.startswith(option.allow_command):
                            if option.offset == offset or (option.offset == -1 and offset == id):
                                return blocks[line].command.removeprefix(option.command)
                            
                    if option.allow_command is None:
                            return blocks[line].command.removeprefix(option.command)
                
        return None


    def get_keyword_line(line_no: int, blocks: BlockList, keyword: list[KW], seek_limit = 20) -> bool:
        expr = Keywords.get_keyword_arg(line_no, blocks, keyword, seek_limit)
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
    
    WIPE = 'wipe'
    END_WIPE = 'no_wipe'
    
    NO_OBJECT = -1
    
    
    def get_type(line: str):
        string = line.lower()
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
            'wipe_end': MoveTypes.END_WIPE,
            'wipe': MoveTypes.WIPE
            }
        
        for test in type_assign.keys():
            if test in string: return type_assign[test]
        return None
    
    def get_object(id: int, gcode: BlockList):
        
        def sanitize(name: str):
            return ''.join(c if c.isalnum() else '_' for c in name).strip('_')
        
        line = gcode[id].command or ''
        
        is_end = Keywords.get_keyword_line(id, gcode, Keywords.OBJECT_END)
        if is_end:
            return MoveTypes.NO_OBJECT
        
        name = Keywords.get_keyword_arg(id, gcode, Keywords.OBJECT_START)
        if name is not None:
            return sanitize(name)

        return None
        


class GcodeTools:    

    def read_config(gcode: BlockList):
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


    def fill_meta(gcode: BlockList):
        new_gcode = BlockList()
        meta = {'object': None, 'type': None, 'layer': 0.0, 'line': 0}
        was_start = False
        for id, block in tqdm(enumerate(gcode), desc="Analising G-code", unit="line", total=len(gcode)):
            
            line = block.command
            meta['line'] = id
            
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
            new_block.meta = meta.copy()
            new_gcode.append(new_block)
            
        return new_gcode


    def split(gcode: BlockList) -> tuple[BlockList, BlockList, BlockList, dict[BlockList]]:
        """
        returns (start_gcode: BlockList, end_gcode: BlockList, object_gcode: BlockList, objects: dict[BlockList])
        """
        object_gcode = gcode.new()
        start_gcode = gcode.new()
        end_gcode = gcode.new()
        objects: dict[BlockList] = {}
        
        for block in gcode:
            
            if block.meta['type'] == MoveTypes.PRINT_START:
                start_gcode.append(block)
            elif block.meta['type'] == MoveTypes.PRINT_END:
                end_gcode.append(block)
            else:
                object_gcode.append(block)
            
            object = block.meta['object']
            if object not in objects.keys():
                objects[object] = gcode.new()
            
            objects[object].append(block)
        
        return (start_gcode, end_gcode, object_gcode, objects)


    def trim(gcode: BlockList):
        """
        Trims G-code from every command that's not handled by GcodeTools.
        
        Warning: some commands that aren't handled, may be important for the G-code!
        """
        
        gcode_new = gcode.new()
        pos = gcode[0]
        for item in gcode:
            if item.move != pos:
                pos = item.move
                gcode_new.append(item)
        return gcode_new