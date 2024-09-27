import os
# import numpy as np
import re
import json
import time
import math
from gcode_types import *
from gcode_class import Gcode



class Keywords:
    
    CONFIG_START = [("; CONFIG_BLOCK_START", "")]
    CONFIG_END = [("; CONFIG_BLOCK_END", "")]
    
    HEADER_START = [("; HEADER_BLOCK_START", "")]
    HEADER_END = [("; HEADER_BLOCK_END", "")]
    
    EXECUTABLE_START = [("; EXECUTABLE_BLOCK_START", "")]
    EXECUTABLE_END = [("; EXECUTABLE_BLOCK_END", "")]
    
    LAYER_CHANGE_START = [(";BEFORE_LAYER_CHANGE", "")]
    LAYER_CHANGE_END = [(";AFTER_LAYER_CHANGE", ";TYPE:")]
    
    OBJECT_START = [("EXCLUDE_OBJECT_START", ";TYPE:")]
    OBJECT_END = [("EXCLUDE_OBJECT_END", "")]
    
    GCODE_START = [(";AFTER_LAYER_CHANGE", ";TYPE:")]
    GCODE_END = [("EXCLUDE_OBJECT_END", "; EXECUTABLE_BLOCK_END")]
    
    
    def get_keyword_line(line_no: int, blocks: Blocks, keyword: list[tuple[str, str]], seek_limit = 20):
        lines = blocks.b
        for option in keyword:
            if lines[line_no].command.startswith(option[0]):
                if option[1] == "": return True
                
                for nextline in lines[line_no: line_no + seek_limit]:
                    if nextline.command.startswith(option[1]):
                        return True
                
        return False



class GcodeTools:
    
    def __init__(self, gcode: Gcode):
        self.gcode = gcode
        # self.gcode_blocks = self.gcode.blocks
        
        self.start_gcode = None
        self.end_gcode = None
        self.object_gcode = None
        
        self.precision = 0.02


    def read_metadata(self):
        self.metadata = {}
        start_id, end_id = -1, -1
        for id, block in self.gcode.blocks.enum():
        
            if start_id == -1 and Keywords.get_keyword_line(id, self.gcode.blocks, Keywords.CONFIG_START): start_id = id
            if end_id == -1 and Keywords.get_keyword_line(id, self.gcode.blocks, Keywords.CONFIG_END): end_id = id
                
        for gcode in self.gcode.blocks.b[start_id + 1 : end_id]:
            line = gcode.command
            key = line[1:line.find('=')].strip()
            value = line[line.find('=') + 1:].strip()
            self.metadata[key] = value
        return self.metadata


# FIXME: mutable gcode.blocks
    def split(self):
        blocks = self.gcode.blocks
        blocks_bare = Blocks()
        object_gcode = Blocks()
        start_gcode = Blocks()
        end_gcode = Blocks()
        layers = []
        objects_layers = {}
        
        start_id, end_id = -1, -1
        
        for id, block in blocks.enum():
            if start_id == -1 and Keywords.get_keyword_line(id, blocks, Keywords.EXECUTABLE_START): start_id = id
            if end_id == -1 and Keywords.get_keyword_line(id, blocks, Keywords.EXECUTABLE_END): end_id = id
            
            if start_id > 0 and end_id > 0:
                blocks_bare.b = self.gcode.blocks.b[start_id : end_id + 1]
                break
        
        start_id, end_id = -1, -1
        
        for id, block in blocks_bare.enum():
            
            if start_id == -1 and Keywords.get_keyword_line(id, blocks_bare, Keywords.OBJECT_START): start_id = id
            if end_id == -1 and Keywords.get_keyword_line(id, blocks_bare, Keywords.OBJECT_END): end_id = id
            
            if start_id > 0 and end_id > 0:
                object_gcode.b += blocks_bare.b[start_id:end_id].copy()
                object_gcode.append(';OBJECT_SPLIT', id)
                start_id = -1
                end_id = -1
        
        start_id, end_id = -1, -1
        for id, block in blocks_bare.enum():
            
            if start_id == -1 and Keywords.get_keyword_line(id, blocks_bare, Keywords.GCODE_START):
                start_id = id
                start_gcode.b = blocks_bare.b[:start_id]
                print(f'found start gcode at line {id}')
                
            if end_id == -1 and Keywords.get_keyword_line(id, blocks_bare, Keywords.GCODE_END):
                end_id = id
                end_gcode = blocks_bare.b[end_id:]
                print(f'found end gcode at line {id}')
        
        layer = []
        objects_layer = {}
        # FIXME: performance
        # for block in object_gcode:
            
        #     if Keywords.get_keyword_line(id, gcode, Keywords.LAYER_CHANGE_START):
        #         layers.append(layer)
                
        #         for id in objects_layer.keys():
        #             if id not in objects_layers:
        #                 objects_layers[id] = []
        #             objects_layers[id].append(objects_layer[id])
            
        #     elif Keywords.get_keyword_line(id, gcode, Keywords.LAYER_CHANGE_END):
        #         layer = []
        #         objects_layer = {}
        #     else:
        #         layer.append(block)
                
        #         objects_key = block.meta['object'] or 'Travel'
        #         if objects_key not in objects_layer:
        #             objects_layer[objects_key] = []
        #         objects_layer[objects_key].append(block)
        
        # layers.append(layer)
        
        self.start_gcode = start_gcode
        self.end_gcode = end_gcode
        self.layers = layers
        self.objects_layers = objects_layers


    def log_json(self, path='.'):
        print('Logging json...')
        class CustomEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, 'to_dict'):
                    return obj.to_dict()
                return super().default(obj)

        with open(os.path.join(path, 'gcode.json'), 'w') as f:
            f.write(json.dumps(self.gcode.blocks.b, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'objects_layers.json'), 'w') as f:
            f.write(json.dumps(self.objects_layers, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'start_gcode.json'), 'w') as f:
            f.write(json.dumps(self.start_gcode, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'end_gcode.json'), 'w') as f:
            f.write(json.dumps(self.end_gcode, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'metadata.json'), 'w') as f:
            f.write(json.dumps(self.metadata, indent=4))
        print('Json logged')

