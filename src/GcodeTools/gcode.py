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
        self.header = ''
        self.footer = ''
        self.objects: list[str] = []
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


    def from_str(self, gcode_str: str, block = Block(), progress_callback: typing.Callable|None = None) -> 'Gcode':
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            gcode_str: `str` - string that will be parsed into `Gcode`
            block: `Block` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
        """
        self: Gcode = self.__get_parser__().from_str(self, gcode_str, block, progress_callback)
        self.__fill_meta__()
        return self

    def from_file(self, filename: str, block = Block(), progress_callback: typing.Callable|None = None) -> 'Gcode':
        """
        Args:
            gcode: `Gcode` or `None`. When `Gcode`, uses its config. When `None`, creates an empty `Gcode`
            filename: `str` - filename containing g-code to be parsed
            block: `Block` - initial printer state
            progress_callback: `Callable(current: int, total: int)`
        """
        self: Gcode = self.__get_parser__().from_file(self, filename, block, progress_callback)
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
        return self.__get_parser__().write_file(self, filename, verbose, progress_callback)


    def new(self):
        """
        Create an empty G-code list with self's config
        """
        new = Gcode()
        new.config = self.config
        new.objects = self.objects
        return new


    def __add_block__(self, block: Block, index: int):
        """The same as `Gcode.insert()`"""

        idx = index if index < len(self) else -1
        block_obj = block.copy()
        if idx == -1:
            super().append(block_obj)
        else:
            super().insert(index, block_obj)


    def __add_str__(self, gcode: str, index: int = -1, block:Block|None=None, compile = False):
        """
        The same as `Gcode.insert()`
        
        For advanced use - `Block` can be build from its params

        Args:
            gcode: `str`
            index: `int`
                Default index = `-1` => append to the end of `Gcode`
            block: `Block`
            compile: `bool` - compile `Block` using `CoordSystem` and `GcodeParser` instead of only putting command into a block.
                - compilation doesn't propagate forward, i.e. putting `M106` only affects newly created `Block`.
        """
        
        idx = index if index < len(self) else -1
        
        if len(self) == 0:
            if block is None: block = Block(config=self.config)
        else:
            last_index = idx - 1 * (idx > 0)
            
            if block is None: block = self[last_index]
        
        if compile:
            parser = self.__get_parser__()
            position = self[max(idx, 0) - 1].position if len(self) else Vector()
            gcode_objs = parser._parse_line(parser.ParserData(CoordSystem(position=position), Block(None, gcode, True, block, self.config)))
            for idx, obj in enumerate(gcode_objs):
                if idx == -1:
                    super().append(obj.block)
                else:
                    super().insert(index + idx, obj.block)
            return
        gcode_obj = block
        gcode_obj.prev = None
        gcode_obj.command = gcode
        # gcode_obj.config = self.config
        
        if idx == -1:
            super().append(gcode_obj)
            return
        super().insert(index, gcode_obj)


    def __super__(self):
        return super()


    def __iter__(self):
        return super().__iter__()


    def __getitem__(self, key):
        """Returns a shallow copy of `Gcode` or `Block`"""
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
        gcode.objects = self.objects
        
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
            layer_num = block.layer
            if layer_num is not None:
                if layer_num not in layer_dict:
                    layer_dict[layer_num] = self.new()
                layer_dict[layer_num].append(block.copy())
        
        return [layer_dict[i] for i in sorted(layer_dict.keys())]



    def block_to_str(self, block_id: int, verbose=False):
        """Returns gcode string of `Block`"""
        
        current: Block = self[block_id]
        if block_id < 1: prev = Block()
        else: prev: Block = self[block_id - 1]

        out = ''
        if current.layer != prev.layer:
            out += ';LAYER_CHANGE\n'
        if current.move_type != prev.move_type:
            out += f';TYPE:{Static.MOVE_TYPES.get(current.move_type, Static.MOVE_TYPES[-1])}\n'
        if current.object != prev.object:
            if prev.object > -1:
                if not self.config.enable_exclude_object: out += ';'
                out += f'EXCLUDE_OBJECT_END NAME={prev.object}\n'
            if current.object > -1:
                if not self.config.enable_exclude_object: out += ';'
                out += f'EXCLUDE_OBJECT_START NAME={current.object}\n'
        
        if current.e_temp != prev.e_temp and current.e_temp is not None:
            out += f'{Static.E_TEMP_DESC.format(current.e_temp)}\n'
        if current.bed_temp != prev.bed_temp and current.bed_temp is not None:
            out += f'{Static.BED_TEMP_DESC.format(current.bed_temp)}\n'
        
        if current.e_temp != prev.e_temp and current.e_temp is not None and current.e_wait:
            out += f'{Static.E_TEMP_WAIT_DESC.format(current.e_temp)}\n'
        if current.bed_temp != prev.bed_temp and current.bed_temp is not None and current.bed_wait:
            out += f'{Static.BED_TEMP_WAIT_DESC.format(current.bed_temp)}\n'
        
        if current.fan != prev.fan and current.fan is not None:
            out += f'{Static.FAN_SPEED_DESC.format(current.fan)}\n'
        if current.T != prev.T and current.T is not None:
            out += f'{Static.TOOL_CHANGE_DESC.format(current.T)}\n'
        
        print_coord = lambda param, a: '' f' {param}{a:.{self.config.precision}f}'.rstrip('0').rstrip('.')
        move = ''

        if current.position.X != prev.position.X: move += print_coord('X', current.position.X)
        if current.position.Y != prev.position.Y: move += print_coord('Y', current.position.Y)
        if current.position.Z != prev.position.Z: move += print_coord('Z', current.position.Z)
        if current.position.E != 0: move += print_coord('E', current.position.E)
        if current.position.F != prev.position.F: move += print_coord('F', current.position.F)
        
        if move != '': out += 'G1' + move + '\n'
        
        if current.position != Vector() and prev.position == Vector(): out = Static.HOME_DESC + '\n' + out
        
        
        if current.emit_command and current.command:
            out += current.command + '\n'
        
        if out != '':
            if verbose:
                out += '; '
                out += remove_chars(json.dumps(self.block_to_dict(block_id)), '{} \"').replace(",", " ")
                out += '\n'
        
        return out


    def block_to_dict(self, block_id):
        current: Block = self[block_id]
        return {
            'command': current.command,
            'emit_command': current.emit_command,
            'config': current.config,
            'e_temp': current.e_temp,
            'e_wait': current.e_wait,
            'bed_temp': current.bed_temp,
            'bed_wait': current.bed_wait,
            'fan': current.fan,
            'T': current.T,
            'object': current.object,
            'move_type': current.move_type,
            'layer': current.layer,
            'position': current.position
        }
