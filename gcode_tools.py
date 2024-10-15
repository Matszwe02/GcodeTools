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
    """List of possible commands. Each command is treated as a prefix, so G1 will match any move command, etc.
    
    Each element is a tuple of (
    
        command,
    
        command to be followed by within seek_limit,
    
        command that breaks seek_limit
    
    )
    """
    
    CONFIG_START = [("; CONFIG_BLOCK_START", "", "")]
    CONFIG_END = [("; CONFIG_BLOCK_END", "", "")]
    
    HEADER_START = [("; HEADER_BLOCK_START", "", "")]
    HEADER_END = [("; HEADER_BLOCK_END", "", "")]
    
    EXECUTABLE_START = [("; EXECUTABLE_BLOCK_START", "", ""), (";TYPE:", "", ""), (";Generated with Cura_SteamEngine", "", "")]
    EXECUTABLE_END = [("; EXECUTABLE_BLOCK_END", "", "")]
    
    LAYER_CHANGE_START = [(";LAYER_CHANGE", "", ""), (";LAYER:", ";TYPE:", "")]
    LAYER_CHANGE_END = [(";TYPE:", "", ""), (";TYPE:", "", "")]
    
    GCODE_START = [(";TYPE:", "", ""), (";Generated with Cura_SteamEngine", "", "")]
    GCODE_END = [("EXCLUDE_OBJECT_END", "; EXECUTABLE_BLOCK_END", ""), (";TIME_ELAPSED:", ";End of Gcode", ";TIME_ELAPSED:")]
    
    OBJECT_START = [("; printing object", "", "EXCLUDE_OBJECT_START"), ("EXCLUDE_OBJECT_START", "", ""), (";MESH:", "", ""), ("M486 S", "", "")]
    OBJECT_END = [("; stop printing object", "", "EXCLUDE_OBJECT_END"), ("EXCLUDE_OBJECT_END", "", ""), (";MESH:NONMESH", "", ""), ("M486 S-1", "", "")]
    
    
    def get_keyword_line(line_no: int, blocks: BlockList, keyword: list[tuple[str, str, str]], seek_limit = 20):

        for option in keyword:
            if blocks[line_no].command.startswith(option[0]):
                if option[1] == "": return True
                
                for nextline in blocks[line_no + 1 : line_no + seek_limit]:
                    if option[2] != "" and nextline.command.startswith(option[2]):
                        return False
                    if nextline.command.startswith(option[1]):
                        return True
                
        return False



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
        line = gcode[id].command or ''
        string = line.lower()
        
        is_end = Keywords.get_keyword_line(id, gcode, Keywords.OBJECT_END)
        if is_end: return MoveTypes.NO_OBJECT
        
        is_start = Keywords.get_keyword_line(id, gcode, Keywords.OBJECT_START)
        
        if is_start:
            line = gcode[id].command
            name = line.removeprefix('; printing object').removeprefix(';MESH:').removeprefix('EXCLUDE_OBJECT_START NAME=').removeprefix('M486 S')
            return name.strip().replace(' ', '_').replace("'", '')

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


    def split(gcode: BlockList):
        """
        returns (start_gcode: BlockList, end_gcode: BlockList, layers: list[BlockList], objects_layers: dict[list[BlockList]])
        """
        blocks_bare = gcode.new()
        object_gcode = gcode.new()
        start_gcode = gcode.new()
        end_gcode = gcode.new()
        layers = gcode.new()
        objects_layers: dict[BlockList] = {}
        
        start_id, end_id = -1, -1
        
        for id, block in enumerate(gcode):
            if start_id == -1 and Keywords.get_keyword_line(id, gcode, Keywords.EXECUTABLE_START): start_id = id
            if end_id == -1 and Keywords.get_keyword_line(id, gcode, Keywords.EXECUTABLE_END): end_id = id
            
            if start_id > 0 and end_id > 0:
                blocks_bare = gcode[start_id : end_id + 1]
                break
        
        start_id, end_id = -1, -1
        for id, block in enumerate(blocks_bare):
            
            if start_id == -1 and Keywords.get_keyword_line(id, blocks_bare, Keywords.GCODE_START):
                start_id = id
                start_gcode = blocks_bare[:start_id]
                print(f'found start gcode at line {id}')
                
            if end_id == -1 and Keywords.get_keyword_line(id, blocks_bare, Keywords.GCODE_END):
                end_id = id
                end_gcode = blocks_bare[end_id:]
                print(f'found end gcode at line {id}')
        
        layer: BlockList = []
        objects_layer = {}
        
        # TODO: Combined enumeration
        
        for id, block in enumerate(blocks_bare):
            
            if Keywords.get_keyword_line(id, blocks_bare, Keywords.LAYER_CHANGE_START):
                layers.append(layer)
                
                for layer_block in layer:
                    obj_name = layer_block.meta.get('object', None)
                    if obj_name is not None:
                        for id in objects_layer.keys():
                            if obj_name not in objects_layers and obj_name is not None:
                                objects_layers[obj_name] = BlockList()
                            objects_layers[obj_name] = layer.copy()
                        # objects_layers[id].append(objects_layer[id])
            
            elif Keywords.get_keyword_line(id, blocks_bare, Keywords.LAYER_CHANGE_END):
                layer = []
                objects_layer = {}
            else:
                layer.append(block)
                
                try:
                    objects_key = block.meta['object'] or 'Travel'
                except:
                    objects_key = 'Travel'
                
                if objects_key not in objects_layer:
                    objects_layer[objects_key] = BlockList()
                objects_layer[objects_key].append(block)
        
        layers.append(layer)
        
        return (start_gcode, end_gcode, layers, objects_layers)
