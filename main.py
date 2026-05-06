"""
Wood Sculpture Slicer - Komut satiri arayuzu.

Tum is mantigi slicer.pipeline.run_pipeline()'da. Bu dosya sadece
argparse + cagri.
"""
import argparse
import sys
from slicer.pipeline import run_pipeline


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
                        help="Olcekleme hangi eksende (default: Z)")

    # Kerf ve pin parametreleri
    parser.add_argument("--kerf", type=float, default=0.08,
                        help="Lazer kerf telafisi mm (default: 0.08, diyot lazer)")
    parser.add_argument("--pin-diameter", type=float, default=3.0,
                        help="Hizalama pin/dowel capi mm (default: 3.0)")
    parser.add_argument("--pin-min-size", type=float, default=30.0,
                        help="Bu boyuttan kucuk parcaya pin koyma (default: 30 mm)")
    parser.add_argument("--pin-grid-size", type=float, default=60.0,
                        help="Her iki boyut da bundan buyukse 2x2 grid pin "
                             "(default: 60 mm)")
    parser.add_argument("--edge-tick", action='store_true',
                        help="Plaka kenarina kucuk numara ekle (montajda yandan okunur)")

    # Cikti tercihleri
    parser.add_argument("--format", choices=['dxf', 'svg', 'both'], default='both',
                        help="Cikti formati (default: both)")
    parser.add_argument("--export", action='store_true',
                        help="DXF/SVG cikti uretmek icin bu bayragi kullan")
    parser.add_argument("--no-preview", action='store_true',
                        help="Onizleme PNG uretme (hizli calistir)")
    parser.add_argument("--output-dir", default="output",
                        help="Cikti klasoru (default: output)")

    args = parser.parse_args()

    # Format listesi
    if args.format == 'both':
        formats = ['dxf', 'svg']
    else:
        formats = [args.format]

    # Pipeline'i calistir
    result = run_pipeline(
        model_path=args.model_path,
        output_dir=args.output_dir,
        axis=args.axis,
        size_axis=args.size_axis,
        size_mm=args.size,
        thickness_mm=args.thickness,
        kerf_mm=args.kerf,
        pin_diameter_mm=args.pin_diameter,
        pin_min_size_mm=args.pin_min_size,
        pin_grid_size_mm=args.pin_grid_size,
        edge_tick=args.edge_tick,
        formats=formats,
        generate_preview=not args.no_preview,
        export=args.export,
        verbose=True,
    )

    # Export yapilmadiysa kullaniciyi bilgilendir
    if not args.export and result['success']:
        print("\n(!) DXF/SVG cikti uretilmedi. Uretmek icin --export bayragini ekle.")
        print("    Ornek: python3 main.py models/Hermes.stl --export")

    # Hata durumunda exit code 1
    if not result['success']:
        sys.exit(1)


if __name__ == "__main__":
    main()