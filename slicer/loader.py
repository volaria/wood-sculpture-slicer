"""
Model yükleme ve temel mesh analizi.
"""
import trimesh
import numpy as np
from pathlib import Path


def load_mesh(file_path: str) -> trimesh.Trimesh:
    """OBJ veya STL dosyasını yükler ve Trimesh nesnesi döndürür."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")

    suffix = path.suffix.lower()
    if suffix not in ['.obj', '.stl']:
        raise ValueError(f"Desteklenmeyen format: {suffix}. Sadece .obj ve .stl destekleniyor.")

    mesh = trimesh.load(file_path, force='mesh')

    # Birden fazla mesh varsa (Scene) tek mesh'e birleştir
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate([
            trimesh.Trimesh(vertices=g.vertices, faces=g.faces)
            for g in mesh.geometry.values()
        ])

    return mesh


def analyze_mesh(mesh: trimesh.Trimesh) -> dict:
    """Mesh hakkında temel bilgileri döndürür."""
    bounds = mesh.bounds  # [[xmin,ymin,zmin],[xmax,ymax,zmax]]
    extents = mesh.extents  # [dx, dy, dz]

    info = {
        'vertex_count': len(mesh.vertices),
        'face_count': len(mesh.faces),
        'is_watertight': mesh.is_watertight,
        'is_winding_consistent': mesh.is_winding_consistent,
        'bounds_min': bounds[0],
        'bounds_max': bounds[1],
        'extents': extents,  # X, Y, Z boyutları
        'volume': mesh.volume if mesh.is_watertight else None,
        'center_mass': mesh.center_mass if mesh.is_watertight else mesh.centroid,
    }
    return info


def print_mesh_report(info: dict, file_path: str):
    """Mesh bilgilerini okunabilir şekilde yazdırır."""
    print(f"\n{'=' * 60}")
    print(f"MODEL ANALİZ RAPORU: {Path(file_path).name}")
    print(f"{'=' * 60}")
    print(f"Vertex sayısı     : {info['vertex_count']:,}")
    print(f"Face (üçgen) sayısı: {info['face_count']:,}")
    print(f"Watertight (kapalı): {'EVET' if info['is_watertight'] else 'HAYIR ⚠️'}")
    print(f"Winding tutarlı   : {'EVET' if info['is_winding_consistent'] else 'HAYIR ⚠️'}")

    print(f"\n--- BOYUTLAR (model birimi neyse o, genelde mm) ---")
    print(f"X ekseni: {info['extents'][0]:.2f}")
    print(f"Y ekseni: {info['extents'][1]:.2f}")
    print(f"Z ekseni: {info['extents'][2]:.2f}")

    print(f"\n--- BOUNDING BOX ---")
    print(f"Min: ({info['bounds_min'][0]:.2f}, {info['bounds_min'][1]:.2f}, {info['bounds_min'][2]:.2f})")
    print(f"Max: ({info['bounds_max'][0]:.2f}, {info['bounds_max'][1]:.2f}, {info['bounds_max'][2]:.2f})")

    if info['volume'] is not None:
        print(f"\nHacim: {info['volume']:.2f} (birim³)")

    # Uyarılar
    if not info['is_watertight']:
        print(f"\n⚠️  UYARI: Mesh kapalı değil. Dilimleme sırasında bazı dilimler")
        print(f"   açık polyline olabilir. Sonradan kapatma adımı gerekebilir.")

    print(f"{'=' * 60}\n")