import os
# import numpy as np
import re
import json
import time
import math
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
    
    EXECUTABLE_START = [("; EXECUTABLE_BLOCK_START", "", "")]
    EXECUTABLE_END = [("; EXECUTABLE_BLOCK_END", "", "")]
    
    LAYER_CHANGE_START = [(";BEFORE_LAYER_CHANGE", "", "")]
    LAYER_CHANGE_END = [(";AFTER_LAYER_CHANGE", ";TYPE:", "")]
    
    # OBJECT_START = [("EXCLUDE_OBJECT_START", ";TYPE:", "")]
    # OBJECT_END = [("EXCLUDE_OBJECT_END", "", "")]
    
    GCODE_START = [(";AFTER_LAYER_CHANGE", ";TYPE:", "")]
    GCODE_END = [("EXCLUDE_OBJECT_END", "; EXECUTABLE_BLOCK_END", "")]
    
    
    def get_keyword_line(line_no: int, blocks: BlockList, keyword: list[tuple[str, str, str]], seek_limit = 20):

        for option in keyword:
            if blocks[line_no].command.startswith(option[0]):
                if option[1] == "": return True
                
                for nextline in blocks[line_no: line_no + seek_limit]:
                    if option[2] != "" and nextline.command.startswith(option[2]):
                        return False
                    if nextline.command.startswith(option[1]):
                        return True
                
        return False



class GcodeTools:

    def read_metadata(gcode: BlockList):
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


    def split(gcode: BlockList):
        """
        returns (start_gcode: BlockList, end_gcode: BlockList, layers: list[BlockList], objects_layers: dict[list[BlockList]])
        """
        blocks_bare = BlockList()
        object_gcode = BlockList()
        start_gcode = BlockList()
        end_gcode = BlockList()
        layers = BlockList()
        objects_layers: dict[BlockList] = {}
        
        start_id, end_id = -1, -1
        
        for id, block in enumerate(gcode):
            if start_id == -1 and Keywords.get_keyword_line(id, gcode, Keywords.EXECUTABLE_START): start_id = id
            if end_id == -1 and Keywords.get_keyword_line(id, gcode, Keywords.EXECUTABLE_END): end_id = id
            
            if start_id > 0 and end_id > 0:
                blocks_bare = gcode[start_id : end_id + 1]
                break
        
        start_id, end_id = -1, -1
        
        # for id, block in enumerate(blocks_bare):
            
            # if start_id == -1 and Keywords.get_keyword_line(id, blocks_bare, Keywords.OBJECT_START): start_id = id
            # if end_id == -1 and Keywords.get_keyword_line(id, blocks_bare, Keywords.OBJECT_END): end_id = id
            
            # if start_id > 0 and end_id > 0:
            # if block.meta.get('object', None) is not None:
            #     object_gcode += blocks_bare[start_id:end_id].copy()
            #     object_gcode.g_add(';OBJECT_SPLIT', id)
            #     start_id = -1
            #     end_id = -1
        
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
                
                # TODO: Better meta
                try:
                    objects_key = block.meta['object'] or 'Travel'
                except:
                    objects_key = 'Travel'
                
                if objects_key not in objects_layer:
                    objects_layer[objects_key] = BlockList()
                objects_layer[objects_key].append(block)
        
        layers.append(layer)
        
        return (start_gcode, end_gcode, layers, objects_layers)
