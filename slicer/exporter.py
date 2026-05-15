"""
DXF ve SVG cikti uretimi: kerf compensation + hizalama delikleri + numaralandirma.
"""
import os
import ezdxf
import svgwrite
from shapely.geometry import Polygon, Point
from shapely.affinity import translate
from .slicer import SliceResult, Slice, AXIS_NAMES


# ============================================================
# KERF COMPENSATION
# ============================================================

def apply_kerf(polygon: Polygon, kerf_mm: float, direction: str = 'outward') -> Polygon:
    """
    Polygon'a kerf telafisi uygular (Shapely buffer).

    Args:
        polygon: shapely Polygon
        kerf_mm: kerf degeri mm (lazer ne kadar yakar)
        direction: 'outward' (disa offset) veya 'inward' (ice offset)

    Returns:
        Offset edilmis polygon
    """
    if kerf_mm <= 0:
        return polygon

    # Lazer kerf yariciapi kadar disa genisletmek gerekir ki
    # parca lazer keserken yandiktan sonra nominal boyutta kalsin
    offset = kerf_mm / 2.0
    if direction == 'inward':
        offset = -offset

    # Shapely buffer: pozitif disa, negatif ice
    # join_style=2 (mitre): keskin kosileri korur (yumuşatmaz)
    # cap_style=3 (square): uc noktalarda kare bitis
    result = polygon.buffer(offset, join_style=2, mitre_limit=2.0)

    # Buffer sonrasi MultiPolygon olabilir (nadir); en buyugunu al
    if result.geom_type == 'MultiPolygon':
        result = max(result.geoms, key=lambda p: p.area)

    return result


# ============================================================
# HIZALAMA DELIKLERI (DOWEL PINS)
# ============================================================

def generate_pin_holes(polygon: Polygon, pin_diameter: float = 3.0,
                       margin: float = 8.0,
                       min_dim_for_pin: float = 30.0,
                       min_dim_for_grid: float = 60.0) -> list:
    """
    Polygon icin hizalama delik konumlarini hesaplar.

    Strateji:
    - Her iki boyut da min_dim_for_grid'den buyukse: 2x2 grid (4 delik)
    - Sadece bir boyut min_dim_for_grid'den buyukse: o eksen boyunca 2 delik
    - En kucuk boyut min_dim_for_pin'den kucukse: delik yok
    - Aksi halde uzun eksen boyunca 2 delik

    Args:
        polygon: shapely Polygon (kerf uygulandiktan sonraki hali)
        pin_diameter: delik capi mm
        margin: pin merkezi kontur kenarindan en az bu kadar uzak olsun
        min_dim_for_pin: bu boyuttan kucuk parcaya pin koyma
        min_dim_for_grid: her iki boyut da bundan buyukse 2x2 grid

    Returns:
        list of shapely Point (delik merkezleri)
    """
    bounds = polygon.bounds
    minx, miny, maxx, maxy = bounds
    width = maxx - minx
    height = maxy - miny
    min_dim = min(width, height)
    max_dim = max(width, height)

    # Cok kucuk parca - pin yok
    if min_dim < min_dim_for_pin:
        return []

    # Polygon'un icinde margin kadar icerideki guvenli bolge
    safe_zone = polygon.buffer(-margin)
    if safe_zone.is_empty or safe_zone.area < 1:
        return []

    safe_bounds = safe_zone.bounds
    sminx, sminy, smaxx, smaxy = safe_bounds

    # Her iki boyut da yeterince buyuk -> 2x2 grid
    if width >= min_dim_for_grid and height >= min_dim_for_grid:
        # 4 koseye yakin pin: %25 ve %75 X, %25 ve %75 Y
        candidate_xs = [sminx + (smaxx - sminx) * 0.20,
                        sminx + (smaxx - sminx) * 0.80]
        candidate_ys = [sminy + (smaxy - sminy) * 0.20,
                        sminy + (smaxy - sminy) * 0.80]
        pins = []
        for x in candidate_xs:
            for y in candidate_ys:
                pt = Point(x, y)
                if safe_zone.contains(pt):
                    pins.append(pt)
                else:
                    pin = _find_nearest_safe_point(safe_zone, x, y)
                    if pin is not None:
                        pins.append(pin)
        return pins

    # Tek eksen boyunca 2 delik (uzun eksen)
    if width >= height:
        # Yatay yonelim - X boyunca 2 pin
        xs = [sminx + (smaxx - sminx) * 0.20,
              sminx + (smaxx - sminx) * 0.80]
        y_center = (sminy + smaxy) / 2.0
        pins = []
        for x in xs:
            pt = Point(x, y_center)
            if safe_zone.contains(pt):
                pins.append(pt)
            else:
                pin = _find_nearest_safe_point(safe_zone, x, y_center)
                if pin is not None:
                    pins.append(pin)
        return pins
    else:
        # Dikey yonelim - Y boyunca 2 pin
        ys = [sminy + (smaxy - sminy) * 0.20,
              sminy + (smaxy - sminy) * 0.80]
        x_center = (sminx + smaxx) / 2.0
        pins = []
        for y in ys:
            pt = Point(x_center, y)
            if safe_zone.contains(pt):
                pins.append(pt)
            else:
                pin = _find_nearest_safe_point(safe_zone, x_center, y)
                if pin is not None:
                    pins.append(pin)
        return pins


def _find_nearest_safe_point(safe_zone, target_x, target_y):
    """Hedef noktaya en yakin safe_zone icindeki noktayi bul."""
    from shapely.geometry import LineString
    target = Point(target_x, target_y)
    if safe_zone.contains(target):
        return target
    # Y'de yatay cizgi cek, kesisim al
    bounds = safe_zone.bounds
    line_h = LineString([(bounds[0] - 1, target_y), (bounds[2] + 1, target_y)])
    inter_h = safe_zone.intersection(line_h)
    if not inter_h.is_empty:
        if inter_h.geom_type == 'LineString':
            coords = list(inter_h.coords)
            # Hedefe en yakin uctaki noktayi al
            best = min(coords, key=lambda c: abs(c[0] - target_x))
            return Point(best[0], target_y)
        elif inter_h.geom_type == 'MultiLineString':
            best_pt = None
            best_dist = float('inf')
            for geom in inter_h.geoms:
                for c in geom.coords:
                    d = abs(c[0] - target_x)
                    if d < best_dist:
                        best_dist = d
                        best_pt = c
            if best_pt:
                return Point(best_pt[0], target_y)
    return None



# ============================================================
# SLICE PROCESSING (kerf + pinler)
# ============================================================

def process_slice(slice_obj: Slice, kerf_mm: float, pin_diameter: float,
                  min_dim_for_pin: float = 30.0,
                  min_dim_for_grid: float = 60.0,
                  global_pins: list = None) -> dict:
    """
    Bir dilim icin kerf uygular ve pin deliklerini hesaplar.

    Returns:
        {
            'polygons': [kerf uygulanmis polygons],
            'pins': [Point(x,y), ...],
            'pin_diameter': float,
            'index': int,
            'axis_position': float,
        }
    """
    processed_polys = []
    all_pins = []

    for poly in slice_obj.polygons:
        # Kerf uygula (disa)
        kp = apply_kerf(poly, kerf_mm, direction='outward')
        if kp.is_empty:
            continue
        processed_polys.append(kp)

        # Pin deliklerini hesapla
        if global_pins is not None:
            # Global sabit konumlar: polygon icinde olan pinleri al
            pins = [p for p in global_pins if kp.contains(p)]
        else:
            pins = generate_pin_holes(
                kp,
                pin_diameter=pin_diameter,
                min_dim_for_pin=min_dim_for_pin,
                min_dim_for_grid=min_dim_for_grid,
            )
        all_pins.extend(pins)

    return {
        'polygons': processed_polys,
        'pins': all_pins,
        'pin_diameter': pin_diameter,
        'index': slice_obj.index,
        'axis_position': slice_obj.axis_position,
    }

# ============================================================
# DXF EXPORT
# ============================================================

def export_slice_to_dxf(processed_slice: dict, output_path: str,
                        slice_total: int, model_name: str = "model",
                        edge_tick: bool = False):
    """
    Bir dilimi DXF dosyasina yazar.

    Args:
        processed_slice: process_slice cikti dict
        output_path: yazilacak DXF dosya yolu
        slice_total: toplam dilim sayisi (numara formatinda kullanilir, "17/44")
        model_name: model adi
        edge_tick: True ise plakanin ust kenarina ek mikro numara yaz
    """
    doc = ezdxf.new(dxfversion='R2010', setup=True)
    msp = doc.modelspace()

    # Layerlar
    if 'CUT' not in doc.layers:
        doc.layers.add('CUT', color=1)  # kirmizi - kesim
    if 'PIN' not in doc.layers:
        doc.layers.add('PIN', color=5)  # mavi - pin delikleri
    if 'ENGRAVE' not in doc.layers:
        doc.layers.add('ENGRAVE', color=3)  # yesil - gravur (ana numara)
    if 'TICK' not in doc.layers:
        doc.layers.add('TICK', color=4)  # cyan - kenar tick numarasi

    # Konturlari yaz
    for poly in processed_slice['polygons']:
        # Dis kontur
        exterior_coords = list(poly.exterior.coords)
        msp.add_lwpolyline(exterior_coords, close=True, dxfattribs={'layer': 'CUT'})

        # Ic delikler (polygon icindeki bosluklar)
        for interior in poly.interiors:
            interior_coords = list(interior.coords)
            msp.add_lwpolyline(interior_coords, close=True, dxfattribs={'layer': 'CUT'})

    # Pin delikleri (cember)
    pin_radius = processed_slice['pin_diameter'] / 2.0
    for pin in processed_slice['pins']:
        msp.add_circle(
            center=(pin.x, pin.y),
            radius=pin_radius,
            dxfattribs={'layer': 'PIN'}
        )

    # Numara metni
    if processed_slice['polygons']:
        # En buyuk polygon'u sec (cogu zaman ana parca)
        main_poly = max(processed_slice['polygons'], key=lambda p: p.area)
        text_str = f"{processed_slice['index']:02d}/{slice_total - 1:02d}"

        # ANA NUMARA - merkeze (yapistirma sonrasi gizli kalir)
        rep = main_poly.representative_point()
        msp.add_text(
            text_str,
            dxfattribs={
                'layer': 'ENGRAVE',
                'height': 4.0,
                'insert': (rep.x, rep.y),
            }
        )

        # KENAR TICK - opsiyonel
        if edge_tick:
            bounds = main_poly.bounds
            tick_x = bounds[0] + 3.0
            tick_y = bounds[3] - 3.5
            msp.add_text(
                f"{processed_slice['index']:02d}",
                dxfattribs={
                    'layer': 'TICK',
                    'height': 2.0,
                    'insert': (tick_x, tick_y),
                }
            )

    doc.saveas(output_path)


# ============================================================
# SVG EXPORT
# ============================================================

def export_slice_to_svg(processed_slice: dict, output_path: str,
                        slice_total: int, model_name: str = "model",
                        edge_tick: bool = False):
    """
    Bir dilimi SVG dosyasina yazar (lazer kesim yazilimlarinin cogu icin uygun).

    Renk kodu (cogu lazer yaziliminda layer ayrimi icin kullanilir):
      kirmizi -> kesim
      mavi    -> pin delikleri (cember)
      yesil   -> ana numara (gravur)
      cyan    -> kenar tick (gravur, opsiyonel)
    """
    if not processed_slice['polygons']:
        return

    # Tum geometrinin ortak bounding box'i
    all_bounds = [p.bounds for p in processed_slice['polygons']]
    minx = min(b[0] for b in all_bounds)
    miny = min(b[1] for b in all_bounds)
    maxx = max(b[2] for b in all_bounds)
    maxy = max(b[3] for b in all_bounds)

    # Pin delikleri de bounds'a katki yapsin
    if processed_slice['pins']:
        r = processed_slice['pin_diameter'] / 2.0
        for pin in processed_slice['pins']:
            minx = min(minx, pin.x - r)
            miny = min(miny, pin.y - r)
            maxx = max(maxx, pin.x + r)
            maxy = max(maxy, pin.y + r)

    # 5mm padding
    pad = 5.0
    minx -= pad
    miny -= pad
    maxx += pad
    maxy += pad
    width = maxx - minx
    height = maxy - miny

    dwg = svgwrite.Drawing(
        output_path,
        size=(f"{width}mm", f"{height}mm"),
        viewBox=f"0 0 {width} {height}",
        profile='tiny',
    )

    # SVG koordinati Y asagi gider; CAD/lazer Y yukari gider -> Y'yi flip et
    def to_svg(x, y):
        return (x - minx, maxy - y)

    # Konturlar (kesim - kirmizi)
    cut_group = dwg.g(stroke='red', fill='none', stroke_width=0.1)
    for poly in processed_slice['polygons']:
        exterior_pts = [to_svg(x, y) for x, y in poly.exterior.coords]
        cut_group.add(dwg.polygon(points=exterior_pts))
        for interior in poly.interiors:
            int_pts = [to_svg(x, y) for x, y in interior.coords]
            cut_group.add(dwg.polygon(points=int_pts))
    dwg.add(cut_group)

    # Pin delikleri (mavi cember)
    if processed_slice['pins']:
        pin_group = dwg.g(stroke='blue', fill='none', stroke_width=0.1)
        r = processed_slice['pin_diameter'] / 2.0
        for pin in processed_slice['pins']:
            cx, cy = to_svg(pin.x, pin.y)
            pin_group.add(dwg.circle(center=(cx, cy), r=r))
        dwg.add(pin_group)

    # Numara metni
    main_poly = max(processed_slice['polygons'], key=lambda p: p.area)
    text_str = f"{processed_slice['index']:02d}/{slice_total - 1:02d}"

    # ANA NUMARA - merkeze (yapistirma sonrasi gizli)
    rep = main_poly.representative_point()
    cx, cy = to_svg(rep.x, rep.y)
    dwg.add(dwg.text(
        text_str,
        insert=(cx, cy),
        fill='green',
        font_size=4,
        font_family='Arial',
        text_anchor='middle',
    ))

    # KENAR TICK - opsiyonel
    if edge_tick:
        bounds = main_poly.bounds
        tick_x = bounds[0] + 3.0
        tick_y = bounds[3] - 3.5
        tx, ty = to_svg(tick_x, tick_y)
        dwg.add(dwg.text(
            f"{processed_slice['index']:02d}",
            insert=(tx, ty),
            fill='cyan',
            font_size=2,
            font_family='Arial',
        ))

    dwg.save()

# ============================================================
# ASSEMBLY GUIDE
# ============================================================

def write_assembly_guide(result: SliceResult, processed_slices: list,
                         output_path: str, model_name: str,
                         kerf_mm: float, pin_diameter: float):
    """
    Human-readable assembly guide written into the ZIP output.
    """
    lines = []
    lines.append("=" * 70)
    lines.append(f"ASSEMBLY GUIDE: {model_name}")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Slice axis          : {AXIS_NAMES[result.slice_axis]}")
    lines.append(f"Plywood thickness   : {result.plywood_thickness} mm")
    lines.append(f"Kerf compensation   : {kerf_mm} mm (outward offset)")
    lines.append(f"Alignment pin diam. : {pin_diameter} mm")
    lines.append(f"Sculpture size      : "
                 f"{result.mesh_extents_mm[0]:.1f} x "
                 f"{result.mesh_extents_mm[1]:.1f} x "
                 f"{result.mesh_extents_mm[2]:.1f} mm")
    lines.append(f"Total plates        : {len([p for p in processed_slices if p['polygons']])}")
    lines.append("")
    lines.append("ASSEMBLY STEPS:")
    lines.append("-" * 70)
    lines.append("1. Confirm all plates are cut (plate 00 through the last number).")
    lines.append("2. Each plate has 2–4 blue circles — these are alignment pin holes.")
    lines.append(f"3. Prepare {pin_diameter} mm diameter wooden dowel pins.")
    lines.append("4. Insert the dowel pin(s) into plate 00.")
    lines.append("5. Stack plates in order onto the pin(s): 00, 01, 02, ...")
    lines.append("6. Apply PVA wood glue between each plate.")
    lines.append("7. Clamp the stack and allow to cure fully.")
    lines.append("8. Once dry, trim the dowel pins flush with the surface.")
    lines.append("")
    lines.append("FLOATING PARTS (ISLANDS):")
    lines.append("-" * 70)
    lines.append("Some plates may contain multiple separate pieces (e.g. ears, shoulders).")
    lines.append("Glue these smaller parts onto the main piece at the correct spacing.")
    lines.append("Use the 3D model or the stacked-outline preview as a reference.")
    lines.append("")
    lines.append("PLATE LIST:")
    lines.append("-" * 70)
    lines.append(f"{'No':<5} {'Parts':<14} {'Size W x H (mm)':<20} {'Pins':<12}")

    for ps in processed_slices:
        if not ps['polygons']:
            continue
        n_polys = len(ps['polygons'])
        all_b = [p.bounds for p in ps['polygons']]
        w = max(b[2] for b in all_b) - min(b[0] for b in all_b)
        h = max(b[3] for b in all_b) - min(b[1] for b in all_b)
        n_pins = len(ps['pins'])
        lines.append(f"{ps['index']:<5} {n_polys:<14} {w:>6.1f} x {h:<10.1f}  {n_pins:<12}")

    lines.append("")
    lines.append("=" * 70)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

# ============================================================
# ANA EXPORT FONKSIYONU
# ============================================================
def _compute_global_pins(slices, pin_diameter,
                          min_dim_for_pin=30.0,
                          min_dim_for_grid=60.0):
    """
    Tum dilimlerin global bounding box'indan sabit pin konumlari uretir.
    Her dilimde ayni XY koordinatlarinda pinler olur.
    """
    from shapely.geometry import Point

    # Tum dilimlerin global bbox'ini bul
    all_minx, all_miny, all_maxx, all_maxy = [], [], [], []
    for sl in slices:
        for poly in sl.polygons:
            b = poly.bounds
            all_minx.append(b[0])
            all_miny.append(b[1])
            all_maxx.append(b[2])
            all_maxy.append(b[3])

    if not all_minx:
        return []

    gminx = min(all_minx)
    gminy = min(all_miny)
    gmaxx = max(all_maxx)
    gmaxy = max(all_maxy)

    width  = gmaxx - gminx
    height = gmaxy - gminy
    margin = 8.0

    # Pin sayisi: global boyuta gore
    min_dim = min(width, height)
    if min_dim < min_dim_for_pin:
        return []

    # Global grid pin konumlari
    if width >= min_dim_for_grid and height >= min_dim_for_grid:
        # 2x2 grid
        xs = [gminx + width * 0.20, gminx + width * 0.80]
        ys = [gminy + height * 0.20, gminy + height * 0.80]
        pins = [Point(x, y) for x in xs for y in ys]
    elif width >= height:
        # Yatay 2 pin
        xs = [gminx + width * 0.20, gminx + width * 0.80]
        y  = gminy + height * 0.50
        pins = [Point(x, y) for x in xs]
    else:
        # Dikey 2 pin
        x  = gminx + width * 0.50
        ys = [gminy + height * 0.20, gminy + height * 0.80]
        pins = [Point(x, y) for y in ys]

    return pins

def export_all(result: SliceResult, output_dir: str,
               model_name: str = "model",
               kerf_mm: float = 0.08,
               pin_diameter: float = 3.0,
               formats: list = None,
               min_dim_for_pin: float = 30.0,
               min_dim_for_grid: float = 60.0,
               edge_tick: bool = False):
    """
    Tum dilimleri DXF ve/veya SVG olarak yazar, montaj rehberi olusturur.

    Args:
        result: SliceResult
        output_dir: cikti klasoru (orn 'output')
        model_name: dosya isimleri prefix
        kerf_mm: kerf telafisi mm (lazer ne kadar yakar)
        pin_diameter: hizalama delik capi mm
        formats: ['dxf'], ['svg'], veya ['dxf', 'svg']
        min_dim_for_pin: bu boyuttan kucuk parcaya pin koyma
        min_dim_for_grid: her iki boyut da bundan buyukse 2x2 grid pin
        edge_tick: True ise her plakaya kenar tick numarasi ekle (montajda)
    """
    if formats is None:
        formats = ['dxf', 'svg']

    os.makedirs(output_dir, exist_ok=True)

    # Format alt klasorleri
    dxf_dir = os.path.join(output_dir, 'dxf')
    svg_dir = os.path.join(output_dir, 'svg')
    if 'dxf' in formats:
        os.makedirs(dxf_dir, exist_ok=True)
    if 'svg' in formats:
        os.makedirs(svg_dir, exist_ok=True)

    # Tum dilimleri isle (kerf + pin hesabi)
    print(f"\nIsleniyor: kerf={kerf_mm}mm, pin capi={pin_diameter}mm, "
          f"edge tick={'ACIK' if edge_tick else 'KAPALI'}")
    processed_slices = []
    # Global pin konumlarini hesapla (tum dilimler icin sabit)
    global_pins = _compute_global_pins(
        result.slices, pin_diameter,
        min_dim_for_pin=min_dim_for_pin,
        min_dim_for_grid=min_dim_for_grid,
    )

    for sl in result.slices:
        ps = process_slice(
            sl, kerf_mm, pin_diameter,
            min_dim_for_pin=min_dim_for_pin,
            min_dim_for_grid=min_dim_for_grid,
            global_pins=global_pins,
        )
        processed_slices.append(ps)

    # Bos olmayan dilim sayisi
    total = sum(1 for p in processed_slices if p['polygons'])

    # Yaz
    written_dxf = 0
    written_svg = 0
    for ps in processed_slices:
        if not ps['polygons']:
            continue

        idx = ps['index']
        filename_base = f"{model_name}_slice_{idx:02d}"

        if 'dxf' in formats:
            dxf_path = os.path.join(dxf_dir, filename_base + '.dxf')
            export_slice_to_dxf(
                ps, dxf_path,
                slice_total=total,
                model_name=model_name,
                edge_tick=edge_tick,
            )
            written_dxf += 1

        if 'svg' in formats:
            svg_path = os.path.join(svg_dir, filename_base + '.svg')
            export_slice_to_svg(
                ps, svg_path,
                slice_total=total,
                model_name=model_name,
                edge_tick=edge_tick,
            )
            written_svg += 1

    # Montaj rehberi
    guide_path = os.path.join(output_dir, 'assembly_guide.txt')
    write_assembly_guide(
        result, processed_slices, guide_path,
        model_name=model_name, kerf_mm=kerf_mm, pin_diameter=pin_diameter,
    )

    print(f"  DXF yazildi : {written_dxf} dosya -> {dxf_dir}")
    print(f"  SVG yazildi : {written_svg} dosya -> {svg_dir}")
    print(f"  Montaj rehberi -> {guide_path}")

    return processed_slices