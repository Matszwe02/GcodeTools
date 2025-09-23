from GcodeTools.gcode_types import *
from GcodeTools.gcode import Gcode
from GcodeTools.gcode_tools import MoveTypes, Tools
import numpy as np
from PIL import Image


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
    def generate_thumbnail(gcode: Gcode, *, resolution = 500, e_scale = 1, draw_bounding_box = False, color: tuple[int, int, int]|None = None, camera_pos = Vector.one(), orthographic = False, fov = 45):
        ps = Thumbnails._generate_scene(gcode, True, resolution, e_scale, draw_bounding_box, color, camera_pos, orthographic, fov)
        buf = ps.screenshot_to_buffer()
        image = Image.fromarray(buf)
        return image


    @staticmethod
    def interactive(gcode: Gcode, resolution = 500, e_scale = 1, draw_bounding_box = False, color = None, camera_pos = Vector.one(), orthographic = False, fov = 45):
        ps = Thumbnails._generate_scene(gcode, False, resolution, e_scale, draw_bounding_box, color, camera_pos, orthographic, fov)
        ps.show()


    @staticmethod
    def _generate_scene(gcode: Gcode, backend, resolution: int, e_scale: float, draw_bounding_box: bool, color: tuple[int, int, int], camera_pos: Vector, orthographic: bool, fov: float):
        import polyscope as ps
        if backend:
            ps.init('openGL3_egl')
        else:
            ps.init()
        ps.set_window_size(resolution, resolution)
        ps.set_up_dir("z_up")
        ps.set_SSAA_factor(1)
        ps.set_view_projection_mode("orthographic" if orthographic else "perspective")
        intrinsics = ps.CameraIntrinsics(fov_vertical_deg=fov, aspect=1.)
        extrinsics = ps.CameraExtrinsics(root=(2., 2., 2.), look_dir=(-1., 0., 0.), up_dir=(0.,1.,0.))
        new_params = ps.CameraParameters(intrinsics, extrinsics)
        ps.set_view_camera_parameters(new_params)

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

        print(len(nodes))
        print(len(edges))


        bounding_box = Tools.get_bounding_box(gcode)

        middle = (bounding_box[0] + bounding_box[1]) / 2
        size = bounding_box[1] - bounding_box[0]
        size_max = max(size.X, max(size.Y, size.Z))
        camera_pos_abs = middle + camera_pos * (size_max * 1)

        if len(nodes) > 0:
            ps_net = ps.register_curve_network("Gcode Path", nodes, edges, material="clay")
            ps_net.add_scalar_quantity("radius", sizes, enabled=True)
            ps_net.set_node_radius_quantity("radius", False)
            ps_net.add_color_quantity("colors", colors, defined_on='edges', enabled=True)
        if draw_bounding_box:
            min_x = bounding_box[0].X
            min_y = bounding_box[0].Y
            min_z = bounding_box[0].Z
            max_x = bounding_box[1].X
            max_y = bounding_box[1].Y
            max_z = bounding_box[1].Z

            bbox_nodes = np.array([
                [min_x, min_y, min_z],
                [max_x, min_y, min_z],
                [min_x, max_y, min_z],
                [max_x, max_y, min_z],
                [min_x, min_y, max_z],
                [max_x, min_y, max_z],
                [min_x, max_y, max_z],
                [max_x, max_y, max_z],
            ])

            bbox_edges = np.array([
                [0, 1], [1, 3], [3, 2], [2, 0],  # Bottom rectangle
                [4, 5], [5, 7], [7, 6], [6, 4],  # Top rectangle
                [0, 4], [1, 5], [2, 6], [3, 7],  # Vertical edges
            ])

            if len(bbox_nodes) > 0:
                ps_bbox_net = ps.register_curve_network("Bounding Box", bbox_nodes, bbox_edges, material="flat")
                ps_bbox_net.set_color((1, 0, 0))
                ps_bbox_net.set_radius(0.0005)

        ps.look_at((camera_pos_abs.X, camera_pos_abs.Y, camera_pos_abs.Z), (middle.X, middle.Y, middle.Z))
        ps.set_view_center((middle.X, middle.Y, middle.Z))
        ps.set_ground_plane_mode("none")
        return ps