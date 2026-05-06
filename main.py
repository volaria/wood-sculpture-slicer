"""
Ahsap heykel dilimleyici - Ana giris noktasi.
"""
import argparse
import os
from pathlib import Path
from slicer.loader import load_mesh, analyze_mesh, print_mesh_report
from slicer.slicer import (
    slice_mesh, print_slice_report,
    AXIS_X, AXIS_Y, AXIS_Z, AXIS_NAMES,
)
from slicer.viewer import plot_slice_grid, plot_assembly_preview
from slicer.exporter import export_all


AXIS_MAP = {'X': AXIS_X, 'Y': AXIS_Y, 'Z': AXIS_Z}


def main():
    parser = argparse.ArgumentParser(
        description="Ahsap heykel dilimleyici - OBJ/STL'den lazer kesim DXF/SVG'ye"
    )

    # Giris dosyasi
    parser.add_argument("model_path", help="OBJ veya STL dosya yolu")

    # Dilimleme parametreleri
    parser.add_argument("--axis", choices=['X', 'Y', 'Z'], default='X',
                        help="Dilimleme ekseni (default: X - dikey profil dilimleri)")
    parser.add_argument("--thickness", type=float, default=3.0,
                        help="Plywood kalinligi mm (default: 3.0)")
    parser.add_argument("--size", type=float, default=250.0,
                        help="Hedef heykel boyutu mm (default: 250)")
    parser.add_argument("--size-axis", choices=['X', 'Y', 'Z'], default='Z',
                        help="Olcekleme hangi eksende (default: Z - heykel yuksekligi)")

    # Kerf ve pin parametreleri
    parser.add_argument("--kerf", type=float, default=0.08,
                        help="Lazer kerf telafisi mm (default: 0.08, diyot lazer icin tipik)")
    parser.add_argument("--pin-diameter", type=float, default=3.0,
                        help="Hizalama pin/dowel capi mm (default: 3.0)")
    parser.add_argument("--pin-min-size", type=float, default=30.0,
                        help="Bu boyuttan kucuk parcaya pin koyma (default: 30 mm)")
    parser.add_argument("--pin-grid-size", type=float, default=60.0,
                        help="Her iki boyut da bundan buyukse 2x2 grid pin (default: 60 mm)")
    parser.add_argument("--edge-tick", action='store_true',
                        help="Plaka kenarina kucuk numara ekle (montajda yandan okunur)")

    # Cikti formati
    parser.add_argument("--format", choices=['dxf', 'svg', 'both'], default='both',
                        help="Cikti formati (default: both)")
    parser.add_argument("--export", action='store_true',
                        help="DXF/SVG cikti uretmek icin bu bayragi kullan")
    parser.add_argument("--no-preview", action='store_true',
                        help="Onizleme PNG uretme (hizli calistir)")

    # Cikti yollari
    parser.add_argument("--output-dir", default="output",
                        help="Cikti klasoru (default: output)")
    parser.add_argument("--max-grid", type=int, default=None,
                        help="Grid'de gosterilecek max dilim")

    args = parser.parse_args()

    # Eksenleri map et
    slice_axis = AXIS_MAP[args.axis]
    size_axis = AXIS_MAP[args.size_axis]

    # Format listesi
    if args.format == 'both':
        formats = ['dxf', 'svg']
    else:
        formats = [args.format]

    # Model adi (dosya adindan, uzantisiz)
    model_name = Path(args.model_path).stem

    # 1. Yukle ve analiz et
    print(f"\nModel yukleniyor: {args.model_path}")
    mesh = load_mesh(args.model_path)
    info = analyze_mesh(mesh)
    print_mesh_report(info, args.model_path)

    # 2. Dilimle
    print(f"Dilimleme basliyor (eksen={args.axis}, "
          f"plywood={args.thickness}mm, hedef={args.size}mm "
          f"@ {AXIS_NAMES[size_axis]})...")

    result = slice_mesh(
        mesh,
        plywood_thickness=args.thickness,
        slice_axis=slice_axis,
        target_size_mm=args.size,
        target_axis=size_axis,
    )
    print_slice_report(result)

    # 3. Onizleme PNG (default acik)
    os.makedirs(args.output_dir, exist_ok=True)

    if not args.no_preview:
        grid_path = os.path.join(args.output_dir, f"slices_grid_{args.axis}.png")
        overlay_path = os.path.join(args.output_dir, f"slices_overlay_{args.axis}.png")
        plot_slice_grid(result, output_path=grid_path, max_slices=args.max_grid)
        plot_assembly_preview(result, output_path=overlay_path)

    # 4. DXF/SVG cikti (--export bayragi gerekli)
    if args.export:
        export_all(
            result,
            output_dir=args.output_dir,
            model_name=model_name,
            kerf_mm=args.kerf,
            pin_diameter=args.pin_diameter,
            formats=formats,
            min_dim_for_pin=args.pin_min_size,
            min_dim_for_grid=args.pin_grid_size,
            edge_tick=args.edge_tick,
        )
    else:
        print("\n(!) DXF/SVG cikti uretilmedi. Uretmek icin --export bayragini ekle.")
        print("    Ornek: python3 main.py models/Hermes.stl --export")

    print("\nIslem tamamlandi.\n")


if __name__ == "__main__":
    main()