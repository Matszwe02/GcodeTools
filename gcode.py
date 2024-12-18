from gcode_types import *
from gcode_parser import *



class Gcode(list[Block]):
    
    def __init__(self):
        self.config = Config()
        """
        Configuration of the G-Code computation
        """
        super().__init__()


    def from_file(self, filename: str):
        self = GcodeParser.from_file(self, filename)
        return self
    
    def from_str(self, gcode_str: str):
        self = GcodeParser.from_str(self, gcode_str)
        return self
    
    def write_str(self, verbose = False):
        return GcodeParser.write_str(self, verbose)

    def write_file(self, filename: str, verbose = False):
        return GcodeParser.write_file(self, filename, verbose)



    def get_by_meta(self, meta: str, value = any, value_check = lambda x: False, break_on = lambda x: False):
        gcode = self.new()
        is_none = True
        for i in self:
            i_meta = i.meta.get(meta, None)
            
            if value == any:
                if value_check(i_meta):
                    gcode.g_add(i)
                    is_none = False
            else:
                if i_meta == value:
                    gcode.g_add(i)
                    is_none = False
            
            if break_on(i_meta):
                break
        
        if is_none:
            return None
        return gcode


    def new(self):
        """
        Create an empty G-code list with self's config
        """
        new = Gcode()
        new.config = self.config
        return new


    def g_add(self, gcode: Block|str, index: int = -1, data:BlockData|None=None, meta: dict|None=None):
        """Appends gcode block to Gcode.\n\n`gcode`: Block or gcode str.\n\ndefault `index` -1: append to the end"""
        
        idx = index if index < len(self) else -1
        
        if type(gcode) == str:
            if len(self) == 0:
                move = Move()
                if data is None: data = BlockData()
            else:
                last_index = -1
                if idx > 0:
                    last_index = idx-1
                elif idx == 0:
                    last_index = 0
                
                move = self[last_index].move
                if data is None: data = self[last_index].block_data
                if meta is None: meta = self[last_index].meta
            
            if meta is None: meta = {}
            gcode_obj = Block(move, gcode, True, data, meta)
            
        else:
            gcode_obj = gcode.copy()
        if idx == -1:
            self.append(gcode_obj)
            return
        self.insert(index, gcode_obj)


    def copy(self):
        gcode = self.new()
        
        for i in self:
            gcode.g_add(i.copy())
        
        return gcode