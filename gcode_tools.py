import os
# import numpy as np
import re
import json
import time
import math
from gcode_types import *
from gcode_class import Gcode



class GcodeTools:
    
    def __init__(self, gcode: Gcode):
        self.gcode = gcode
        self.gcode_blocks = self.gcode.gcode_blocks
        
        self.start_gcode = None
        self.end_gcode = None
        self.object_gcode = None
        
        self.precision = 0.02


    def read_metadata(self):
        self.metadata = {}
        start_id, end_id = -1, -1
        for id, block in enumerate(self.gcode.gcode_blocks):
            if block.command == "; CONFIG_BLOCK_START":
                start_id = id
            if block.command == "; CONFIG_BLOCK_END":
                end_id = id
                
        for gcode in self.gcode.gcode_blocks[start_id + 1 : end_id]:
            line = gcode.command
            key = line[1:line.find('=')].strip()
            value = line[line.find('=') + 1:].strip()
            self.metadata[key] = value
        return self.metadata


    def split(self):
        gcode = self.gcode.gcode_blocks
        object_gcode = []
        start_gcode = []
        end_gcode = []
        layers = []
        objects_layers = {}
        
        start_id, end_id = -1, -1
        
        for id, block in enumerate(gcode):
            if block.command == "; EXECUTABLE_BLOCK_START":
                start_id = id + 1
            if block.command == "; EXECUTABLE_BLOCK_END":
                end_id = id
            if start_id > 0 and end_id > 0:
                gcode = gcode[start_id:end_id]
                break
        
        start_id, end_id = -1, -1
        for id, block in enumerate(gcode):
            if ";WIDTH:" in block.command and start_id == -1:
                start_id = id + 1
            if block.command == "; filament end gcode":
                end_id = id
            if start_id > 0 and end_id > 0:
                object_gcode = gcode[start_id:end_id]
                
            
        start_id, end_id = -1, -1
        for id, block in enumerate(gcode):
            if block.command == "; filament end gcode":
                end_id = id
            if block.command == "; Filament gcode":
                start_id = id + 1
            if start_id > 0 and end_id > 0:
                start_gcode = gcode[:start_id]
                end_gcode = gcode[end_id:]
            
                
        layer = []
        objects_layer = {}
        for block in object_gcode:
            if block.command == ";BEFORE_LAYER_CHANGE":
                layers.append(layer)
                # objects_layers.append(objects_layer)
                
                for id in objects_layer.keys():
                    if id not in objects_layers:
                        objects_layers[id] = []
                    objects_layers[id].append(objects_layer[id])
                
            elif block.command == ";AFTER_LAYER_CHANGE":
                layer = []
                objects_layer = {}
            else:
                layer.append(block)
                
                objects_key = block.meta['object'] or 'Travel'
                if objects_key not in objects_layer:
                    objects_layer[objects_key] = []
                objects_layer[objects_key].append(block)
        
        layers.append(layer)
        
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
            f.write(json.dumps(self.gcode.gcode_blocks, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'objects_layers.json'), 'w') as f:
            f.write(json.dumps(self.objects_layers, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'start_gcode.json'), 'w') as f:
            f.write(json.dumps(self.start_gcode, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'end_gcode.json'), 'w') as f:
            f.write(json.dumps(self.end_gcode, indent=4, cls=CustomEncoder))
            
        with open(os.path.join(path, 'metadata.json'), 'w') as f:
            f.write(json.dumps(self.metadata, indent=4))
        print('Json logged')

