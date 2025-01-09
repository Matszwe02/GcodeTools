from gcode_types import *
from typing import Callable, Any



class Gcode(list[Block]):
    
    def __init__(self):
        self.config = Config()
        """
        Configuration of the G-Code computation
        """
        super().__init__()


    def __get_parser__(self):
        from gcode_parser import GcodeParser
        return GcodeParser


    def from_str(self, gcode_str: str, data = BlockData(), progress_callback: typing.Callable|None = None) -> 'Gcode':
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            gcode_str: `str` - string that will be parsed into `Gcode`
            data: `BlockData` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
        """
        self:'Gcode' = self.__get_parser__().from_str(self, gcode_str, data, progress_callback)
        self.order()
        return self

    def from_file(self, filename: str, data = BlockData(), progress_callback: typing.Callable|None = None) -> 'Gcode':
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            filename: `str` - filename containing g-code to be parsed
            data: `BlockData` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
        """
        self:'Gcode' = self.__get_parser__().from_file(self, filename, data, progress_callback)
        self.order()
        return self

    def write_str(self, verbose = False, progress_callback: typing.Callable|None = None):
        """
        Write G-Code as a string
        
        Args:
            gcode: `Gcode`
            verbose: `bool` - include Block's metadata for each line. Warning: takes up much more time and space
            progress_callback: `Callable(current: int, total: int)`
        Returns:
            str
        """
        self.order() # TODO: detect need for ordering, skip already ordered `Gcode`
        return self.__get_parser__().write_str(self, verbose, progress_callback)

    def write_file(self, filename: str, verbose = False, progress_callback: typing.Callable|None = None):
        """
        Write G-Code as a string into a file
        
        Args:
            gcode: `Gcode`
            filename: `str` of output path
            verbose: `bool` - include Block's metadata for each line. Warning: takes up much more time and space
            progress_callback: `Callable(current: int, total: int)`
        """
        self.order() # TODO: detect need for ordering, skip already ordered `Gcode`
        return self.__get_parser__().write_file(self, filename, verbose, progress_callback)


    def get_by_meta(self, meta: str, value = None, value_check: Callable[[Any], bool]|None = None, break_on = lambda x: False):
        gcode = self.new()
        is_none = True
        for i in self:
            i_meta = i.meta.get(meta, None)
            
            if value_check is None:
                if i_meta == value:
                    gcode.g_add(i)
                    is_none = False
            else:
                if value_check(i_meta):
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
        """
        Appends a G-code block to the `Gcode`.

        Args:
            gcode: `Block`|`str`
            index: `int`
                Default index = `-1` => append to the end of `Gcode`
            data: `BlockData`
            meta: `dict`
        """
        
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
                
                move = self[last_index].move.duplicate()
                if data is None: data = self[last_index].block_data
                if meta is None: meta = self[last_index].meta
            
            if meta is None: meta = {}
            gcode_obj = Block(None, move, gcode, True, data, meta)
            
        else:
            gcode_obj = gcode.copy()
            if meta is not None:
                gcode_obj.meta = json.loads(json.dumps(meta))
            if data is not None:
                gcode_obj.block_data = data.copy()
        if idx == -1:
            self.append(gcode_obj)
            return
        self.insert(index, gcode_obj)


    def order(self):
        """
        Order `Blocks` inside `Gcode`. Used to create position reference inside each `Block`
        """
        for idx, i in enumerate(self):
            i.prev = self[idx-1] if idx > 0 else None
            i.sync()


    def unlink(self):
        """
        Inverse of `order`. Used to make object serializable
        """
        for i in self:
            i.unlink()


    def copy(self):
        gcode = self.new()
        
        for i in self:
            gcode.g_add(i.copy())
        
        return gcode