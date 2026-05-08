"""
Nesting: 2D bin packing ile dilimleri plywood plakalarina yerlestir.
Her sheet icin ayri DXF ve SVG uretir.

Algoritma: rectpack (guillotine bin packing)
- Hizli, deterministik
- Opsiyonel 90 derece rotasyon
- Standart (A4/A3) veya ozel plaka boyutu
"""
import os
import io
import math
import logging
import zipfile
from dataclasses import dataclass, field
from typing import Optional

import rectpack
from rectpack import newPacker, PackingMode, PackingBin, SORT_RATIO
from shapely.affinity import translate, rotate
import ezdxf
import svgwrite

logger = logging.getLogger(__name__)

# Standart plaka boyutlari (mm)
SHEET_SIZES = {
    'A4':     (210, 297),
    'A3':     (297, 420),
    'A2':     (420, 594),
    'A1':     (594, 841),
    'custom': None,  # kullanici girer
}


@dataclass
class NestingParams:
    """Nesting parametreleri."""
    sheet_width: float = 297.0      # mm
    sheet_height: float = 420.0     # mm
    gap: float = 2.0                # parcalar arasi bosluk mm
    allow_rotation: bool = True     # 90 derece rotasyona izin ver
    preserve_grain: bool = False    # ahsap doku yonu koru (rotasyon yok)

    def __post_init__(self):
        if self.preserve_grain:
            self.allow_rotation = False


@dataclass
class NestedItem:
    """Yerlestirilmis tek bir dilim parcasi."""
    slice_index: int        # orijinal dilim numarasi
    part_index: int         # dilim icindeki parca numarasi (adaciklar icin)
    sheet_index: int        # hangi plakaya yerlestirildi
    x: float               # plaka uzerindeki X pozisyonu (mm)
    y: float               # plaka uzerindeki Y pozisyonu (mm)
    width: float           # parca genisligi (mm)
    height: float          # parca yuksekligi (mm)
    rotated: bool          # 90 derece donduruldu mu
    polygon: object        # shapely Polygon (orijinal, transform edilmemis)
    pins: list             # pin noktalari (shapely Point listesi)
    pin_diameter: float    # pin capi mm


@dataclass
class NestingSheet:
    """Tek bir plaka ve uzerindeki parcalar."""
    index: int
    width: float
    height: float
    items: list = field(default_factory=list)

    @property
    def item_count(self):
        return len(self.items)

    @property
    def used_area(self):
        return sum(i.width * i.height for i in self.items)

    @property
    def total_area(self):
        return self.width * self.height

    @property
    def utilization_pct(self):
        if self.total_area <= 0:
            return 0.0
        return round(self.used_area / self.total_area * 100, 1)


@dataclass
class NestingResult:
    """Tum nesting sonucu."""
    sheets: list = field(default_factory=list)
    params: NestingParams = field(default_factory=NestingParams)
    total_items: int = 0
    placed_items: int = 0
    unplaced_items: int = 0

    @property
    def sheet_count(self):
        return len(self.sheets)

    @property
    def avg_utilization(self):
        if not self.sheets:
            return 0.0
        return round(sum(s.utilization_pct for s in self.sheets) / len(self.sheets), 1)


# =====================================================================
# Ana nesting fonksiyonu
# =====================================================================

def nest_slices(processed_slices: list, params: NestingParams) -> NestingResult:
    """
    Islenmis dilimleri (process_slice ciktisi) plywood plakalarina yerlestir.

    Args:
        processed_slices: exporter.process_slice() ciktilari listesi
        params: NestingParams

    Returns:
        NestingResult
    """
    gap = params.gap
    sw = params.sheet_width
    sh = params.sheet_height

    # Tum parcalari (polygon + pin) listele
    all_parts = []
    for ps in processed_slices:
        if not ps['polygons']:
            continue
        for pi, poly in enumerate(ps['polygons']):
            bounds = poly.bounds
            w = bounds[2] - bounds[0]
            h = bounds[3] - bounds[1]
            all_parts.append({
                'slice_index': ps['index'],
                'part_index': pi,
                'polygon': poly,
                'pins': ps['pins'],
                'pin_diameter': ps['pin_diameter'],
                'orig_w': w,
                'orig_h': h,
                'orig_minx': bounds[0],
                'orig_miny': bounds[1],
            })

    total = len(all_parts)

    if total == 0:
        return NestingResult(params=params, total_items=0)

    # rectpack: her parca icin (genislik + gap, yukseklik + gap) dikdortgen
    packer = newPacker(
        mode=PackingMode.Offline,
        bin_algo=PackingBin.BFF,   # Best Fit First
        sort_algo=SORT_RATIO,
        rotation=params.allow_rotation,
    )

    # Parcalari ekle (rid = part listesindeki index)
    for i, part in enumerate(all_parts):
        pw = part['orig_w'] + gap
        ph = part['orig_h'] + gap
        packer.add_rect(pw, ph, rid=i)

    # Sinirli sayida plaka ekle (max 999 plaka yeterli)
    for _ in range(999):
        packer.add_bin(sw, sh)

    packer.pack()

    # Sonuclari isle
    sheet_map = {}  # sheet_index -> NestingSheet
    placed_ids = set()

    for rect in packer.rect_list():
        # rect = (bin_index, x, y, w, h, rid)
        bin_idx, rx, ry, rw, rh, rid = rect
        part = all_parts[rid]

        if bin_idx not in sheet_map:
            sheet_map[bin_idx] = NestingSheet(
                index=bin_idx,
                width=sw,
                height=sh,
            )

        # Rotasyon kontrolu: rectpack genislik/yuksekligi degistirdiyse dondurulmustur
        orig_w_gap = part['orig_w'] + gap
        orig_h_gap = part['orig_h'] + gap
        rotated = not (
            abs(rw - orig_w_gap) < 0.01 and
            abs(rh - orig_h_gap) < 0.01
        )

        # Parca boyutlari (gap cikarilmis)
        placed_w = rw - gap
        placed_h = rh - gap

        item = NestedItem(
            slice_index=part['slice_index'],
            part_index=part['part_index'],
            sheet_index=bin_idx,
            x=rx,
            y=ry,
            width=placed_w,
            height=placed_h,
            rotated=rotated,
            polygon=part['polygon'],
            pins=part['pins'],
            pin_diameter=part['pin_diameter'],
        )
        sheet_map[bin_idx].items.append(item)
        placed_ids.add(rid)

    sheets = [sheet_map[i] for i in sorted(sheet_map.keys())]
    unplaced = total - len(placed_ids)

    return NestingResult(
        sheets=sheets,
        params=params,
        total_items=total,
        placed_items=len(placed_ids),
        unplaced_items=unplaced,
    )


# =====================================================================
# Polygon transform (plakadaki pozisyona tasima + rotasyon)
# =====================================================================

def _transform_polygon(poly, item: NestedItem, gap: float):
    """
    Polygon'u plakadaki hedef pozisyona tasir.
    Rotasyon uygulandiysa once 90 derece dondurur.
    """
    bounds = poly.bounds
    minx, miny = bounds[0], bounds[1]

    if item.rotated:
        # 90 derece saat yonunde dondur (kendi merkezinde)
        cx = (bounds[0] + bounds[2]) / 2
        cy = (bounds[1] + bounds[3]) / 2
        poly = rotate(poly, -90, origin=(cx, cy))
        bounds = poly.bounds
        minx, miny = bounds[0], bounds[1]

    # Plakadaki pozisyona tasir (gap/2 ic bosluk birak)
    dx = item.x + gap / 2 - minx
    dy = item.y + gap / 2 - miny
    return translate(poly, dx, dy)


def _transform_pin(pin, item: NestedItem, poly_orig, gap: float):
    """Pin noktasini polygon ile ayni transformasyonla tasir."""
    from shapely.geometry import Point
    from shapely.affinity import translate as sh_translate, rotate as sh_rotate

    bounds = poly_orig.bounds
    minx, miny = bounds[0], bounds[1]

    px, py = pin.x, pin.y

    if item.rotated:
        cx = (bounds[0] + bounds[2]) / 2
        cy = (bounds[1] + bounds[3]) / 2
        # 90 derece saat yonunde rotasyon formulu
        nx = cx + (py - cy)
        ny = cy - (px - cx)
        px, py = nx, ny
        # Yeni bounds
        rpoly = rotate(poly_orig, -90, origin=(cx, cy))
        rbounds = rpoly.bounds
        minx, miny = rbounds[0], rbounds[1]

    dx = item.x + gap / 2 - minx
    dy = item.y + gap / 2 - miny
    return Point(px + dx, py + dy)


# =====================================================================
# DXF export
# =====================================================================

def export_sheet_to_dxf(sheet: NestingSheet, output_path: str,
                         params: NestingParams, model_name: str = "model"):
    """Tek bir plakay DXF olarak yazar."""
    doc = ezdxf.new(dxfversion='R2010', setup=True)
    msp = doc.modelspace()

    # Layerlar
    for name, color in [('SHEET', 2), ('CUT', 1), ('PIN', 5),
                         ('ENGRAVE', 3), ('BORDER', 6)]:
        if name not in doc.layers:
            doc.layers.add(name, color=color)

    # Plaka siniri (kesim yapilmaz, referans icin)
    msp.add_lwpolyline(
        [(0, 0), (sheet.width, 0),
         (sheet.width, sheet.height), (0, sheet.height), (0, 0)],
        close=True,
        dxfattribs={'layer': 'BORDER'}
    )

    gap = params.gap

    for item in sheet.items:
        poly = item.polygon
        transformed = _transform_polygon(poly, item, gap)

        # Dis kontur
        exterior = list(transformed.exterior.coords)
        msp.add_lwpolyline(exterior, close=True, dxfattribs={'layer': 'CUT'})

        # Ic delikler
        for interior in transformed.interiors:
            msp.add_lwpolyline(
                list(interior.coords), close=True,
                dxfattribs={'layer': 'CUT'}
            )

        # Pin delikleri
        pin_radius = item.pin_diameter / 2.0
        for pin in item.pins:
            tp = _transform_pin(pin, item, poly, gap)
            msp.add_circle(
                center=(tp.x, tp.y),
                radius=pin_radius,
                dxfattribs={'layer': 'PIN'}
            )

        # Numara gravuru
        rep = transformed.representative_point()
        label = f"{item.slice_index:02d}"
        if item.rotated:
            label += "R"
        msp.add_text(
            label,
            dxfattribs={
                'layer': 'ENGRAVE',
                'height': 3.0,
                'insert': (rep.x, rep.y),
            }
        )

    doc.saveas(output_path)


# =====================================================================
# SVG export
# =====================================================================

def export_sheet_to_svg(sheet: NestingSheet, output_path: str,
                         params: NestingParams, model_name: str = "model"):
    """Tek bir plakay SVG olarak yazar."""
    w = sheet.width
    h = sheet.height
    gap = params.gap

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{w}mm", f"{h}mm"),
        viewBox=f"0 0 {w} {h}",
        profile='tiny',
    )

    def to_svg(x, y):
        return (x, h - y)

    # Plaka siniri
    dwg.add(dwg.rect(
        insert=(0, 0), size=(w, h),
        stroke='#444', fill='none', stroke_width=0.3,
        stroke_dasharray='5,3'
    ))

    for item in sheet.items:
        poly = item.polygon
        transformed = _transform_polygon(poly, item, gap)

        # Dis kontur
        ext_pts = [to_svg(x, y) for x, y in transformed.exterior.coords]
        dwg.add(dwg.polygon(
            points=ext_pts,
            stroke='red', fill='none', stroke_width=0.1
        ))

        # Ic delikler
        for interior in transformed.interiors:
            int_pts = [to_svg(x, y) for x, y in interior.coords]
            dwg.add(dwg.polygon(
                points=int_pts,
                stroke='red', fill='none', stroke_width=0.1
            ))

        # Pin delikleri
        r = item.pin_diameter / 2.0
        for pin in item.pins:
            tp = _transform_pin(pin, item, poly, gap)
            cx, cy = to_svg(tp.x, tp.y)
            dwg.add(dwg.circle(
                center=(cx, cy), r=r,
                stroke='blue', fill='none', stroke_width=0.1
            ))

        # Numara
        rep = transformed.representative_point()
        rx, ry = to_svg(rep.x, rep.y)
        label = f"{item.slice_index:02d}"
        if item.rotated:
            label += "R"
        dwg.add(dwg.text(
            label,
            insert=(rx, ry),
            fill='green', font_size=3,
            font_family='Arial',
            text_anchor='middle',
        ))

    dwg.save()


# =====================================================================
# Tum sheet'leri export et
# =====================================================================

def export_nesting(result: NestingResult, output_dir: str,
                   model_name: str = "model",
                   formats: list = None) -> dict:
    """
    Tum sheet'leri DXF ve/veya SVG olarak yazar.

    Returns:
        {
            'dxf_dir': str,
            'svg_dir': str,
            'sheet_count': int,
            'report': str,   # okunabilir ozet
        }
    """
    if formats is None:
        formats = ['dxf', 'svg']

    dxf_dir = os.path.join(output_dir, 'nesting_dxf')
    svg_dir = os.path.join(output_dir, 'nesting_svg')

    if 'dxf' in formats:
        os.makedirs(dxf_dir, exist_ok=True)
    if 'svg' in formats:
        os.makedirs(svg_dir, exist_ok=True)

    params = result.params

    for sheet in result.sheets:
        base = f"{model_name}_sheet_{sheet.index + 1:02d}"

        if 'dxf' in formats:
            export_sheet_to_dxf(
                sheet,
                os.path.join(dxf_dir, base + '.dxf'),
                params, model_name
            )
        if 'svg' in formats:
            export_sheet_to_svg(
                sheet,
                os.path.join(svg_dir, base + '.svg'),
                params, model_name
            )

    # Ozet rapor
    report_lines = [
        f"NESTING REPORT: {model_name}",
        f"{'=' * 50}",
        f"Sheet size      : {params.sheet_width} x {params.sheet_height} mm",
        f"Gap             : {params.gap} mm",
        f"Rotation        : {'yes' if params.allow_rotation else 'no (grain preserved)'}",
        f"Total parts     : {result.total_items}",
        f"Placed          : {result.placed_items}",
        f"Unplaced        : {result.unplaced_items}",
        f"Sheets used     : {result.sheet_count}",
        f"Avg utilization : {result.avg_utilization}%",
        "",
        f"{'Sheet':<8} {'Parts':<8} {'Utilization':<15}",
        "-" * 35,
    ]
    for sheet in result.sheets:
        report_lines.append(
            f"{sheet.index + 1:<8} {sheet.item_count:<8} {sheet.utilization_pct}%"
        )

    report = "\n".join(report_lines)

    # Raporu dosyaya yaz
    report_path = os.path.join(output_dir, 'nesting_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    return {
        'dxf_dir': dxf_dir if 'dxf' in formats else None,
        'svg_dir': svg_dir if 'svg' in formats else None,
        'sheet_count': result.sheet_count,
        'report': report,
        'report_path': report_path,
    }