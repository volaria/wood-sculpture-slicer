"""
Pipeline: tum boru hattini tek fonksiyonda calistirir.
CLI ve Flask web arayuzu ayni fonksiyonu cagirir.
"""
import os
from pathlib import Path
from typing import Optional

from .loader import load_mesh, analyze_mesh
from .slicer import (
    slice_mesh, AXIS_X, AXIS_Y, AXIS_Z, AXIS_NAMES,
)
from .viewer import plot_slice_grid, plot_assembly_preview
from .exporter import export_all

AXIS_MAP = {'X': AXIS_X, 'Y': AXIS_Y, 'Z': AXIS_Z}


def run_pipeline(
        model_path: str,
        output_dir: str = 'output',
        *,
        # Model meta
        model_name: Optional[str] = None,
        # Dilimleme parametreleri
        axis: str = 'X',
        size_axis: str = 'Z',
        size_mm: float = 250.0,
        thickness_mm: float = 3.0,
        # Kerf ve pin parametreleri
        kerf_mm: float = 0.08,
        pin_diameter_mm: float = 3.0,
        pin_min_size_mm: float = 30.0,
        pin_grid_size_mm: float = 60.0,
        edge_tick: bool = False,
        # Cikti tercihleri
        formats: Optional[list] = None,
        generate_preview: bool = True,
        export: bool = True,
        # Loglama
        verbose: bool = True,
        log_callback=None,
) -> dict:
    """
    Tum boru hattini calistirir: model yukle -> analiz -> dilim -> onizle -> export.

    Args:
        model_path: OBJ veya STL dosya yolu
        output_dir: cikti klasoru (PNG, DXF/, SVG/, assembly_guide.txt buraya yazilir)
        model_name: cikti dosyalarinin prefix'i (orn: 'Hermes' -> Hermes_slice_00.dxf).
                    None ise model_path dosya adindan turetilir.
        axis: dilimleme ekseni 'X', 'Y' veya 'Z'
        size_axis: olcekleme hangi eksen uzerinden ('X', 'Y', 'Z')
        size_mm: hedef heykel boyutu mm (size_axis ekseninde)
        thickness_mm: plywood kalinligi mm
        kerf_mm: lazer kerf telafisi mm (disa offset)
        pin_diameter_mm: hizalama pin/dowel capi mm
        pin_min_size_mm: bu boyuttan kucuk parcaya pin koyma
        pin_grid_size_mm: her iki boyut da bundan buyukse 2x2 grid pin
        edge_tick: True ise plakalara kenar mikro numara ekle
        formats: cikti formati listesi: ['dxf'], ['svg'] veya ['dxf', 'svg'].
                 None ise default ['dxf', 'svg'].
        generate_preview: True ise PNG onizleme uretir (grid + overlay)
        export: True ise DXF/SVG cikti uretir; False ise sadece onizleme
        verbose: True ise stdout'a print eder
        log_callback: opsiyonel callback fonksiyonu (str -> None);
                      verilirse her log mesaji ona iletilir (Flask icin yararli)

    Returns:
        dict: {
            'success': bool,
            'error': Optional[str],
            'mesh_info': dict,           # vertex/face sayisi, boyutlar, watertight vb.
            'slice_report': dict,        # dilim sayisi, olcek faktoru, plate sayilari
            'preview_paths': dict,       # {'grid': str, 'overlay': str} veya bos
            'export_paths': dict,        # {'dxf_dir': str, 'svg_dir': str, 'assembly_guide': str}
            'output_dir': str,           # absolute path
            'plate_summary': list,       # her plaka icin {'index', 'parts', 'width', 'height', 'pins'}
        }
    """
    if formats is None:
        formats = ['dxf', 'svg']

    # Log helper'i
    def log(msg: str):
        if verbose:
            print(msg)
        if log_callback is not None:
            try:
                log_callback(msg)
            except Exception:
                pass  # log callback hatalarinin pipeline'i bozmamasini sagla

    # Sonuc iskeleti
    result_data = {
        'success': False,
        'error': None,
        'mesh_info': {},
        'slice_report': {},
        'preview_paths': {},
        'export_paths': {},
        'output_dir': os.path.abspath(output_dir),
        'plate_summary': [],
    }

    try:
        # Eksen dogrulama
        if axis not in AXIS_MAP:
            raise ValueError(f"Gecersiz axis: {axis}. X, Y veya Z olmali.")
        if size_axis not in AXIS_MAP:
            raise ValueError(f"Gecersiz size_axis: {size_axis}. X, Y veya Z olmali.")

        slice_axis_idx = AXIS_MAP[axis]
        size_axis_idx = AXIS_MAP[size_axis]

        # Model adi: parametre verilmediyse dosya adindan turet
        if model_name is None:
            model_name = Path(model_path).stem

        # Cikti klasoru hazirla
        os.makedirs(output_dir, exist_ok=True)

        # 1. YUKLE VE ANALIZ
        log(f"Model yukleniyor: {model_path}")
        mesh = load_mesh(model_path)
        info = analyze_mesh(mesh)

        result_data['mesh_info'] = {
            'vertex_count': int(info['vertex_count']),
            'face_count': int(info['face_count']),
            'is_watertight': bool(info['is_watertight']),
            'is_winding_consistent': bool(info['is_winding_consistent']),
            'extents': [float(x) for x in info['extents']],
            'bounds_min': [float(x) for x in info['bounds_min']],
            'bounds_max': [float(x) for x in info['bounds_max']],
            'volume': float(info['volume']) if info['volume'] is not None else None,
        }

        log(f"  Vertex: {info['vertex_count']:,}  Face: {info['face_count']:,}")
        log(f"  Boyutlar: {info['extents'][0]:.2f} x "
            f"{info['extents'][1]:.2f} x {info['extents'][2]:.2f}")
        if not info['is_watertight']:
            log("  (!) Mesh kapali degil; bazi dilimler bos cikabilir.")

        # 2. DILIMLE
        log(f"\nDilimleme (eksen={axis}, plywood={thickness_mm}mm, "
            f"hedef={size_mm}mm @ {size_axis})...")

        slice_result = slice_mesh(
            mesh,
            plywood_thickness=thickness_mm,
            slice_axis=slice_axis_idx,
            target_size_mm=size_mm,
            target_axis=size_axis_idx,
        )

        result_data['slice_report'] = {
            'slice_axis': axis,
            'plywood_thickness': float(thickness_mm),
            'scale_factor': float(slice_result.scale_factor),
            'mesh_extents_mm': [float(x) for x in slice_result.mesh_extents_mm],
            'slice_count': int(slice_result.slice_count),
            'non_empty_count': int(slice_result.non_empty_count),
        }

        log(f"  Toplam dilim: {slice_result.slice_count}, "
            f"dolu: {slice_result.non_empty_count}")

        # 3. ONIZLEME (opsiyonel)
        if generate_preview:
            grid_path = os.path.join(output_dir, f"slices_grid_{axis}.png")
            overlay_path = os.path.join(output_dir, f"slices_overlay_{axis}.png")

            plot_slice_grid(slice_result, output_path=grid_path)
            plot_assembly_preview(slice_result, output_path=overlay_path)

            result_data['preview_paths'] = {
                'grid': os.path.abspath(grid_path),
                'overlay': os.path.abspath(overlay_path),
            }
            log(f"  Onizleme: {grid_path}")

        # 4. DXF/SVG EXPORT (opsiyonel)
        if export:
            log(f"\nExport (kerf={kerf_mm}mm, pin={pin_diameter_mm}mm, "
                f"edge_tick={'AC' if edge_tick else 'KAP'})...")

            processed_slices = export_all(
                slice_result,
                output_dir=output_dir,
                model_name=model_name,
                kerf_mm=kerf_mm,
                pin_diameter=pin_diameter_mm,
                formats=formats,
                min_dim_for_pin=pin_min_size_mm,
                min_dim_for_grid=pin_grid_size_mm,
                edge_tick=edge_tick,
            )

            # Plaka ozet listesi (Flask UI'de tablo olarak gostermek icin)
            plate_summary = []
            for ps in processed_slices:
                if not ps['polygons']:
                    continue
                all_b = [p.bounds for p in ps['polygons']]
                w = max(b[2] for b in all_b) - min(b[0] for b in all_b)
                h = max(b[3] for b in all_b) - min(b[1] for b in all_b)
                plate_summary.append({
                    'index': int(ps['index']),
                    'parts': len(ps['polygons']),
                    'width_mm': round(float(w), 1),
                    'height_mm': round(float(h), 1),
                    'pins': len(ps['pins']),
                })

            result_data['plate_summary'] = plate_summary

            export_paths = {
                'assembly_guide': os.path.abspath(
                    os.path.join(output_dir, 'assembly_guide.txt')
                ),
            }
            if 'dxf' in formats:
                export_paths['dxf_dir'] = os.path.abspath(
                    os.path.join(output_dir, 'dxf')
                )
            if 'svg' in formats:
                export_paths['svg_dir'] = os.path.abspath(
                    os.path.join(output_dir, 'svg')
                )
            result_data['export_paths'] = export_paths

        result_data['success'] = True
        log("\nIslem tamamlandi.")

    except FileNotFoundError as e:
        result_data['error'] = f"Dosya bulunamadi: {e}"
        log(f"HATA: {result_data['error']}")
    except ValueError as e:
        result_data['error'] = f"Gecersiz parametre: {e}"
        log(f"HATA: {result_data['error']}")
    except Exception as e:
        result_data['error'] = f"Beklenmeyen hata: {type(e).__name__}: {e}"
        log(f"HATA: {result_data['error']}")
        if verbose:
            import traceback
            traceback.print_exc()

    return result_data