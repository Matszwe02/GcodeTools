from GcodeTools.gcode_types import *


class Gcode(list[Block]):
    
    def __init__(self, filename = None, *, gcode_str = None, config = Config()):
        """
        Initializes a `Gcode` object.

        Args:
            filename: `str` - Path to a G-code file to load.
            gcode_str: `str` - A string containing G-code to parse.
            config: `Config` - Printer configuration for G-code.
        """
        self.config = config
        self.ordered = False
        self.header = ''
        self.footer = ''
        super().__init__()
        if filename:
            self.from_file(filename)
        elif gcode_str:
            self.from_str(gcode_str)


    def __get_parser__(self):
        from GcodeTools.gcode_parser import GcodeParser
        return GcodeParser

    def __get_meta_parser__(self):
        from GcodeTools.gcode_parser import MetaParser
        return MetaParser


    def __fill_meta__(self):
        self.__get_meta_parser__().fill_meta(self)


    def try_order(self):
        if not self.ordered:
            self.order()
            self.ordered = True


    def from_str(self, gcode_str: str, data = BlockData(), progress_callback: typing.Callable|None = None) -> 'Gcode':
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            gcode_str: `str` - string that will be parsed into `Gcode`
            data: `BlockData` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
        """
        self: Gcode = self.__get_parser__().from_str(self, gcode_str, data, progress_callback)
        self.order()
        self.__fill_meta__()
        return self

    def from_file(self, filename: str, data = BlockData(), progress_callback: typing.Callable|None = None) -> 'Gcode':
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            filename: `str` - filename containing g-code to be parsed
            data: `BlockData` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
        """
        self: Gcode = self.__get_parser__().from_file(self, filename, data, progress_callback)
        self.order()
        self.__fill_meta__()
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


    def __add_block__(self, block: Block, index: int):
        """The same as `Gcode.insert()`"""

        self.ordered = False
        idx = index if index < len(self) else -1
        block_obj = block.copy()
        if idx == -1:
            super().append(block_obj)
        else:
            super().insert(index, block_obj)


    def __add_str__(self, gcode: str, index: int = -1, data:BlockData|None=None, compile = False):
        """
        The same as `Gcode.insert()`
        
        For advanced use - `Block` can be build from its params

        Args:
            gcode: `str`
            index: `int`
                Default index = `-1` => append to the end of `Gcode`
            data: `BlockData`
            compile: `bool` - compile `Block` using `CoordSystem` and `GcodeParser` instead of only putting command into a block.
                - compilation doesn't propagate forward, i.e. putting `M106` only affects newly created `Block`.
        """
        self.ordered = False
        
        idx = index if index < len(self) else -1
        
        if len(self) == 0:
            if data is None: data = BlockData(config=self.config)
        else:
            last_index = idx - 1 * (idx > 0)
            
            if data is None: data = self[last_index].block_data
        
        if compile:
            parser = self.__get_parser__()
            position = self[max(idx, 0) - 1].block_data.position if len(self) else Vector()
            gcode_objs = parser._parse_line(parser.ParserData(CoordSystem(position=position), Block(None, gcode, True, data, self.config)))
            for idx, obj in enumerate(gcode_objs):
                if idx == -1:
                    super().append(obj.block)
                else:
                    super().insert(index + idx, obj.block)
            return
        gcode_obj = Block(None, gcode, True, data, self.config)
        
        if idx == -1:
            super().append(gcode_obj)
            return
        super().insert(index, gcode_obj)


    def order(self):
        """
        Order `Blocks` inside `Gcode`. Used to create position reference inside each `Block`
        """
        i = 0
        while i < len(self):
            block: Block = self[i].unlink()
            block.prev = self[i - 1] if i > 0 else None
            i += 1
            block.sync()


    def unlink(self):
        """
        Inverse of `order`. Used to make object serializable
        """
        self.ordered = False
        for i in self:
            i.unlink()


    def __super__(self):
        return super()


    def __iter__(self):
        self.ordered = False
        return super().__iter__()


    def __getitem__(self, key):
        """Returns a shallow copy of `Gcode` or `Block`"""
        self.ordered = False
        if isinstance(key, slice):
            new_gcode = self.new()
            for block in super().__getitem__(key):
                new_gcode.__super__().append(block)
            return new_gcode
        else:
            return super().__getitem__(key)


    def __len__(self):
        return super().__len__()


    def __add__(self, other):
        new_gcode = self.new()
        new_gcode.extend(self)
        new_gcode.extend(other)
        new_gcode.ordered = False
        return new_gcode


    def insert(self, index: int, value: Block|str):
        if type(value) == str:
            self.__add_str__(value, index)
        else:
            self.__add_block__(value, index)


    def append(self, value: Block|str):
        self.insert(-1, value)


    def extend(self, iterable: typing.Iterable[Block|str]):
        for item in iterable:
            self.append(item)


    def copy(self):
        gcode = self.new()
        gcode.header = self.header
        gcode.footer = self.footer
        
        for i in self:
            gcode.append(i.copy())
        
        return gcode


    @property
    def layers(self) -> list['Gcode']:
        """
        Returns a list of Gcode, each representing a layer in the original Gcode.
        
        Returns:
            list[Gcode]: List of Gcode, one for each layer
        """
        
        layer_dict = {}
        
        for block in self:
            layer_num = block.block_data.layer
            if layer_num is not None:
                if layer_num not in layer_dict:
                    layer_dict[layer_num] = self.new()
                layer_dict[layer_num].append(block.copy())
        
        return [layer_dict[i] for i in sorted(layer_dict.keys())]
