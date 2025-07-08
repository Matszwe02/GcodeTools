import math
import io
from PIL import Image, ImageDraw
from GcodeTools import Vector, Gcode, Tools, MoveTypes


class ThumbnailTools:
    """
    Contains tools for generating G-code thumbnails.
    """

    COLOR_MODE_LAYER = 'layer'
    COLOR_MODE_FEATURE = 'feature'
    COLOR_MODE_FEEDRATE = 'feedrate'

    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    ORANGE = (255, 125, 0)
    PURPLE = (128, 0, 128)
    CYAN = (0, 255, 255)
    GREY = (128, 128, 128)
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)


    @staticmethod
    def _generate_lines(
        gcode: Gcode,
        color_mode: str
    ) -> list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[int, int, int], float]]:
        """
        Generates raw line data from G-code in 3D coordinates.

        Returns:
            list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[int, int, int], int]]:
            A list of tuples, each containing:
            - Start position ([x, y, z])
            - End position ([x, y, z])
            - Base color ([r, g, b])
            - Line width type (0 for travel moves, 1 for extrusion)
        """
        
        max_feed_rate = 0
        for block in gcode:
            if block.move and block.move.speed is not None:
                 max_feed_rate = max(max_feed_rate, block.move.speed)
        max_feed_rate = max_feed_rate or gcode.config.speed

        feature_color_map = {
            MoveTypes.EXTERNAL_PERIMETER: ThumbnailTools.ORANGE,
            MoveTypes.INTERNAL_PERIMETER: ThumbnailTools.YELLOW,
            MoveTypes.OVERHANG_PERIMETER: ThumbnailTools.BLUE,
            MoveTypes.SOLID_INFILL: ThumbnailTools.PURPLE,
            MoveTypes.TOP_SOLID_INFILL: ThumbnailTools.RED,
            MoveTypes.SPARSE_INFILL: ThumbnailTools.RED,
            MoveTypes.BRIDGE: ThumbnailTools.BLUE,
            MoveTypes.SKIRT: ThumbnailTools.GREEN,
            MoveTypes.PRINT_START: ThumbnailTools.WHITE,
            MoveTypes.PRINT_END: ThumbnailTools.BLACK
        }
        travel_color = ThumbnailTools.BLUE


        def hue_to_rgb(hue: float) -> tuple[int, int, int]:
            hue *= 360
            while hue < 0: hue += 360
            while hue >= 360: hue -= 360

            hue_section = hue / 60
            second_largest_component = 1 - abs(hue_section % 2 - 1)

            if hue_section >= 0 and hue_section <= 1:
                red = 255
                green = round(255 * (second_largest_component))
                blue = 0
            elif hue_section > 1 and hue_section <= 2:
                red = round(255 * (second_largest_component))
                green = 255
                blue = 0
            elif hue_section > 2 and hue_section <= 3:
                red = 0
                green = 255
                blue = round(255 * (second_largest_component))
            elif hue_section > 3 and hue_section <= 4:
                red = 0
                green = round(255 * (second_largest_component))
                blue = 255
            elif hue_section > 4 and hue_section <= 5:
                red = round(255 * (second_largest_component))
                green = 0
                blue = 255
            else:
                red = 255
                green = 0
                blue = round(255 * (second_largest_component))

            return (red, green, blue)


        line_segments: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[int, int, int], int]] = []

        last_pos_3d: Vector | None = None
        last_speed: float | None = gcode.config.speed

        for block in gcode:
            current_pos_3d = block.move.position

            if last_pos_3d and current_pos_3d:
                is_extrusion = block.move.position.E is not None and block.move.position.E > 1e-6

                base_color_rgb = travel_color
                line_width = -1

                if is_extrusion:
                    # line_width = block.move.get_flowrate() or 0
                    line_width = 1

                    if color_mode == ThumbnailTools.COLOR_MODE_FEEDRATE:
                        current_speed = block.move.speed if block.move.speed is not None else last_speed
                        feed_rate = current_speed if current_speed is not None else gcode.config.speed
                        factor = (feed_rate) / (max_feed_rate)
                        base_color_rgb = hue_to_rgb(2/3 - (factor * 2/3))
                        last_speed = current_speed
                    
                    elif color_mode == ThumbnailTools.COLOR_MODE_LAYER:
                        layer = block.meta.get('layer')
                        layer = int(layer) if layer is not None else 0
                        base_color_rgb = hue_to_rgb(layer/10)
                    
                    elif color_mode == ThumbnailTools.COLOR_MODE_FEATURE:
                        move_type = block.meta.get('type')
                        base_color_rgb = feature_color_map.get(move_type, ThumbnailTools.GREY)
                    
                    else:
                        base_color_rgb = color_mode
                
                if not last_pos_3d.is_none(False) and not current_pos_3d.is_none(False):
                    line_segments.append((last_pos_3d.to_list(False), current_pos_3d.to_list(False), base_color_rgb, line_width))
            
            last_pos_3d = current_pos_3d

        return line_segments


    @staticmethod
    def GenerateThumbnail(
        gcode: Gcode,
        yaw: float = 30,
        pitch: float = 45,
        linewidth: float = 0.4,
        image_size: int = 256,
        draw_travels: bool = False,
        color_mode = 'feature',
        ) -> bytes:
        """
        Generates a thumbnail image of the G-code using Pillow, applying workflow
        concepts from the reference JS viewer for improved rendering.

        Args:
            gcode: Gcode object to visualize.
            yaw: Yaw angle for the view (in degrees).
            pitch: Pitch angle for the view (in degrees).
            linewidth: Base width of the lines in the thumbnail (scaled).
            image_size: The width and height of the thumbnail image in pixels.
            draw_travels: Whether to draw travel moves (non-extrusion).
            color_mode: 'feature' (color by move type) or 'feedrate' (color by feed speed).

        Returns:
            bytes: PNG image data of the thumbnail.
        """

        line_data = ThumbnailTools._generate_lines(gcode, color_mode)

        if not line_data:
            output_buffer = io.BytesIO()
            Image.new('RGBA', (image_size, image_size), (0, 0, 0, 0)).save(output_buffer, format='PNG')
            return output_buffer.getvalue()

        v1, v2 = Tools.get_bounding_box(gcode)

        center = (v1 + v2) / 2

        yaw_rad = math.radians(yaw)
        pitch_rad = math.radians(-pitch)
        cos_yaw, sin_yaw = math.cos(yaw_rad), math.sin(yaw_rad)
        cos_pitch, sin_pitch = math.cos(pitch_rad), math.sin(pitch_rad)

        corners = [
            Vector(v1.X, v1.Y, v1.Z),
            Vector(v2.X, v1.Y, v1.Z),
            Vector(v1.X, v2.Y, v1.Z),
            Vector(v1.X, v1.Y, v2.Z),
            Vector(v2.X, v2.Y, v1.Z),
            Vector(v2.X, v1.Y, v2.Z),
            Vector(v1.X, v2.Y, v2.Z),
            Vector(v2.X, v2.Y, v2.Z)
        ]

        projected_points = []
        for corner in corners:
            centered = corner - center
            
            rotated_x = centered.X * cos_yaw - centered.Y * sin_yaw
            rotated_y = centered.X * sin_yaw + centered.Y * cos_yaw
            rotated_z = centered.Z
            
            final_x = rotated_x
            final_y = rotated_y * cos_pitch - rotated_z * sin_pitch

            projected_points.append((final_x, final_y))

        min_proj_x = min(p[0] for p in projected_points)
        max_proj_x = max(p[0] for p in projected_points)
        min_proj_y = min(p[1] for p in projected_points)
        max_proj_y = max(p[1] for p in projected_points)

        proj_width = max_proj_x - min_proj_x
        proj_height = max_proj_y - min_proj_y

        if proj_width <= 1e-6 and proj_height <= 1e-6:
            scale = 1
        elif proj_width <= 1e-6:
             scale = image_size / proj_height
        elif proj_height <= 1e-6:
             scale = image_size / proj_width
        else: # Normal case
            scale_x = image_size / proj_width
            scale_y = image_size / proj_height
            scale = min(scale_x, scale_y)

        scaled_width = proj_width * scale
        scaled_height = proj_height * scale
        offset_x = (image_size - scaled_width) / 2 - (min_proj_x * scale)
        offset_y = (image_size - scaled_height) / 2 - (-max_proj_y * scale)

        def transform_to_screen(proj_x, proj_y):
            """Transforms projected 3D coordinates (after rotation) to 2D screen coordinates."""
            screen_x = proj_x * scale + offset_x
            screen_y = -proj_y * scale + offset_y
            return screen_x, screen_y

        image = Image.new('RGBA', (image_size, image_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image, 'RGBA')

        for start_pos, end_pos, base_color_rgb, width in line_data:
            
            if width == -1 and not draw_travels: continue

            start_x_centered = start_pos[0] - center.X
            start_y_centered = start_pos[1] - center.Y
            start_z_centered = start_pos[2] - center.Z

            end_x_centered = end_pos[0] - center.X
            end_y_centered = end_pos[1] - center.Y
            end_z_centered = end_pos[2] - center.Z

            start_x_rotated = start_x_centered * cos_yaw - start_y_centered * sin_yaw
            start_y_rotated = start_x_centered * sin_yaw + start_y_centered * cos_yaw
            start_z_rotated = start_z_centered

            end_x_rotated = end_x_centered * cos_yaw - end_y_centered * sin_yaw
            end_y_rotated = end_x_centered * sin_yaw + end_y_centered * cos_yaw
            end_z_rotated = end_z_centered

            start_x_final = start_x_rotated
            start_y_final = start_y_rotated * cos_pitch - start_z_rotated * sin_pitch
            start_z_final = start_y_rotated * sin_pitch + start_z_rotated * cos_pitch

            end_x_final = end_x_rotated
            end_y_final = end_y_rotated * cos_pitch - end_z_rotated * sin_pitch
            end_z_final = end_y_rotated * sin_pitch + end_z_rotated * cos_pitch

            start_screen = transform_to_screen(start_x_final, start_y_final)
            end_screen = transform_to_screen(end_x_final, end_y_final)

            line_draw_width = max(1, int(linewidth * width * scale))

            # Apply shading in GenerateThumbnail
            final_color_rgba = base_color_rgb + (255,)
            if width > -1: # Only apply shading to extrusion lines
                 dx = end_x_final - start_x_final
                 dy = end_y_final - start_y_final
                 dz = end_z_final - start_z_final
                 line_len_sq = dx*dx + dy*dy + dz*dz

                 if line_len_sq > 1e-9:
                     line_len = math.sqrt(line_len_sq)
                     norm_x, norm_y, norm_z = dx / line_len, dy / line_len, dz / line_len
                     light_vec_x, light_vec_y, light_vec_z = 0.577, -0.577, 0.577
                     dot_product = norm_x * light_vec_x + norm_y * light_vec_y + norm_z * light_vec_z
                     shading_factor = max(0.3, min(1.0, (dot_product + 1) * 0.35 + 0.3))
                     r = int(base_color_rgb[0] * shading_factor)
                     g = int(base_color_rgb[1] * shading_factor)
                     b = int(base_color_rgb[2] * shading_factor)
                     final_color_rgba = (r, g, b, 255)
            
            draw.line([start_screen, end_screen], fill=final_color_rgba, width=line_draw_width)

        output_buffer = io.BytesIO()
        image.save(output_buffer, format='PNG')
        png_data = output_buffer.getvalue()
        output_buffer.close()
        return png_data
