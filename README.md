# Wood Sculpture Slicer

OBJ/STL 3D modellerini lazer kesim için 2D plywood plakalarına dilimleyen Python aracı.

## Özellikler

- OBJ/STL model yükleme
- 3 eksen seçimi (X/Y/Z)
- Otomatik boyutlandırma
- Kerf compensation (lazer kesim telafisi)
- Akıllı pin/dowel deliği yerleşimi (2x2 grid veya tek hat)
- DXF + SVG çıktı (renk kodlu layer)
- Montaj rehberi (TXT)

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Kullanım

```bash
python3 main.py models/Hermes.stl --export
```

### Parametreler

- `--axis X|Y|Z` — Dilimleme ekseni (default: X)
- `--size 250` — Hedef heykel boyutu mm (default: 250)
- `--thickness 3.0` — Plywood kalınlığı mm
- `--kerf 0.08` — Lazer kerf telafisi mm
- `--pin-diameter 3.0` — Hizalama pin çapı mm
- `--edge-tick` — Plaka kenarına mikro numara ekle
- `--format dxf|svg|both` — Çıktı formatı

## Lisans

Şahsi proje.
