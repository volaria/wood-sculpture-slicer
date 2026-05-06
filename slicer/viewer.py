"""
Dilim onizleme: tum dilimleri grid halinde matplotlib ile cizer.
"""
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
import numpy as np
from .slicer import SliceResult, AXIS_NAMES


def _polygon_to_mpl_patches(poly, **kwargs):
    patches = []
    exterior = np.array(poly.exterior.coords)
    patches.append(MplPolygon(exterior, closed=True, **kwargs))
    for interior in poly.interiors:
        hole_coords = np.array(interior.coords)
        hole_kwargs = dict(kwargs)
        hole_kwargs['facecolor'] = 'white'
        hole_kwargs['edgecolor'] = kwargs.get('edgecolor', 'black')
        patches.append(MplPolygon(hole_coords, closed=True, **hole_kwargs))
    return patches


def plot_slice_grid(result, output_path=None, cols=10, max_slices=None):
    slices_to_plot = [s for s in result.slices if s.polygons]
    if max_slices and len(slices_to_plot) > max_slices:
        idx = np.linspace(0, len(slices_to_plot) - 1, max_slices, dtype=int)
        slices_to_plot = [slices_to_plot[i] for i in idx]

    n = len(slices_to_plot)
    if n == 0:
        print("Cizilecek dilim yok.")
        return

    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 1.5, rows * 1.5))

    if rows == 1:
        axes = np.array([axes])
    if cols == 1:
        axes = axes.reshape(-1, 1)

    all_bounds = [s.bounds_2d for s in slices_to_plot if s.bounds_2d]
    if all_bounds:
        gminx = min(b[0] for b in all_bounds)
        gminy = min(b[1] for b in all_bounds)
        gmaxx = max(b[2] for b in all_bounds)
        gmaxy = max(b[3] for b in all_bounds)
        pad = max(gmaxx - gminx, gmaxy - gminy) * 0.05
        gminx -= pad
        gminy -= pad
        gmaxx += pad
        gmaxy += pad

    for i, ax in enumerate(axes.flat):
        if i < n:
            sl = slices_to_plot[i]
            for poly in sl.polygons:
                patches = _polygon_to_mpl_patches(
                    poly, facecolor='#d4a574', edgecolor='#5c3a1e', linewidth=0.5
                )
                for p in patches:
                    ax.add_patch(p)
            ax.set_xlim(gminx, gmaxx)
            ax.set_ylim(gminy, gmaxy)
            ax.set_aspect('equal')
            ax.set_title(f"#{sl.index}", fontsize=7)
            ax.set_xticks([])
            ax.set_yticks([])
        else:
            ax.axis('off')

    fig.suptitle(
        f"Dilimler ({AXIS_NAMES[result.slice_axis]} ekseni, "
        f"{result.plywood_thickness}mm plywood, "
        f"toplam {result.non_empty_count} dilim)",
        fontsize=12
    )
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=120, bbox_inches='tight')
        print(f"Kaydedildi: {output_path}")
    else:
        plt.show()
    plt.close()


def plot_assembly_preview(result, output_path=None):
    fig, ax = plt.subplots(figsize=(10, 8))
    cmap = plt.cm.copper
    n = result.non_empty_count
    plotted = 0

    for sl in result.slices:
        if not sl.polygons:
            continue
        color = cmap(plotted / max(n - 1, 1))
        plotted += 1
        for poly in sl.polygons:
            coords = np.array(poly.exterior.coords)
            ax.fill(coords[:, 0], coords[:, 1], color=color, alpha=0.15,
                    edgecolor=color, linewidth=0.4)

    ax.set_aspect('equal')
    ax.set_title(f"Tum dilimler ust uste - {AXIS_NAMES[result.slice_axis]} ekseni")
    ax.grid(True, alpha=0.3)

    if output_path:
        plt.savefig(output_path, dpi=120, bbox_inches='tight')
        print(f"Kaydedildi: {output_path}")
    else:
        plt.show()
    plt.close()