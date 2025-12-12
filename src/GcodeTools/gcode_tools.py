import json
from GcodeTools.gcode_types import *
from GcodeTools.gcode import Gcode
import base64
import textwrap
from GcodeTools.gcode_parser import MetaParser


class Tools:


    @staticmethod
    def get_slicer_name(gcode: Gcode) -> tuple[str, str]:
        """
        Get (`slicer_name`, `slicer_version`)
        """
        for line in gcode[:20]:
            cmd = line.command
            if 'bambustudio' in cmd.lower():
                slicer = 'BambuStudio'
                version = cmd.split('BambuStudio')[1].trim()
                return (slicer, version)
            if 'generated' in cmd.lower():
                line = cmd.split('by')[-1].split('with')[-1].replace('Version', '').replace('(R)', '').split()
                slicer = line[0]
                version = line[1]
                return (slicer, version)


    @staticmethod
    def read_config(gcode: Gcode):
        """
        Read slicer's config from `Gcode`
        """
        metadata = {}
        start_id, end_id = -1, -1
        for id, block in enumerate(gcode):
        
            if start_id == -1 and MetaParser.get_keyword_line(id, gcode, MetaParser.CONFIG_START): start_id = id
            if end_id == -1 and start_id != -1 and MetaParser.get_keyword_line(id, gcode, MetaParser.CONFIG_END): end_id = id
        
        if start_id == -1 or end_id - start_id > 1000: return None
        print(f'{start_id=}, {end_id=}')
        
        for block in gcode[start_id + 1 : end_id]:
            line = block.command
            delimeter = line.find('=')
            if delimeter < 0: delimeter = line.find(',')
            key = line[1:delimeter].strip()
            value = line[delimeter + 1:].strip()
            metadata[key] = value
        
        return metadata


    @staticmethod
    def generate_config_files(gcode: Gcode) -> dict[str, str]:
        """
        Generate configuration file(s) for slicer which generated the gcode.

        Returns:
            {`filename`, `contents`}
        """
        slicer, version = Tools.get_slicer_name(gcode)
        config = Tools.read_config(gcode)
        if slicer.lower() in ['cura']:
            print(f'{slicer.lower()} doesn\'t generate configuration')
            return {}
        elif slicer.lower() in ['orcaslicer', 'bambustudio']:
            machine = config.copy()
            process = config.copy()
            filament = {}

            filament_fields = ['filament', 'fan_', 'temp', 'nozzle', 'slow', 'air_']
            for key in config.keys():
                if any(field in key for field in filament_fields):
                    filament[key] = config[key]

            try:
                inherit_groups = config['inherits_group'].split(';')
                if inherit_groups[0]:
                    process['inherits'] = inherit_groups[0]
                if inherit_groups[1]:
                    filament['inherits'] = inherit_groups[1]
                if inherit_groups[2]:
                    machine['inherits'] = inherit_groups[2]
                    process['compatible_printers'] = [inherit_groups[2]]
                    filament['compatible_printers'] = [inherit_groups[2]]
            except KeyError:
                pass

            filament['from'] = 'User'
            filament['type'] = 'filament'
            filament['is_custom_defined'] = '0'
            filament['version'] = version
            filament['name'] = config['filament_settings_id']

            machine['from'] = 'User'
            machine['type'] = 'machine'
            machine['is_custom_defined'] = '0'
            machine['version'] = version
            machine['name'] = config['printer_settings_id']

            process['from'] = 'User'
            process['type'] = 'process'
            process['is_custom_defined'] = '0'
            process['version'] = version
            process['name'] = config['print_settings_id']

            filament_str = json.dumps(filament, indent=4)
            machine_str = json.dumps(machine, indent=4)
            process_str = json.dumps(process, indent=4)

            return {'filament.json': filament_str, 'machine.json': machine_str, 'process.json': process_str}

        else:
            if slicer.lower() not in ['prusaslicer', 'slic3r', 'superslicer']:
                print('Unsupported slicer: trying generating slic3r config')
            output = ''
            for key in config.keys():
                output += key + ' = ' + config[key] + '\n'
            return {'config.ini': output}


    @staticmethod
    def split(gcode: Gcode) -> tuple[Gcode, Gcode, Gcode, dict[Gcode]]:
        """
        Splits `Gcode` into:
            start_gcode, object_gcode, end_gcode, where object_gcode is everything between start and end gcodes
            objects: `dict` of individual objects' `Gcode`s
        
        
        Returns:
            `tuple`: (`start_gcode`: Gcode, `end_gcode`: Gcode, `object_gcode`: Gcode, `objects`: dict[Gcode])
        """
        object_gcode = gcode.new()
        start_gcode = gcode.new()
        end_gcode = gcode.new()
        objects: dict[Gcode] = {}
        
        for block in gcode:
            
            if block.block_data.move_type == Static.PRINT_START:
                start_gcode.append(block)
            elif block.block_data.move_type == Static.PRINT_END:
                end_gcode.append(block)
            else:
                object_gcode.append(block)
            
            object = block.block_data.object
            if object not in objects.keys():
                objects[object] = gcode.new()
            
            objects[object].append(block)
        
        return (start_gcode, end_gcode, object_gcode, objects)


    @staticmethod
    def trim(gcode: Gcode):
        """
        Trims G-code from every command that's not handled by GcodeTools
        
        Warning: some commands that aren't handled, may be important for the G-code!
        """
        
        gcode_new = gcode.new()
        pos = gcode[0].block_data.position
        for item in gcode:
            if item.block_data.position != pos:
                pos = item.block_data.position
                it = item.copy()
                it.emit_command = False
                it.command = ''
                gcode_new.append(it)
        return gcode_new


    @staticmethod
    def set_flowrate(gcode: Gcode, flowrate: float, force_extrusion = False) -> Gcode:
        """
        Sets flowrate (mm in E over mm in XYZ)
        
        Args:
            flowrate: `float` - desired flowrate
            force_extrusion: `bool` - on `True` forces flowrate even on non-extrusion moves
        """
        gcode_new = gcode.copy()
        for i in gcode_new:
            if force_extrusion or (i.block_data.position.E and i.block_data.position.E > 0):
                # i.move.set_flowrate(flowrate)
                pass
        return gcode_new


    @staticmethod
    def translate(gcode: Gcode, vector: Vector) -> Gcode:
        gcode_new = gcode.copy()
        for i in gcode_new:
            i.block_data.position += vector
        gcode_new.order()
        return gcode_new


    @staticmethod
    def rotate(gcode: Gcode, deg: int) -> Gcode:
        gcode_new = gcode.copy()
        for i in gcode_new:
            i.block_data.position.rotate(deg)
        return gcode_new


    @staticmethod
    def scale(gcode: Gcode, scale: int|Vector) -> Gcode:
        gcode_new = gcode.copy()
        for i in gcode_new:
            i.block_data.position *= scale
        return gcode_new


    @staticmethod
    def center(gcode: Gcode) -> Vector:
        """
        Get center of bounding box of gcode
        """
        vec1, vec2 = Tools.get_bounding_box(gcode)
        return (vec1 + vec2) / 2


    @staticmethod
    def get_bounding_box(gcode: Gcode) -> tuple[Vector, Vector]:
        """
        Get bounding box of gcode
        
        Returns:
            `tuple` of (low_corner, high_corner)
        """
        low_corner: Vector = gcode[0].block_data.position.xyz()
        high_corner: Vector = gcode[0].block_data.position.xyz()
        
        lower_bound = lambda a,b: a if a < b else b
        upper_bound = lambda a,b: a if a > b else b
        
        for item in gcode:
            high_corner = high_corner.vector_op(item.block_data.position, upper_bound)
            low_corner = low_corner.vector_op(item.block_data.position, lower_bound)
            
        return (low_corner.xyz(), high_corner.xyz())


    @staticmethod
    def center_of_mass(gcode: Gcode) -> Vector:
        """
        Calculate the center of mass of the model
        """
        total_volume = 0
        sum = Vector()
        sum_e = 0
        
        for block in gcode:
            pos = block.block_data.position
            sum_e += pos.E or 0
            if sum_e > 0:
                volume = (pos.E or 0) + sum_e
                total_volume += volume
                
                sum += pos * volume
        
        if total_volume < gcode.config.step:
            return Vector()
        
        return (sum / total_volume).xyz()


    # TODO: regenerate_travels:
    # - ensure clean travel trimming
    # FIXME: correct travel begin/end
    @staticmethod
    def regenerate_travels(gcode: Gcode, move_speed = 0):
        out_gcode = gcode.new()
        past_item = None
        is_first = True
        e_add = 0
        for item in gcode:
            if is_first:
                out_gcode.append(item.copy())
                if item.block_data.object != None:
                    is_first = False
                continue
            
            if item.block_data.object == None:
                if past_item is None:
                    out_gcode.append('G10; retract')
                past_item = item.copy()
                e_add += past_item.block_data.position.E
                past_item.block_data.position.E = 0
            else:
                if past_item is not None:
                    if move_speed > 0:
                        past_item.block_data.position.F = move_speed
                    out_gcode.append(past_item.copy())
                    past_item.block_data.position.E = e_add
                    out_gcode.append(past_item.copy())
                    out_gcode.append('G11; unretract')
                    e_add = 0
                past_item = None
                
                out_gcode.append(item.copy())
        if is_first:
            print('Cannot regenerate travels: no objects present in metadata')
        return out_gcode


    @staticmethod
    def remove_thumbnails(gcode: Gcode) -> Gcode:
        """
        Remove embedded thumbnails from gcode
        """
        new_gcode = gcode.new()
        start = -1
        for idx, i in enumerate(gcode):
            if start > -1:
                if i.command == '; THUMBNAIL_BLOCK_END':
                    start = -1
            elif i.command == '; THUMBNAIL_BLOCK_START':
                start = idx
            else:
                new_gcode.append(i)
        
        return new_gcode


    @staticmethod
    def read_thumbnails(gcode: Gcode) -> list[bytes]:
        """
        Get all thumbnails from `Gcode`, ordered as appearing in `Gcode`. For now only `png` format is supported
        
        Example implementation:
        ```
        for idx, thumb in enumerate(Tools.get_thumbnails(gcode)):
            with open(f'thumb{idx}.png', 'wb') as f:
                f.write(thumb)
        ```
        """
        start = -1
        image_text = ''
        images = []
        for idx, i in enumerate(gcode):
            if start > -1:
                if i.command == '; THUMBNAIL_BLOCK_END':
                    start = -1
                    images.append(base64.b64decode(image_text))
                
                text = i.command.removeprefix(';').strip()
                if 'thumbnail end' in text or 'thumbnail begin' in text or len(text) == 0: continue
                image_text += text
            
            if i.command == '; THUMBNAIL_BLOCK_START':
                start = idx
                image_text = ''
        
        return images


    @staticmethod
    def write_thumbnail(gcode: Gcode, data: bytes, width: int, height: int, textwidth = None) -> Gcode:
        """
        Args:
            data: `bytes` - raw png data
            width: `int` - width in pixels
            height: `int` - height in pixels
            textwidth: `int` - custom wrapping width of thumbnail text
                Defaults to 80 below 10kB, otherwise 160
        """
        new = gcode.copy()
        
        THUMB_BLOCK = '\n'\
        '; thumbnail begin {0}x{1} {2}\n'\
        '{3}\n'\
        '; thumbnail end\n'\
        
        text = base64.b64encode(data)
        len_text = len(text)
        if not textwidth: textwidth = 80 if len_text < 10000 else 160
        text = textwrap.indent(textwrap.fill(text.decode('utf-8'), textwidth - 2), '; ')

        thumb = THUMB_BLOCK.format(width, height, len_text, text)
        
        Tools.write_slicer_header(new)
        new.header += thumb
        return new


    @staticmethod
    def write_slicer_header(gcode: Gcode):
        if 'Slicer' not in gcode.header.splitlines()[0]:
            gcode.header = '; old Moonraker versions required typing PrusaSlicer - on here\n' + gcode.header