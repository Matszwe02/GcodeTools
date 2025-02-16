from GcodeTools.gcode_types import *


class Gcode(list[Block]):
    
    def __init__(self):
        self.config = Config()
        "Configuration of the G-Code computation"
        self.ordered = False
        super().__init__()


    def __get_parser__(self):
        from GcodeTools.gcode_parser import GcodeParser
        return GcodeParser


    def __get_meta_provider__(self):
        from GcodeTools.gcode_tools import GcodeTools
        meta_provider = GcodeTools.fill_meta
        return meta_provider


    def __fill_meta__(self, meta_provider: typing.Callable = None):
        """
            meta_provider: `Callable` - method to fill in meta
                Default `None` = `GcodeTools.fill_meta()`
        """
        if meta_provider is None:
            meta_provider = self.__get_meta_provider__()
        meta_provider(self)


    def try_order(self):
        if not self.ordered:
            self.order()
            self.ordered = True


    def from_str(self, gcode_str: str, data = BlockData(), progress_callback: typing.Callable|None = None, meta_provider: typing.Callable = None) -> 'Gcode':
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            gcode_str: `str` - string that will be parsed into `Gcode`
            data: `BlockData` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
            meta_provider: `Callable` - method to fill in meta
                Default `None` = `GcodeTools.fill_meta()`
        """
        self: Gcode = self.__get_parser__().from_str(self, gcode_str, data, progress_callback)
        self.order()
        self.__fill_meta__(meta_provider)
        return self

    def from_file(self, filename: str, data = BlockData(), progress_callback: typing.Callable|None = None, meta_provider: typing.Callable = None) -> 'Gcode':
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            filename: `str` - filename containing g-code to be parsed
            data: `BlockData` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
            meta_provider: `Callable` - method to fill in meta
                Default `None` = `GcodeTools.fill_meta()`
        """
        self: Gcode = self.__get_parser__().from_file(self, filename, data, progress_callback)
        self.order()
        self.__fill_meta__(meta_provider)
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
        self.try_order()
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
        self.try_order()
        return self.__get_parser__().write_file(self, filename, verbose, progress_callback)


    def new(self):
        """
        Create an empty G-code list with self's config
        """
        new = Gcode()
        new.config = self.config
        return new


    def g_add(self, gcode: Block|str, index: int = -1, data:BlockData|None=None, meta: dict|None=None, compile = False):
        """
        Appends a G-code block to the `Gcode`.

        Args:
            gcode: `Block`|`str`
            index: `int`
                Default index = `-1` => append to the end of `Gcode`
            data: `BlockData`
            meta: `dict`
            compile: `bool` - when `gcode` is `str`, it can be compiled into a `Block` instead of being a command
        """
        self.ordered = False
        
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
            if compile:
                parser = self.__get_parser__()
                speed = self[max(idx, 0) - 1].move.speed if len(self) else None
                position = self[max(idx, 0) - 1].move.position if len(self) else Vector()
                gcode_objs = parser._parse_line(parser.ParserData(CoordSystem(speed=speed, position=position), Block(None, move, gcode, True, data, meta)))
                for idx, obj in enumerate(gcode_objs):
                    if idx == -1:
                        self.append(obj.block)
                    else:
                        self.insert(index + idx, obj.block)
                return
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
        self.ordered = False
        for i in self:
            i.unlink()


    def __iter__(self):
        self.ordered = False
        return super().__iter__()

    def __getitem__(self, i):
        self.ordered = False
        return super().__getitem__(i)


    def copy(self):
        gcode = self.new()
        
        for i in self:
            gcode.g_add(i.copy())
        
        return gcode
    
    list