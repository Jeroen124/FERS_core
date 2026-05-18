from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

Point2 = Tuple[float, float]
Point3 = Tuple[float, float, float]

TOL = 1.0e-9


def triangulate_surface_polygon(
    polygon: Iterable[Point3],
    *,
    mesh_size: float | None = None,
) -> List[List[Point3]]:
    vertices = _remove_duplicate_tail([_coerce_point3(vertex) for vertex in polygon])
    if len(vertices) < 3:
        raise ValueError("PlateSurface requires at least three vertices.")

    origin, axis_u, axis_v, normal = _build_plane_basis(vertices)
    densified = _densify_edges(vertices, mesh_size)
    vertices_2d = [_project_to_2d(point, origin, axis_u, axis_v) for point in densified]

    if _signed_area(vertices_2d) < 0.0:
        densified.reverse()
        vertices_2d.reverse()
        normal = tuple(-component for component in normal)

    triangles = _ear_clip(vertices_2d)
    return [[densified[i], densified[j], densified[k]] for i, j, k in triangles]


def _coerce_point3(point: Sequence[float]) -> Point3:
    if len(point) != 3:
        raise ValueError("Expected 3D point.")
    return (float(point[0]), float(point[1]), float(point[2]))


def _remove_duplicate_tail(vertices: list[Point3]) -> list[Point3]:
    if len(vertices) > 1 and _distance3(vertices[0], vertices[-1]) <= TOL:
        return vertices[:-1]
    return vertices


def _build_plane_basis(vertices: list[Point3]) -> tuple[Point3, Point3, Point3, Point3]:
    origin = vertices[0]
    axis_u = None
    normal = None

    for index in range(1, len(vertices) - 1):
        edge_a = _sub3(vertices[index], origin)
        edge_b = _sub3(vertices[index + 1], origin)
        if axis_u is None and _norm3(edge_a) > TOL:
            axis_u = _normalize3(edge_a)
        candidate = _cross3(edge_a, edge_b)
        if _norm3(candidate) > TOL:
            normal = _normalize3(candidate)
            break

    if axis_u is None or normal is None:
        raise ValueError("PlateSurface polygon is degenerate.")

    for vertex in vertices[1:]:
        if abs(_dot3(_sub3(vertex, origin), normal)) > 1.0e-7:
            raise ValueError("PlateSurface polygon must be planar.")

    axis_v = _normalize3(_cross3(normal, axis_u))
    return origin, axis_u, axis_v, normal


def _densify_edges(vertices: list[Point3], mesh_size: float | None) -> list[Point3]:
    if mesh_size is None or mesh_size <= 0.0:
        return vertices

    densified: list[Point3] = []
    count = len(vertices)
    for index in range(count):
        start = vertices[index]
        end = vertices[(index + 1) % count]
        edge = _sub3(end, start)
        length = _norm3(edge)
        segments = max(1, int(math.ceil(length / mesh_size)))
        for segment in range(segments):
            t = segment / segments
            densified.append(
                (
                    start[0] + edge[0] * t,
                    start[1] + edge[1] * t,
                    start[2] + edge[2] * t,
                )
            )

    return _remove_consecutive_duplicates(densified)


def _remove_consecutive_duplicates(vertices: list[Point3]) -> list[Point3]:
    if not vertices:
        return vertices

    deduped = [vertices[0]]
    for vertex in vertices[1:]:
        if _distance3(vertex, deduped[-1]) > TOL:
            deduped.append(vertex)
    if len(deduped) > 1 and _distance3(deduped[0], deduped[-1]) <= TOL:
        deduped.pop()
    return deduped


def _project_to_2d(point: Point3, origin: Point3, axis_u: Point3, axis_v: Point3) -> Point2:
    relative = _sub3(point, origin)
    return (_dot3(relative, axis_u), _dot3(relative, axis_v))


def _ear_clip(vertices: list[Point2]) -> list[tuple[int, int, int]]:
    if len(vertices) < 3:
        raise ValueError("Need at least three vertices to triangulate.")

    indices = list(range(len(vertices)))
    triangles: list[tuple[int, int, int]] = []

    while len(indices) > 3:
        ear_found = False
        for offset, current in enumerate(indices):
            previous = indices[offset - 1]
            following = indices[(offset + 1) % len(indices)]
            a = vertices[previous]
            b = vertices[current]
            c = vertices[following]

            if _cross2(_sub2(b, a), _sub2(c, b)) <= TOL:
                continue

            if any(
                candidate not in {previous, current, following}
                and _point_in_triangle(vertices[candidate], a, b, c)
                for candidate in indices
            ):
                continue

            triangles.append((previous, current, following))
            del indices[offset]
            ear_found = True
            break

        if not ear_found:
            raise ValueError(
                "PlateSurface polygon could not be triangulated. "
                "Use a simple non-self-intersecting polygon."
            )

    triangles.append((indices[0], indices[1], indices[2]))
    return triangles


def _point_in_triangle(point: Point2, a: Point2, b: Point2, c: Point2) -> bool:
    v0 = _sub2(c, a)
    v1 = _sub2(b, a)
    v2 = _sub2(point, a)

    dot00 = _dot2(v0, v0)
    dot01 = _dot2(v0, v1)
    dot02 = _dot2(v0, v2)
    dot11 = _dot2(v1, v1)
    dot12 = _dot2(v1, v2)

    denominator = dot00 * dot11 - dot01 * dot01
    if abs(denominator) <= TOL:
        return False

    inv = 1.0 / denominator
    u = (dot11 * dot02 - dot01 * dot12) * inv
    v = (dot00 * dot12 - dot01 * dot02) * inv
    return u >= -TOL and v >= -TOL and u + v <= 1.0 + TOL


def _signed_area(vertices: list[Point2]) -> float:
    area = 0.0
    for index, point in enumerate(vertices):
        next_point = vertices[(index + 1) % len(vertices)]
        area += point[0] * next_point[1] - next_point[0] * point[1]
    return 0.5 * area


def _sub2(a: Point2, b: Point2) -> Point2:
    return (a[0] - b[0], a[1] - b[1])


def _dot2(a: Point2, b: Point2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _cross2(a: Point2, b: Point2) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _sub3(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot3(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross3(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm3(a: Point3) -> float:
    return math.sqrt(_dot3(a, a))


def _distance3(a: Point3, b: Point3) -> float:
    return _norm3(_sub3(a, b))


def _normalize3(a: Point3) -> Point3:
    norm = _norm3(a)
    if norm <= TOL:
        raise ValueError("Cannot normalize zero-length vector.")
    return (a[0] / norm, a[1] / norm, a[2] / norm)
