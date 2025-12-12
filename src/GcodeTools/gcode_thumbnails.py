from typing import List
from GcodeTools.gcode_types import *
from GcodeTools.gcode import Gcode
from GcodeTools.gcode_tools import MoveTypes, Tools
import numpy as np
from PIL import Image
import polyscope as ps
import io


class Thumbnails:

    MOVE_TYPE_COLORS = {
        'inner' : [255, 255, 0],
        'outer' : [255, 55, 0],
        'skirt' : [0, 31, 7],
        'solid' : [63, 0, 127],
        'sparse' : [127, 0, 0],
        'bridge' : [0, 127, 255],
        'top' : [192, 0, 0],
        'overhang' : [0, 0, 255],
    }

    @staticmethod
    def generate_thumbnail(gcode: Gcode, *, e_scale = 1, color: tuple[int, int, int]|None = None, yaw = 45, pitch = 45, fov = 45, resolution = 500, render_scale = 1, fit_in_viewport = True):
        ps = Thumbnails._generate_scene(gcode, False, yaw, pitch, fov, resolution * render_scale)
        Thumbnails._create_gcode_object(gcode, e_scale, color)
        buf = ps.screenshot_to_buffer()
        image = Image.fromarray(buf)
        if fit_in_viewport and render_scale > 1.5:
            image = Thumbnails.crop(image)
        image = image.resize((resolution, resolution))
        return image


    @staticmethod
    def interactive(gcode: Gcode = None, gcodes: List[Gcode] = None, e_scale = 1, color_moves = False):
        if not gcodes:
            gcodes = [gcode]
        colors = [(255,0,0),(255,255,0),(0,255,0),(0,255,255),(0,0,255),(255,0,255)]
        ps = Thumbnails._generate_scene(gcodes[0], len(gcodes) < 2, 45, 45, 45, 300)
        for idx, g in enumerate(gcodes):
            Thumbnails._create_gcode_object(g, e_scale, None if color_moves else colors[idx % len(colors)], idx)
        ps.show()


    @staticmethod
    def crop(image: Image.Image):
        image_data = np.asarray(image.quantize().convert('RGB'))
        image_data_bw = image_data.max(axis=2)
        non_empty_columns = np.where(image_data_bw.min(axis=0)<255)[0]
        non_empty_rows = np.where(image_data_bw.min(axis=1)<255)[0]
        cropBox = (min(non_empty_columns), min(non_empty_rows), max(non_empty_columns), max(non_empty_rows))
        w = cropBox[2] - cropBox[0]
        h = cropBox[3] - cropBox[1]
        size = max(w, h) / 2
        middle = ((cropBox[0] + cropBox[2]) / 2, (cropBox[1] + cropBox[3]) / 2)
        print(f'{cropBox=}')
        return image.crop((middle[0] - size, middle[1] - size, middle[0] + size, middle[1] + size))


    @staticmethod
    def _create_gcode_object(gcode: Gcode, e_scale = 1, color: tuple[int, int, int]|None = None, id = 0):
        nodes = []
        edges = []
        sizes = []
        colors = []
        current_position = None
        continuous = False
        if color:
            draw_color = np.array([color[0] / 255, color[1] / 255, color[2] / 255])

        for block in gcode:
            if not block.move.position.is_none(False):
                new_position = np.array([block.move.position.X, block.move.position.Y, block.move.position.Z])
                if current_position is None:
                    current_position = new_position
                    continuous = False
                    continue
                if block.move.position.E <= 0:
                    current_position = new_position
                    continuous = False
                    continue
                flowrate = 0.01 if block.meta.get('type') == MoveTypes.NO_OBJECT else .4
                flowrate *= e_scale
                if not continuous:
                    nodes.append(current_position)
                    sizes.append(flowrate)
                nodes.append(new_position)
                edges.append([len(nodes) - 2, len(nodes) - 1])
                colors_arr = Thumbnails.MOVE_TYPE_COLORS.get(block.meta.get('type'), [127, 127, 127])
                if color is None:
                    draw_color = np.array([colors_arr[0]/255, colors_arr[1]/255, colors_arr[2]/255])
                sizes.append(flowrate)
                colors.append(draw_color)
                current_position = new_position
                continuous = True

        nodes = np.array(nodes)
        edges = np.array(edges)
        sizes = np.array(sizes)
        colors = np.array(colors)
        if len(nodes) > 0:
            ps_net = ps.register_curve_network(f"Gcode {id} Path", nodes, edges, material="clay")
            try:
                ps_net.add_scalar_quantity("radius", sizes, enabled=True)
                ps_net.set_node_radius_quantity("radius", False)
            except:
                print('Warning: some features are not supported with this python version')
                size = np.median(sizes)
                ps_net.set_radius(size, False)
            ps_net.add_color_quantity("colors", colors, defined_on='edges', enabled=True)
            return ps_net


    @staticmethod
    def _create_bounding_box_object(min: Vector, max: Vector):

        bbox_nodes = np.array([
            [min.X, min.Y, min.Z],
            [max.X, min.Y, min.Z],
            [min.X, max.Y, min.Z],
            [max.X, max.Y, min.Z],
            [min.X, min.Y, max.Z],
            [max.X, min.Y, max.Z],
            [min.X, max.Y, max.Z],
            [max.X, max.Y, max.Z],
        ])
        bbox_edges = np.array([
            [0, 1], [1, 3], [3, 2], [2, 0],  # Bottom rectangle
            [4, 5], [5, 7], [7, 6], [6, 4],  # Top rectangle
            [0, 4], [1, 5], [2, 6], [3, 7],  # Vertical edges
        ])
        ps_bbox_net = ps.register_curve_network("Bounding Box", bbox_nodes, bbox_edges, material="flat")
        ps_bbox_net.set_color((1, 0, 0))
        ps_bbox_net.set_radius(0.001)
        return ps_bbox_net


    @staticmethod
    def _generate_scene(gcode: Gcode, draw_bounding_box: bool, yaw: float, pitch: float, fov: float, resolution: int):

        bounding_box = Tools.get_bounding_box(gcode)

        middle = (bounding_box[0] + bounding_box[1]) / 2
        size = (bounding_box[1] - bounding_box[0]) / 2
        radius = math.sqrt(size.X**2 + size.Y**2 + size.Z**2)
        if fov >= 5:
            camera_dist = 1 / (math.sin(math.radians(fov / 2))) * radius
        else:
            camera_dist = radius
        camera_pos = Vector()
        pitch = max(min(pitch, 89.999), -89.999)
        camera_pos.Z = math.sin(math.radians(pitch))
        h_dist = math.cos(math.radians(pitch))
        camera_pos.X = math.sin(math.radians(yaw)) * h_dist
        camera_pos.Y = math.cos(math.radians(yaw)) * h_dist
        camera_pos *= camera_dist
        camera_pos += middle
        

        w, h = ps.get_window_size()
        if w != resolution or h != resolution:
            ps.set_window_size(resolution, resolution)

        try:
            ps.set_allow_headless_backends(True) 
        except:
            print('Warning: some features are not supported with this python version')
        ps.set_verbosity(6)

        # try:
        # except:
        # ps.init('openGL3_egl')
        ps.set_use_prefs_file(False)
        ps.init()
        # ps.set_always_redraw(True)
        ps.set_up_dir("z_up")
        ps.set_view_projection_mode("orthographic" if fov < 5 else "perspective")
        intrinsics = ps.CameraIntrinsics(fov_vertical_deg=fov if fov >= 5 else 35, aspect=1.)
        extrinsics = ps.CameraExtrinsics(root=(2., 2., 2.), look_dir=(-1., 0., 0.), up_dir=(0.,1.,0.))
        new_params = ps.CameraParameters(intrinsics, extrinsics)
        ps.set_view_camera_parameters(new_params)
        ps.look_at((camera_pos.X, camera_pos.Y, camera_pos.Z), (middle.X, middle.Y, middle.Z))

        if draw_bounding_box:
            Thumbnails._create_bounding_box_object(bounding_box[0], bounding_box[1])

        try:
            ps.set_view_center((middle.X, middle.Y, middle.Z))
        except:
            pass
        ps.set_ground_plane_mode("none")
        w, h = ps.get_window_size()
        if w != resolution or h != resolution:
            ps.set_window_size(resolution, resolution)
        return ps


    @staticmethod
    def write_image_thumbnail(gcode: Gcode, image: Image.Image):
        img_data = io.BytesIO()
        image.save(img_data, 'webp', optimize = True, quality = 70)
        w, h = image.size
        return Tools.write_thumbnail(gcode, img_data.getvalue(), w, h)


    @staticmethod
    def set_thumbnail(gcode: Gcode, image: Image.Image):
        """
        Replaces thumbnails with a selected image. Adds a small 48x48 thumbnail.
        """
        gcode = Tools.remove_thumbnails(gcode)
        gcode = Thumbnails.write_image_thumbnail(gcode, image)
        gcode = Thumbnails.write_image_thumbnail(gcode, image.resize((48, 48)))
        return gcode