def run_pipeline(model_path, axis='X', size_axis='Z', size=250.0,
                thickness=3.0, kerf=0.08, pin_diameter=3.0,
                pin_min_size=30.0, pin_grid_size=60.0,
                edge_tick=False, formats=['dxf', 'svg'],
                output_dir='output', generate_preview=True,
                export=True) -> dict:
    """
    Tum boru hatti: model yukle -> analiz -> dilim -> onizle -> export.
    Sonuc bir dict olarak doner (rapor + dosya yollari).
    """
