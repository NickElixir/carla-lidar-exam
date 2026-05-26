#!/usr/bin/env python3

"""Minimal CARLA exam scene: ego car, static pedestrians, RGB camera, LiDAR."""

import argparse
import glob
import json
import os
import random
import sys
import threading
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def append_carla_api_path():
    py_tag = "cp%d%d" % (sys.version_info.major, sys.version_info.minor)
    egg_name = "carla-*%d.%d-%s.egg" % (
        sys.version_info.major,
        sys.version_info.minor,
        "win-amd64" if os.name == "nt" else "linux-x86_64",
    )
    wheel_name = "carla-*%s-*%s*.whl" % (
        py_tag,
        "win_amd64" if os.name == "nt" else "x86_64",
    )
    candidates = [
        os.path.join(SCRIPT_DIR, "PythonAPI/carla/dist", egg_name),
        os.path.join(SCRIPT_DIR, "PythonAPI/carla/dist", wheel_name),
        os.path.join(SCRIPT_DIR, "..", "PythonAPI/carla/dist", egg_name),
        os.path.join(SCRIPT_DIR, "..", "PythonAPI/carla/dist", wheel_name),
    ]
    carla_root = os.environ.get("CARLA_ROOT")
    if carla_root:
        candidates.insert(0, os.path.join(carla_root, "PythonAPI/carla/dist", egg_name))
        candidates.insert(1, os.path.join(carla_root, "PythonAPI/carla/dist", wheel_name))

    matches = []
    for pattern in candidates:
        matches.extend(glob.glob(os.path.abspath(pattern)))
    if matches:
        sys.path.append(matches[0])


append_carla_api_path()

try:
    import carla
except ImportError as exc:
    raise RuntimeError(
        "Could not import CARLA Python API with Python %d.%d. "
        "Use a matching Conda environment, install the matching `carla` "
        "package, or set CARLA_ROOT to a CARLA simulator folder containing "
        "PythonAPI/carla/dist."
        % (sys.version_info.major, sys.version_info.minor)
    ) from exc

import numpy as np
import pygame
from pygame.locals import K_a, K_d, K_DOWN, K_ESCAPE, K_LEFT, K_RIGHT
from pygame.locals import K_s, K_SPACE, K_UP, K_w


SEMANTIC_COLORS = np.array([
    (255, 255, 255),
    (70, 70, 70),
    (100, 40, 40),
    (55, 90, 80),
    (220, 20, 60),
    (153, 153, 153),
    (157, 234, 50),
    (128, 64, 128),
    (244, 35, 232),
    (107, 142, 35),
    (0, 0, 142),
    (102, 102, 156),
    (220, 220, 0),
    (70, 130, 180),
    (81, 0, 81),
    (150, 100, 100),
    (230, 150, 140),
    (180, 165, 180),
    (250, 170, 30),
    (110, 190, 160),
    (170, 120, 50),
    (45, 60, 150),
    (145, 170, 100),
], dtype=np.float64) / 255.0

BOX_EDGES = np.array([
    (0, 1), (1, 3), (3, 2), (2, 0),
    (4, 5), (5, 7), (7, 6), (6, 4),
    (0, 4), (1, 5), (2, 6), (3, 7),
], dtype=np.int32)

MAX_PEOPLE_RADIUS = 10.0


def set_blueprint_attribute_if_present(blueprint, name, value):
    if blueprint.has_attribute(name):
        blueprint.set_attribute(name, str(value))


def get_blueprints(world, pattern, generation):
    blueprints = world.get_blueprint_library().filter(pattern)
    if generation.lower() == "all":
        return list(blueprints)
    try:
        generation_value = int(generation)
    except ValueError:
        return []
    return [
        bp for bp in blueprints
        if bp.has_attribute("generation")
        and int(bp.get_attribute("generation")) == generation_value
    ]


def destroy_existing_npcs(client, world):
    actor_ids = []
    for pattern in ("vehicle.*", "walker.pedestrian.*", "controller.ai.walker"):
        actor_ids.extend(actor.id for actor in world.get_actors().filter(pattern))
    if actor_ids:
        client.apply_batch([carla.command.DestroyActor(actor_id) for actor_id in actor_ids])
    return len(actor_ids)


def major_minor_patch(version):
    parts = []
    for part in str(version).split("."):
        if not part.isdigit():
            break
        parts.append(int(part))
        if len(parts) == 3:
            break
    return tuple(parts)


def ensure_carla_version_compatible(client):
    client_version = client.get_client_version()
    server_version = client.get_server_version()
    client_parts = major_minor_patch(client_version)
    server_parts = major_minor_patch(server_version)
    if client_parts and server_parts and client_parts[:3] != server_parts[:3]:
        raise RuntimeError(
            "CARLA client/server version mismatch: client API is %s, "
            "simulator server is %s. Start a CARLA %s simulator for this "
            "environment, or create a matching Python environment for the "
            "running simulator."
            % (client_version, server_version, client_version)
        )


def spawn_ego_vehicle(world, args):
    blueprints = get_blueprints(world, args.vehicle_filter, args.vehicle_generation)
    if not blueprints:
        raise RuntimeError("No vehicle blueprints matched %s" % args.vehicle_filter)

    blueprint = random.choice(blueprints)
    blueprint.set_attribute("role_name", "hero")
    if blueprint.has_attribute("color"):
        blueprint.set_attribute("color", random.choice(blueprint.get_attribute("color").recommended_values))

    spawn_points = list(world.get_map().get_spawn_points())
    random.shuffle(spawn_points)
    for transform in spawn_points:
        vehicle = world.try_spawn_actor(blueprint, transform)
        if vehicle is not None:
            return vehicle
    raise RuntimeError("Could not spawn ego vehicle at any map spawn point")


def distance_2d(a, b):
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def random_location_around_actor(actor_transform, min_radius, max_radius, angle):
    radius = (random.uniform(min_radius ** 2, max_radius ** 2)) ** 0.5
    forward = actor_transform.get_forward_vector()
    right = actor_transform.get_right_vector()
    location = actor_transform.location
    offset_x = radius * np.cos(angle)
    offset_y = radius * np.sin(angle)
    return carla.Location(
        x=location.x + forward.x * offset_x + right.x * offset_y,
        y=location.y + forward.y * offset_x + right.y * offset_y,
        z=location.z + 0.5,
    )


def spawn_static_people(world, ego, args):
    blueprints = get_blueprints(world, args.people_filter, args.people_generation)
    if not blueprints:
        raise RuntimeError("No pedestrian blueprints matched %s" % args.people_filter)

    ego_location = ego.get_location()
    ego_transform = ego.get_transform()
    people_radius = min(args.people_radius, MAX_PEOPLE_RADIUS)
    people_min_distance = min(args.people_min_distance, people_radius)
    candidates = []

    slots = max(args.static_people, 1)
    sector_width = 2.0 * np.pi / slots
    offset_angle = random.uniform(0.0, 2.0 * np.pi)
    sector_ids = list(range(slots))
    for _cycle in range(max(args.people_sector_cycles, 1)):
        random.shuffle(sector_ids)
        for sector_id in sector_ids:
            angle = offset_angle + sector_width * sector_id + random.uniform(-0.45, 0.45) * sector_width
            candidates.append(random_location_around_actor(
                ego_transform,
                people_min_distance,
                people_radius,
                angle,
            ))

    attempts = 0
    fallback_candidates = []
    while len(fallback_candidates) < args.static_people * 6 and attempts < args.people_attempts:
        attempts += 1
        location = world.get_random_location_from_navigation()
        if location is None:
            continue
        distance = distance_2d(location, ego_location)
        if people_min_distance <= distance <= people_radius:
            fallback_candidates.append(location)

    random.shuffle(candidates)
    random.shuffle(fallback_candidates)
    candidates.extend(fallback_candidates)
    people = []
    target_transforms = []
    for location in candidates:
        if len(people) >= args.static_people:
            break
        if any(distance_2d(location, target.location) < 0.75 for target in target_transforms):
            continue
        blueprint = random.choice(blueprints)
        if blueprint.has_attribute("is_invincible"):
            blueprint.set_attribute("is_invincible", "true")
        transform = carla.Transform(location, carla.Rotation(yaw=random.uniform(-180.0, 180.0)))
        person = world.try_spawn_actor(blueprint, transform)
        if person is not None:
            person.apply_control(carla.WalkerControl(speed=0.0))
            people.append(person)
            target_transforms.append(transform)

    if people:
        world.tick()
        for person, transform in zip(people, target_transforms):
            if person is None or not person.is_alive:
                continue
            person.set_transform(transform)
            person.apply_control(carla.WalkerControl(speed=0.0))
        world.tick()

    actual_distances = [
        distance_2d(person.get_location(), ego_location)
        for person in people
        if person is not None and person.is_alive
    ]

    print(
        "Spawned static pedestrians: %d/%d within %.1f m, actual distances=%s"
        % (
            len(people),
            args.static_people,
            people_radius,
            ", ".join("%.1f" % distance for distance in actual_distances[:8]),
        )
    )
    return people


def actor_bbox_vertices_in_lidar(actor, lidar_transform):
    bbox = actor.bounding_box
    world_vertices = bbox.get_world_vertices(actor.get_transform())
    if len(world_vertices) != 8:
        return None

    world_corners = np.array([
        [vertex.x, vertex.y, vertex.z, 1.0]
        for vertex in world_vertices
    ], dtype=np.float64)
    sensor_inverse = np.array(lidar_transform.get_inverse_matrix(), dtype=np.float64)
    lidar_corners = (sensor_inverse.dot(world_corners.T)).T[:, :3]
    lidar_corners[:, 1] = -lidar_corners[:, 1]
    if lidar_corners.shape != (8, 3) or not np.all(np.isfinite(lidar_corners)):
        return None
    return lidar_corners


def actor_lidar_points_refined_vertices(actor, lidar_transform, lidar_points, object_ids, min_points=6):
    if lidar_points is None or object_ids is None:
        return None
    mask = object_ids == actor.id
    if int(np.count_nonzero(mask)) < min_points:
        return None

    actor_points = np.asarray(lidar_points[mask], dtype=np.float64)
    sensor_points = np.column_stack((
        actor_points[:, 0],
        -actor_points[:, 1],
        actor_points[:, 2],
        np.ones(len(actor_points), dtype=np.float64),
    ))
    sensor_matrix = np.array(lidar_transform.get_matrix(), dtype=np.float64)
    actor_inverse = np.array(actor.get_transform().get_inverse_matrix(), dtype=np.float64)
    local_points = (actor_inverse.dot(sensor_matrix).dot(sensor_points.T)).T[:, :3]
    if local_points.size == 0 or not np.all(np.isfinite(local_points)):
        return None

    base_world_vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    base_world_corners = np.array([
        [vertex.x, vertex.y, vertex.z, 1.0]
        for vertex in base_world_vertices
    ], dtype=np.float64)
    base_local_points = (actor_inverse.dot(base_world_corners.T)).T[:, :3]

    combined_local_points = np.vstack((base_local_points, local_points))
    lower = combined_local_points.min(axis=0)
    upper = combined_local_points.max(axis=0)
    if np.any(upper - lower <= 0.01):
        return None

    local_corners = np.array([
        [lower[0], lower[1], lower[2], 1.0],
        [lower[0], upper[1], lower[2], 1.0],
        [upper[0], lower[1], lower[2], 1.0],
        [upper[0], upper[1], lower[2], 1.0],
        [lower[0], lower[1], upper[2], 1.0],
        [lower[0], upper[1], upper[2], 1.0],
        [upper[0], lower[1], upper[2], 1.0],
        [upper[0], upper[1], upper[2], 1.0],
    ], dtype=np.float64)
    actor_matrix = np.array(actor.get_transform().get_matrix(), dtype=np.float64)
    sensor_inverse = np.array(lidar_transform.get_inverse_matrix(), dtype=np.float64)
    lidar_corners = (sensor_inverse.dot(actor_matrix).dot(local_corners.T)).T[:, :3]
    lidar_corners[:, 1] = -lidar_corners[:, 1]
    if lidar_corners.shape != (8, 3) or not np.all(np.isfinite(lidar_corners)):
        return None
    return lidar_corners


def actor_best_bbox_vertices_in_lidar(actor, lidar_transform, lidar_points=None, object_ids=None):
    refined_vertices = actor_lidar_points_refined_vertices(actor, lidar_transform, lidar_points, object_ids)
    if refined_vertices is not None:
        return refined_vertices
    return actor_bbox_vertices_in_lidar(actor, lidar_transform)


def bbox_dimensions_from_vertices(vertices):
    return {
        "x": float(np.linalg.norm(vertices[2] - vertices[0])),
        "y": float(np.linalg.norm(vertices[1] - vertices[0])),
        "z": float(np.linalg.norm(vertices[4] - vertices[0])),
    }


def build_bbox_lineset_data(
    actors,
    lidar_transform,
    max_distance=None,
    lidar_points=None,
    object_ids=None,
    line_color=None,
):
    points = []
    lines = []
    colors = []
    if line_color is None:
        line_color = [1.0, 0.85, 0.05]

    for actor in actors:
        if actor is None or not actor.is_alive:
            continue
        if max_distance is not None and actor.get_location().distance(lidar_transform.location) > max_distance:
            continue
        base_index = len(points)
        vertices = actor_best_bbox_vertices_in_lidar(actor, lidar_transform, lidar_points, object_ids)
        if vertices is None:
            continue
        points.extend(vertices.tolist())
        lines.extend((BOX_EDGES + base_index).tolist())
        colors.extend([line_color] * len(BOX_EDGES))

    if not points:
        return None, None, None
    box_points = np.ascontiguousarray(points, dtype=np.float64).reshape((-1, 3))
    box_lines = np.ascontiguousarray(lines, dtype=np.int32).reshape((-1, 2))
    box_colors = np.ascontiguousarray(colors, dtype=np.float64).reshape((-1, 3))
    if box_points.size == 0 or box_lines.size == 0:
        return None, None, None
    return box_points, box_lines, box_colors


def merge_bbox_linesets(*datasets):
    all_points = []
    all_lines = []
    all_colors = []
    offset = 0
    for dataset in datasets:
        if dataset is None or dataset[0] is None:
            continue
        points, lines, colors = dataset
        all_points.append(points)
        all_lines.append(lines + offset)
        all_colors.append(colors)
        offset += len(points)
    if not all_points:
        return None
    return np.concatenate(all_points), np.concatenate(all_lines), np.concatenate(all_colors)


class CameraSensor(object):
    def __init__(self, world, ego, width, height):
        self.lock = threading.Lock()
        self.width = width
        self.height = height
        self.frame = 0
        self.rgb_bytes = None
        self.first_frame_saved = False
        blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
        blueprint.set_attribute("image_size_x", str(width))
        blueprint.set_attribute("image_size_y", str(height))
        blueprint.set_attribute("fov", "100")
        set_blueprint_attribute_if_present(blueprint, "enable_postprocess_effects", "false")
        set_blueprint_attribute_if_present(blueprint, "motion_blur_intensity", "0.0")
        transform = carla.Transform(carla.Location(x=-6.0, z=2.8), carla.Rotation(pitch=-14.0))
        self.sensor = world.spawn_actor(
            blueprint,
            transform,
            attach_to=ego,
            attachment_type=carla.AttachmentType.SpringArmGhost,
        )
        self.sensor.listen(self._on_image)

    def _on_image(self, image):
        raw = np.frombuffer(image.raw_data, dtype=np.uint8)
        bgra = raw.reshape((image.height, image.width, 4))
        rgb = bgra[:, :, :3][:, :, ::-1].copy()
        with self.lock:
            self.frame = image.frame
            self.rgb_bytes = rgb.tobytes()
        if not self.first_frame_saved:
            image.save_to_disk(os.path.join(SCRIPT_DIR, "debug_exam_camera_first_frame"))
            self.first_frame_saved = True
            print("RGB camera first frame received: %d" % image.frame)

    def snapshot(self):
        with self.lock:
            if self.rgb_bytes is None:
                return None, self.frame
            return self.rgb_bytes, self.frame

    def destroy(self):
        self.sensor.stop()
        self.sensor.destroy()


class SemanticLidar(object):
    def __init__(self, world, ego, args):
        self.lock = threading.Lock()
        self.points = None
        self.colors = None
        self.object_ids = None
        self.frame = 0
        self.max_points = args.open3d_max_points
        self.keep_points_for_viewer = not args.no_open3d or args.save_dataset
        blueprint = world.get_blueprint_library().find("sensor.lidar.ray_cast_semantic")
        blueprint.set_attribute("channels", str(args.lidar_channels))
        blueprint.set_attribute("range", str(args.lidar_range))
        blueprint.set_attribute("points_per_second", str(args.lidar_points_per_second))
        blueprint.set_attribute("rotation_frequency", str(args.lidar_rotation_frequency))
        blueprint.set_attribute("upper_fov", str(args.lidar_upper_fov))
        blueprint.set_attribute("lower_fov", str(args.lidar_lower_fov))
        set_blueprint_attribute_if_present(blueprint, "noise_stddev", args.lidar_noise_stddev)
        set_blueprint_attribute_if_present(blueprint, "dropoff_general_rate", args.lidar_dropoff_general_rate)
        set_blueprint_attribute_if_present(blueprint, "dropoff_intensity_limit", args.lidar_dropoff_intensity_limit)
        set_blueprint_attribute_if_present(blueprint, "dropoff_zero_intensity", args.lidar_dropoff_zero_intensity)
        set_blueprint_attribute_if_present(
            blueprint,
            "atmosphere_attenuation_rate",
            args.lidar_atmosphere_attenuation_rate,
        )
        z = ego.bounding_box.extent.z + args.lidar_z_offset
        transform = carla.Transform(carla.Location(z=z))
        self.sensor = world.spawn_actor(
            blueprint,
            transform,
            attach_to=ego,
            attachment_type=carla.AttachmentType.Rigid,
        )
        self.sensor.listen(self._on_lidar)

    def _on_lidar(self, data):
        raw = np.frombuffer(data.raw_data, dtype=np.dtype([
            ("x", np.float32),
            ("y", np.float32),
            ("z", np.float32),
            ("cos_angle", np.float32),
            ("object_idx", np.uint32),
            ("object_tag", np.uint32),
        ]))
        if raw.size == 0:
            return
        if not self.keep_points_for_viewer:
            with self.lock:
                self.frame = data.frame
            return

        raw_view = raw
        if raw.size > self.max_points:
            indices = np.linspace(0, raw.size - 1, self.max_points).astype(np.int32)
            raw_view = raw[indices]
        points = np.column_stack((raw_view["x"], -raw_view["y"], raw_view["z"])).astype(np.float64)
        labels = np.clip(raw_view["object_tag"].astype(np.int32), 0, len(SEMANTIC_COLORS) - 1)
        colors = SEMANTIC_COLORS[labels]
        object_ids = raw_view["object_idx"].astype(np.uint32).copy()
        with self.lock:
            self.points = points
            self.colors = colors
            self.object_ids = object_ids
            self.frame = data.frame

    def snapshot(self, include_object_ids=False):
        with self.lock:
            if self.points is None:
                if include_object_ids:
                    return None, None, None, self.frame
                return None, None, self.frame
            if include_object_ids:
                return self.points, self.colors, self.object_ids, self.frame
            return self.points, self.colors, self.frame

    def destroy(self):
        self.sensor.stop()
        self.sensor.destroy()


class Open3DView(object):
    def __init__(self, max_points, update_hz):
        try:
            import open3d as o3d
        except ImportError:
            self.o3d = None
            self.visualizer = None
            print("Open3D is not installed; continuing without 3D point cloud window.")
            return
        self.o3d = o3d
        self.max_points = max_points
        self.min_interval = 1.0 / max(update_hz, 0.1)
        self.last_update = 0.0
        self.point_cloud = o3d.geometry.PointCloud()
        self.box_lines = o3d.geometry.LineSet()
        self.visualizer = o3d.visualization.Visualizer()
        self.visualizer.create_window("Exam Semantic LiDAR", width=960, height=540, left=60, top=60)
        options = self.visualizer.get_render_option()
        options.background_color = np.array([0.02, 0.02, 0.02])
        options.point_size = 1.0
        options.show_coordinate_frame = True
        self.point_cloud_added = False
        self.box_lines_added = False
        self.box_lines_failed = False

    def tick(self, points, colors, box_data=None):
        if self.visualizer is None:
            return
        self.visualizer.poll_events()
        now = time.time()
        if points is None or now - self.last_update < self.min_interval:
            return
        self.point_cloud.points = self.o3d.utility.Vector3dVector(points)
        self.point_cloud.colors = self.o3d.utility.Vector3dVector(colors)
        if not self.point_cloud_added:
            self.visualizer.add_geometry(self.point_cloud)
            self.point_cloud_added = True
        else:
            self.visualizer.update_geometry(self.point_cloud)

        if box_data is not None and box_data[0] is not None and not self.box_lines_failed:
            box_points, box_lines, box_colors = box_data
            try:
                self.box_lines.points = self.o3d.utility.Vector3dVector(box_points)
                self.box_lines.lines = self.o3d.utility.Vector2iVector(box_lines)
                self.box_lines.colors = self.o3d.utility.Vector3dVector(box_colors)
                if not self.box_lines_added:
                    self.visualizer.add_geometry(self.box_lines)
                    self.box_lines_added = True
                else:
                    self.visualizer.update_geometry(self.box_lines)
            except RuntimeError as exc:
                print("Warning: Open3D rejected GT bounding boxes; continuing with point cloud only: %s" % exc)
                self.box_lines_failed = True
        self.visualizer.update_renderer()
        self.last_update = now

    def destroy(self):
        if self.visualizer is not None:
            self.visualizer.destroy_window()


class DatasetWriter(object):
    def __init__(self, root_dir):
        self.root_dir = os.path.abspath(root_dir)
        self.lidar_dir = os.path.join(self.root_dir, "lidar")
        self.label_dir = os.path.join(self.root_dir, "label")
        os.makedirs(self.lidar_dir, exist_ok=True)
        os.makedirs(self.label_dir, exist_ok=True)
        self.index = 0

    def save(self, points, labels):
        if points is None or len(points) == 0:
            print("Dataset save skipped: no LiDAR points yet.")
            return
        frame_name = "%06d" % self.index
        pcd_path = os.path.join(self.lidar_dir, frame_name + ".pcd")
        label_path = os.path.join(self.label_dir, frame_name + ".json")
        self._write_ascii_pcd(pcd_path, points)
        with open(label_path, "w", encoding="utf-8") as label_file:
            json.dump(labels, label_file, indent=2)
        print(
            "Saved dataset frame %s: points=%d labels=%d %s %s"
            % (frame_name, len(points), len(labels), pcd_path, label_path)
        )
        self.index += 1

    def _write_ascii_pcd(self, path, points):
        with open(path, "w", encoding="ascii") as pcd_file:
            pcd_file.write("# .PCD v0.7 - Point Cloud Data file format\n")
            pcd_file.write("VERSION 0.7\n")
            pcd_file.write("FIELDS x y z\n")
            pcd_file.write("SIZE 4 4 4\n")
            pcd_file.write("TYPE F F F\n")
            pcd_file.write("COUNT 1 1 1\n")
            pcd_file.write("WIDTH %d\n" % len(points))
            pcd_file.write("HEIGHT 1\n")
            pcd_file.write("VIEWPOINT 0 0 0 1 0 0 0\n")
            pcd_file.write("POINTS %d\n" % len(points))
            pcd_file.write("DATA ascii\n")
            for x, y, z in points:
                pcd_file.write("%.6f %.6f %.6f\n" % (x, y, z))


def build_sustech_labels(actors, lidar_transform, max_distance=None, lidar_points=None, object_ids=None):
    labels = []
    for actor in actors:
        if actor is None or not actor.is_alive:
            continue
        if max_distance is not None and actor.get_location().distance(lidar_transform.location) > max_distance:
            continue

        vertices = actor_best_bbox_vertices_in_lidar(actor, lidar_transform, lidar_points, object_ids)
        if vertices is None:
            continue
        center = np.mean(vertices, axis=0)
        dimensions = bbox_dimensions_from_vertices(vertices)
        forward = vertices[2] - vertices[0]
        yaw = float(np.arctan2(forward[1], forward[0]))
        flattened_vertices = []
        for x, y, z in vertices:
            flattened_vertices.extend([float(x), float(y), float(z), 1])

        labels.append({
            "psr": {
                "position": {
                    "x": float(center[0]),
                    "y": float(center[1]),
                    "z": float(center[2]),
                },
                "scale": dimensions,
                "rotation": {
                    "x": 0.0,
                    "y": 0.0,
                    "z": yaw,
                },
            },
            "obj_type": "Pedestrian",
            "obj_id": str(actor.id),
            "vertices": flattened_vertices,
        })
    return labels


def apply_manual_control(vehicle, keys, args, control_state):
    control = carla.VehicleControl()
    velocity = vehicle.get_velocity()
    forward = vehicle.get_transform().get_forward_vector()
    longitudinal_speed = velocity.x * forward.x + velocity.y * forward.y + velocity.z * forward.z
    wants_forward = "w" in keys or "up" in keys
    wants_reverse = "s" in keys or "down" in keys
    dt = max(args.fixed_delta_seconds, 0.001)
    throttle = control_state.get("throttle", 0.0)
    target_throttle = 0.0

    if wants_forward:
        target_throttle = args.drive_throttle
        control.reverse = False
        control.gear = 1
    elif wants_reverse:
        if longitudinal_speed > 0.25:
            throttle = 0.0
            control.brake = args.drive_brake
            control.reverse = False
            control.gear = 1
        else:
            target_throttle = args.reverse_throttle
            control.brake = 0.0
            control.reverse = True
            control.gear = -1
    else:
        control.throttle = 0.0
        control.brake = 0.0
        control.reverse = False
        control.gear = 1

    if target_throttle > throttle:
        throttle = min(target_throttle, throttle + args.throttle_ramp_rate * dt)
    else:
        throttle = max(target_throttle, throttle - args.throttle_release_rate * dt)
    control.throttle = throttle
    control_state["throttle"] = throttle

    control.steer = -args.drive_steer if "a" in keys or "left" in keys else 0.0
    if "d" in keys or "right" in keys:
        control.steer = args.drive_steer
    control.hand_brake = "space" in keys
    vehicle.apply_control(control)


def pygame_key_set():
    pressed = pygame.key.get_pressed()
    keys = set()
    if pressed[K_w]:
        keys.add("w")
    if pressed[K_s]:
        keys.add("s")
    if pressed[K_a]:
        keys.add("a")
    if pressed[K_d]:
        keys.add("d")
    if pressed[K_UP]:
        keys.add("up")
    if pressed[K_DOWN]:
        keys.add("down")
    if pressed[K_LEFT]:
        keys.add("left")
    if pressed[K_RIGHT]:
        keys.add("right")
    if pressed[K_SPACE]:
        keys.add("space")
    return keys


def draw_pygame(display, font, camera_bytes, camera_size, camera_frame, lidar_frame, people_count, started_at):
    display.fill((18, 22, 26))
    if camera_bytes is not None:
        surface = pygame.image.frombuffer(camera_bytes, camera_size, "RGB")
        display.blit(surface, (0, 0))
    else:
        elapsed = time.time() - started_at
        title = font.render("Waiting for RGB camera frames", True, (255, 232, 120))
        hint = font.render("If this stays visible, CARLA camera streaming is the failing part.", True, (220, 225, 230))
        elapsed_text = font.render("Elapsed: %.1fs" % elapsed, True, (220, 225, 230))
        display.blit(title, (32, 36))
        display.blit(hint, (32, 70))
        display.blit(elapsed_text, (32, 104))

    panel = pygame.Surface((430, 116), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 145))
    display.blit(panel, (16, 16))
    lines = [
        "WASD/arrows: drive   Space: hand brake   ESC: quit",
        "RGB camera frame: %d" % camera_frame,
        "Semantic LiDAR frame: %d" % lidar_frame,
        "Static pedestrians: %d" % people_count,
    ]
    y = 26
    for line in lines:
        display.blit(font.render(line, True, (245, 248, 250)), (28, y))
        y += 24
    if not getattr(draw_pygame, "_saved_debug_display", False):
        pygame.image.save(display, os.path.join(SCRIPT_DIR, "debug_pygame_display.png"))
        draw_pygame._saved_debug_display = True
        print("Saved first pygame display surface to debug_pygame_display.png")
    pygame.display.flip()


class TkCameraView(object):
    KEYCODE_ALIASES = {
        9: "escape",
        25: "w",
        38: "a",
        39: "s",
        40: "d",
        46: "l",
        65: "space",
        111: "up",
        113: "left",
        114: "right",
        116: "down",
    }

    def __init__(self, width, height, update_hz):
        import tkinter as tk
        from PIL import Image, ImageDraw, ImageTk

        self.tk = tk
        self.Image = Image
        self.ImageDraw = ImageDraw
        self.ImageTk = ImageTk
        self.width = width
        self.height = height
        self.min_interval = 1.0 / max(update_hz, 0.1)
        self.last_image_update = 0.0
        self.keys = set()
        self.closed = False
        self.photo = None
        self.last_camera_frame = None
        self.frame_period = int(round(1000.0 / max(update_hz, 0.1)))

        self.root = tk.Tk()
        self.root.title("CARLA exam Tk RGB + LiDAR")
        self.image_label = tk.Label(self.root, bg="black", takefocus=True)
        self.image_label.pack()
        self.status_var = tk.StringVar()
        self.status = tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            justify="left",
            font=("DejaVu Sans", 11),
        )
        self.status.pack(fill="x")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind_all("<KeyPress>", self._key_press)
        self.root.bind_all("<KeyRelease>", self._key_release)
        self.root.update_idletasks()
        self.root.focus_force()
        self.image_label.focus_set()

    def _normalize_key(self, event):
        keycode = getattr(event, "keycode", None)
        if keycode in self.KEYCODE_ALIASES:
            return self.KEYCODE_ALIASES[keycode]
        keysym = getattr(event, "keysym", "")
        key = keysym.lower()
        aliases = {
            "escape": "escape",
            "space": "space",
        }
        return aliases.get(key, key)

    def _key_press(self, event):
        key = self._normalize_key(event)
        self.keys.add(key)
        if key == "escape":
            self.close()

    def _key_release(self, event):
        self.keys.discard(self._normalize_key(event))

    def close(self):
        self.closed = True

    def tick(self, camera_bytes, camera_size, camera_frame, lidar_frame, people_count, started_at):
        if self.closed:
            return False

        now = time.time()
        should_update_image = (
            self.photo is None
            or camera_frame != self.last_camera_frame
            and now - self.last_image_update >= self.min_interval
        )
        if should_update_image:
            if camera_bytes is not None:
                image = self.Image.frombytes("RGB", camera_size, camera_bytes)
            else:
                image = self.Image.new("RGB", camera_size, (18, 22, 26))
                draw = self.ImageDraw.Draw(image)
                draw.text((32, 34), "Waiting for RGB camera frames", fill=(255, 232, 120))
                draw.text((32, 64), "Elapsed: %.1fs" % (time.time() - started_at), fill=(230, 235, 240))
            self.photo = self.ImageTk.PhotoImage(image)
            self.image_label.configure(image=self.photo)
            self.last_image_update = now
            self.last_camera_frame = camera_frame

        active = ",".join(sorted(self.keys)) if self.keys else "-"
        self.status_var.set(
            "WASD/arrows: drive | Space: hand brake | L: save dataset frame | ESC: quit    "
            "RGB frame: %d    LiDAR frame: %d    Static pedestrians: %d    Keys: %s"
            % (camera_frame, lidar_frame, people_count, active)
        )
        self.root.update_idletasks()
        self.root.update()
        return not self.closed

    def pump_events(self):
        if self.closed:
            return False
        self.root.update_idletasks()
        self.root.update()
        return not self.closed

    def destroy(self):
        try:
            self.root.destroy()
        except self.tk.TclError:
            pass


def follow_with_spectator(world, ego):
    transform = ego.get_transform()
    forward = transform.get_forward_vector()
    location = transform.location - forward * 8.0 + carla.Location(z=4.0)
    rotation = carla.Rotation(pitch=-18.0, yaw=transform.rotation.yaw, roll=0.0)
    world.get_spectator().set_transform(carla.Transform(location, rotation))


def run(args):
    display = None
    font = None
    clock = None
    tk_view = None
    if args.viewer == "pygame":
        pygame.init()
        pygame.font.init()
        display = pygame.display.set_mode((args.width, args.height), pygame.HWSURFACE | pygame.DOUBLEBUF)
        pygame.display.set_caption("CARLA exam minimal RGB + LiDAR")
        font = pygame.font.Font(None, 26)
        clock = pygame.time.Clock()
    elif args.viewer == "tk":
        tk_view = TkCameraView(args.width, args.height, args.viewer_fps)

    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    ensure_carla_version_compatible(client)
    world = client.get_world()
    traffic_manager = client.get_trafficmanager(args.tm_port)
    original_settings = world.get_settings()
    actors = []
    open3d_view = None
    dataset_writer = DatasetWriter(args.dataset_dir) if args.save_dataset else None
    previous_keys = set()
    control_state = {"throttle": 0.0}
    saved_once = False
    started_at = time.time()

    try:
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = args.fixed_delta_seconds
        settings.no_rendering_mode = False
        world.apply_settings(settings)
        traffic_manager.set_synchronous_mode(True)

        removed_count = destroy_existing_npcs(client, world) if args.clear_existing_npcs else 0
        if removed_count:
            world.tick()
        ego = spawn_ego_vehicle(world, args)
        actors.append(ego)
        people = spawn_static_people(world, ego, args)
        actors.extend(people)
        camera = CameraSensor(world, ego, args.width, args.height)
        lidar = SemanticLidar(world, ego, args)
        actors.extend([camera.sensor, lidar.sensor])
        if not args.no_open3d:
            open3d_view = Open3DView(args.open3d_max_points, args.open3d_update_hz)

        print("Scene ready: ego=%d people=%d removed=%d" % (ego.id, len(people), removed_count))
        running = True
        while running:
            if args.duration_seconds > 0.0 and time.time() - started_at >= args.duration_seconds:
                running = False
                continue

            if args.viewer == "pygame":
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN and event.key == K_ESCAPE:
                        running = False
                keys = pygame_key_set()
            elif args.viewer == "tk":
                keys = set(tk_view.keys)
            else:
                keys = set()

            apply_manual_control(ego, keys, args, control_state)
            follow_with_spectator(world, ego)
            world.tick()

            camera_frame, camera_frame_id = camera.snapshot()
            lidar_frame = lidar.frame
            points = None
            colors = None
            object_ids = None
            box_data = None
            if open3d_view is not None:
                points, colors, object_ids, lidar_frame = lidar.snapshot(include_object_ids=True)
                if args.show_gt_boxes:
                    people_box_data = build_bbox_lineset_data(
                        people,
                        lidar.sensor.get_transform(),
                        args.lidar_range,
                        points,
                        object_ids,
                    )
                    ego_box_data = build_bbox_lineset_data(
                        [ego],
                        lidar.sensor.get_transform(),
                        args.lidar_range,
                        line_color=[0.0, 0.9, 1.0],
                    )
                    box_data = merge_bbox_linesets(people_box_data, ego_box_data)
            if open3d_view is not None:
                open3d_view.tick(points, colors, box_data)

            save_requested = dataset_writer is not None and (
                args.save_once and not saved_once and lidar_frame > 0
                or
                "l" in keys and "l" not in previous_keys
                or args.dataset_every_n_frames > 0
                and lidar_frame > 0
                and lidar_frame % args.dataset_every_n_frames == 0
            )
            if save_requested:
                if points is None:
                    points, _colors, object_ids, lidar_frame = lidar.snapshot(include_object_ids=True)
                labels = build_sustech_labels(
                    people,
                    lidar.sensor.get_transform(),
                    lidar_points=points,
                    object_ids=object_ids,
                )
                if points is not None and len(points) > 0:
                    dataset_writer.save(points, labels)
                    saved_once = True
            previous_keys = keys

            if args.viewer == "pygame":
                draw_pygame(
                    display,
                    font,
                    camera_frame,
                    (camera.width, camera.height),
                    camera_frame_id,
                    lidar_frame,
                    len(people),
                    started_at,
                )
                clock.tick(60)
            elif args.viewer == "tk":
                if camera_frame is not None and (
                    tk_view.photo is None
                    or camera_frame_id != tk_view.last_camera_frame
                    and time.time() - tk_view.last_image_update >= tk_view.min_interval
                ):
                    running = tk_view.tick(
                        camera_frame,
                        (camera.width, camera.height),
                        camera_frame_id,
                        lidar_frame,
                        len(people),
                        started_at,
                    )
                else:
                    running = tk_view.pump_events()
            else:
                time.sleep(0.005)
    finally:
        if tk_view is not None:
            tk_view.destroy()
        if open3d_view is not None:
            open3d_view.destroy()
        for actor in reversed(actors):
            if actor is not None and actor.is_alive:
                actor.destroy()
        traffic_manager.set_synchronous_mode(False)
        world.apply_settings(original_settings)
        if args.viewer == "pygame":
            pygame.quit()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("-p", "--port", default=2000, type=int)
    parser.add_argument("--tm-port", default=8000, type=int)
    parser.add_argument("--timeout", default=10.0, type=float)
    parser.add_argument("--width", default=1280, type=int)
    parser.add_argument("--height", default=720, type=int)
    parser.add_argument("--viewer", choices=("tk", "pygame", "spectator"), default="tk")
    parser.add_argument("--viewer-fps", default=15.0, type=float)
    parser.add_argument("--duration-seconds", default=0.0, type=float)
    parser.add_argument("--no-open3d", action="store_true")
    parser.add_argument("--show-gt-boxes", action="store_true", default=True)
    parser.add_argument("--hide-gt-boxes", dest="show_gt_boxes", action="store_false")
    parser.add_argument("--save-dataset", action="store_true")
    parser.add_argument("--save-once", action="store_true")
    parser.add_argument("--dataset-dir", default=os.path.join(SCRIPT_DIR, "exam_dataset"))
    parser.add_argument("--dataset-every-n-frames", default=0, type=int)
    parser.add_argument("--open3d-update-hz", default=10.0, type=float)
    parser.add_argument("--open3d-max-points", default=500000, type=int)
    parser.add_argument("--fixed-delta-seconds", default=0.05, type=float)
    parser.add_argument("--clear-existing-npcs", action="store_true")
    parser.add_argument("--vehicle-filter", default="vehicle.*")
    parser.add_argument("--vehicle-generation", default="2")
    parser.add_argument("--static-people", default=20, type=int)
    parser.add_argument("--people-filter", default="walker.pedestrian.*")
    parser.add_argument("--people-generation", default="All")
    parser.add_argument("--people-radius", default=10.0, type=float)
    parser.add_argument("--people-min-distance", default=2.0, type=float)
    parser.add_argument("--people-attempts", default=5000, type=int)
    parser.add_argument("--people-sector-cycles", default=30, type=int)
    parser.add_argument("--lidar-channels", default=64, type=int)
    parser.add_argument("--lidar-range", default=100.0, type=float)
    parser.add_argument("--lidar-points-per-second", default=500000, type=int)
    parser.add_argument("--lidar-rotation-frequency", default=20.0, type=float)
    parser.add_argument("--lidar-upper-fov", default=10.0, type=float)
    parser.add_argument("--lidar-lower-fov", default=-30.0, type=float)
    parser.add_argument("--lidar-noise-stddev", default=0.0, type=float)
    parser.add_argument("--lidar-dropoff-general-rate", default=0.0, type=float)
    parser.add_argument("--lidar-dropoff-intensity-limit", default=1.0, type=float)
    parser.add_argument("--lidar-dropoff-zero-intensity", default=0.0, type=float)
    parser.add_argument("--lidar-atmosphere-attenuation-rate", default=0.0, type=float)
    parser.add_argument("--lidar-z-offset", default=0.6, type=float)
    parser.add_argument("--drive-throttle", default=0.55, type=float)
    parser.add_argument("--reverse-throttle", default=0.35, type=float)
    parser.add_argument("--drive-brake", default=0.55, type=float)
    parser.add_argument("--drive-steer", default=0.30, type=float)
    parser.add_argument("--throttle-ramp-rate", default=0.9, type=float)
    parser.add_argument("--throttle-release-rate", default=2.5, type=float)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
