# Wood Sculpture Slicer

Convert 3D models (OBJ/STL) into laser-cut plywood slices — ready for assembly into physical wood sculptures.

## Features

- OBJ / STL model loading
- Three slice axes (X / Y / Z)
- Automatic scaling to target size
- Kerf compensation (laser burn offset)
- Smart alignment pin placement (2-pin row or 2×2 grid)
- DXF + SVG output (color-coded layers)
- Assembly guide (TXT) included in ZIP
- Web UI with 3D preview (Three.js)
- CLI for batch/scripted use

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Web UI

```bash
python3 run_server.py
# open http://localhost:5001
```

## CLI Usage

```bash
python3 main.py models/Hermes.stl --export
```

### Parameters

| Flag | Default | Description |
|---|---|---|
| `--axis X\|Y\|Z` | `X` | Slice axis |
| `--size 250` | `250` | Target sculpture size (mm) |
| `--size-axis Z` | `Z` | Which axis the target size applies to |
| `--thickness 3.0` | `3.0` | Plywood thickness (mm) |
| `--kerf 0.08` | `0.08` | Laser kerf compensation (mm) |
| `--pin-diameter 3.0` | `3.0` | Alignment dowel pin diameter (mm) |
| `--edge-tick` | off | Add micro index number to plate edge |
| `--format dxf\|svg\|both` | `both` | Output format |
| `--no-preview` | off | Skip preview PNG generation |

## Output structure

```
output/
├── dxf/          # laser-cut DXF files (one per plate)
├── svg/          # laser-cut SVG files (one per plate)
├── assembly_guide.txt
├── slices_grid_X.png
└── slices_overlay_X.png
```

## Layer color convention (DXF / SVG)

| Color | Layer | Purpose |
|---|---|---|
| Red | CUT | Cutting path |
| Blue | PIN | Alignment pin holes |
| Green | ENGRAVE | Plate index number (engraved, not cut) |
| Cyan | TICK | Edge tick number (optional) |

## License

Personal project by Volkan Duran.