"""
Mesh dilimleme: paralel duzlemlerle keserek 2D konturlar uretir.
"""
import trimesh
import numpy as np
from shapely.geometry import Polygon
from dataclasses import dataclass, field
from typing import Optional


AXIS_X = 0
AXIS_Y = 1
AXIS_Z = 2
AXIS_NAMES = {AXIS_X: 'X', AXIS_Y: 'Y', AXIS_Z: 'Z'}


@dataclass
class Slice:
    index: int
    axis_position: float
    polygons: list
    slice_axis: int

    @property
    def bounds_2d(self):
        if not self.polygons:
            return None
        all_bounds = [p.bounds for p in self.polygons]
        minx = min(b[0] for b in all_bounds)
        miny = min(b[1] for b in all_bounds)
        maxx = max(b[2] for b in all_bounds)
        maxy = max(b[3] for b in all_bounds)
        return (minx, miny, maxx, maxy)

    @property
    def total_area(self):
        return sum(p.area for p in self.polygons)


@dataclass
class SliceResult:
    slices: list = field(default_factory=list)
    slice_axis: int = AXIS_Z
    plywood_thickness: float = 3.0
    target_size: float = 0.0
    scale_factor: float = 1.0
    mesh_extents_mm: tuple = (0, 0, 0)

    @property
    def slice_count(self):
        return len(self.slices)

    @property
    def non_empty_count(self):
        return sum(1 for s in self.slices if s.polygons)


def scale_mesh_to_size(mesh, axis, target_size_mm):
    current_extent = mesh.extents[axis]
    if current_extent <= 0:
        raise ValueError(f"Mesh'in {AXIS_NAMES[axis]} ekseninde boyutu yok.")
    scale = target_size_mm / current_extent
    scaled = mesh.copy()
    scaled.apply_scale(scale)
    return scaled, scale


def slice_mesh(mesh, plywood_thickness=3.0, slice_axis=AXIS_Z,
               target_size_mm=None, target_axis=None):
    if target_axis is None:
        target_axis = slice_axis

    if target_size_mm is not None:
        scaled_mesh, scale = scale_mesh_to_size(mesh, target_axis, target_size_mm)
    else:
        scaled_mesh = mesh
        scale = 1.0

    bounds = scaled_mesh.bounds
    axis_min = bounds[0][slice_axis]
    axis_max = bounds[1][slice_axis]
    axis_extent = axis_max - axis_min

    n_slices = int(np.floor(axis_extent / plywood_thickness))
    if n_slices < 1:
        raise ValueError(
            f"Mesh cok kucuk: extent {axis_extent:.2f}mm < plywood {plywood_thickness}mm"
        )

    offset = (axis_extent - n_slices * plywood_thickness) / 2.0
    positions = np.array([
        axis_min + offset + plywood_thickness * (i + 0.5)
        for i in range(n_slices)
    ])

    plane_normal = np.zeros(3)
    plane_normal[slice_axis] = 1.0

    slices = []
    for i, pos in enumerate(positions):
        plane_origin = np.zeros(3)
        plane_origin[slice_axis] = pos

        section = scaled_mesh.section(
            plane_origin=plane_origin,
            plane_normal=plane_normal,
        )

        polygons_2d = []
        if section is not None:
            try:
                planar, _ = section.to_2D()
                for poly in planar.polygons_full:
                    if poly.is_valid and poly.area > 0.01:
                        polygons_2d.append(poly)
            except Exception as e:
                if i < 3:
                    print(f"  [DEBUG] Dilim #{i} icin hata: {type(e).__name__}: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            if i < 3:
                print(f"  [DEBUG] Dilim #{i}: section None dondu")

        slices.append(Slice(
            index=i,
            axis_position=float(pos),
            polygons=polygons_2d,
            slice_axis=slice_axis,
        ))

    return SliceResult(
        slices=slices,
        slice_axis=slice_axis,
        plywood_thickness=plywood_thickness,
        target_size=target_size_mm or axis_extent,
        scale_factor=scale,
        mesh_extents_mm=tuple(scaled_mesh.extents),
    )


def print_slice_report(result):
    print(f"\n{'='*60}")
    print(f"DILIMLEME RAPORU")
    print(f"{'='*60}")
    print(f"Dilim ekseni       : {AXIS_NAMES[result.slice_axis]}")
    print(f"Plywood kalinligi  : {result.plywood_thickness} mm")
    print(f"Olcek faktoru      : x{result.scale_factor:.4f}")
    print(f"Olceklenmis boyut  : "
          f"{result.mesh_extents_mm[0]:.1f} x "
          f"{result.mesh_extents_mm[1]:.1f} x "
          f"{result.mesh_extents_mm[2]:.1f} mm")
    print(f"Toplam dilim       : {result.slice_count}")
    print(f"Bos olmayan dilim  : {result.non_empty_count}")

    empty_count = result.slice_count - result.non_empty_count
    if empty_count > 0:
        print(f"(!) {empty_count} dilim bos cikti (mesh acigi olabilir)")

    poly_counts = [len(s.polygons) for s in result.slices if s.polygons]
    if poly_counts:
        print(f"\nDilim basina polygon (delik+ada):")
        print(f"  min={min(poly_counts)}  max={max(poly_counts)}  "
              f"ortalama={np.mean(poly_counts):.1f}")
    print(f"{'='*60}\n")