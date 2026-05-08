/* =====================================================================
   Wood Sculpture Slicer - Frontend
   Modules: Upload + 3D viewer + Process + Download
   ===================================================================== */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';

// =====================================================================
// State
// =====================================================================
const state = {
  sessionId: null,
  meshInfo: null,
  filename: null,
  fileBlob: null,        // 3D viewer icin (yeniden gondermiyoruz, lokalde tutuyoruz)
  processing: false,
};

// =====================================================================
// DOM helpers
// =====================================================================
const $ = (id) => document.getElementById(id);

const dom = {
  dropzone:    $('dropzone'),
  fileInput:   $('file-input'),
  fileInfo:    $('file-info'),
  fileName:    $('file-name'),
  fileRemove:  $('file-remove'),
  kvVertex:    $('kv-vertex'),
  kvFace:      $('kv-face'),
  kvX:         $('kv-x'),
  kvY:         $('kv-y'),
  kvZ:         $('kv-z'),
  kvWt:        $('kv-wt'),
  btnProcess:  $('btn-process'),
  viewer3d:    $('viewer-3d'),
};

// =====================================================================
// Utilities
// =====================================================================
function fmt(n, dec = 2) {
  return Number(n).toFixed(dec);
}

function fmtInt(n) {
  return Number(n).toLocaleString('tr-TR');
}

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

// =====================================================================
// Upload
// =====================================================================
function setupDropzone() {
  // Tikla -> file picker
  dom.dropzone.addEventListener('click', () => {
    if (state.processing) return;
    dom.fileInput.click();
  });

  dom.fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) handleFile(file);
  });

  // Drag-drop
  ['dragenter', 'dragover'].forEach(evt => {
    dom.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dom.dropzone.classList.add('dragging');
    });
  });

  ['dragleave', 'drop'].forEach(evt => {
    dom.dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dom.dropzone.classList.remove('dragging');
    });
  });

  dom.dropzone.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  // Kaldir butonu
  dom.fileRemove.addEventListener('click', (e) => {
    e.stopPropagation();
    resetFile();
  });
}

async function handleFile(file) {
  // Extension check (early UI-side error)
  const ext = file.name.toLowerCase().match(/\.(stl|obj)$/);
  if (!ext) {
    showFileError('Only .stl or .obj files are accepted');
    return;
  }

  // Size check (50 MB)
  if (file.size > 50 * 1024 * 1024) {
    showFileError('File size cannot exceed 50 MB');
    return;
  }

  state.fileBlob = file;
  state.filename = file.name;

  // 3D viewer'a hemen yukle (paralel olarak backend'e de)
  load3DModel(file);

  // Backend'e yukle
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();

    if (!res.ok) {
      showFileError(data.error || 'Upload failed');
      return;
    }

    state.sessionId = data.session_id;
    state.meshInfo = data.mesh_info;
    showFileInfo(data);
    dom.btnProcess.disabled = false;
  } catch (err) {
    showFileError('Could not connect to server: ' + err.message);
  }
}

function showFileInfo(data) {
  dom.fileName.textContent = data.filename;
  const m = data.mesh_info;
  dom.kvVertex.textContent = fmtInt(m.vertex_count);
  dom.kvFace.textContent = fmtInt(m.face_count);
  dom.kvX.textContent = fmt(m.extents[0]);
  dom.kvY.textContent = fmt(m.extents[1]);
  dom.kvZ.textContent = fmt(m.extents[2]);
  dom.kvWt.textContent = m.is_watertight ? 'yes' : 'no';
  show(dom.fileInfo);
  hide(dom.dropzone);
}

function showFileError(msg) {
  alert(msg);  // basit; istenirse error-box kullanilabilir
}

function resetFile() {
  state.sessionId = null;
  state.meshInfo = null;
  state.fileBlob = null;
  state.filename = null;
  dom.fileInput.value = '';
  hide(dom.fileInfo);
  show(dom.dropzone);
  dom.btnProcess.disabled = true;
  clear3DViewer();
}

// =====================================================================
// 3D Viewer
// =====================================================================
let three = null;  // {scene, camera, renderer, controls, mesh, animFrame}

function init3DViewer() {
  const container = dom.viewer3d;
  const w = container.clientWidth;
  const h = container.clientHeight;

  const scene = new THREE.Scene();
  scene.background = null;

  const camera = new THREE.PerspectiveCamera(45, w / h, 0.01, 5000);
  camera.position.set(2, 2, 3);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(w, h);
  // Empty placeholder'i temizle, canvas ekle
  container.innerHTML = '';
  container.appendChild(renderer.domElement);

  // Lights
  const amb = new THREE.AmbientLight(0xffffff, 0.55);
  scene.add(amb);
  const dir1 = new THREE.DirectionalLight(0xffffff, 0.8);
  dir1.position.set(5, 5, 5);
  scene.add(dir1);
  const dir2 = new THREE.DirectionalLight(0xfbbf24, 0.3);  // amber rim light
  dir2.position.set(-5, -2, -3);
  scene.add(dir2);

  // Controls
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.rotateSpeed = 0.8;
  controls.minDistance = 0.5;
  controls.maxDistance = 100;

  // Auto rotate (kullanici dokununca duracak)
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.8;

  controls.addEventListener('start', () => {
    controls.autoRotate = false;
  });

  three = { scene, camera, renderer, controls, mesh: null, animFrame: null };

  // Resize listener
  window.addEventListener('resize', onViewerResize);

  // Animation loop
  animate();
}

function animate() {
  if (!three) return;
  three.animFrame = requestAnimationFrame(animate);
  three.controls.update();
  three.renderer.render(three.scene, three.camera);
}

function onViewerResize() {
  if (!three) return;
  const w = dom.viewer3d.clientWidth;
  const h = dom.viewer3d.clientHeight;
  three.camera.aspect = w / h;
  three.camera.updateProjectionMatrix();
  three.renderer.setSize(w, h);
}

function load3DModel(file) {
  if (!three) init3DViewer();

  const reader = new FileReader();
  reader.onload = (e) => {
    const buffer = e.target.result;
    const ext = file.name.toLowerCase().match(/\.(\w+)$/)[1];

    let geometry;
    try {
      if (ext === 'stl') {
        const loader = new STLLoader();
        geometry = loader.parse(buffer);
      } else if (ext === 'obj') {
        const loader = new OBJLoader();
        const text = new TextDecoder().decode(buffer);
        const obj = loader.parse(text);
        // OBJ'den ilk mesh'i al
        let firstMesh = null;
        obj.traverse(child => {
          if (!firstMesh && child.isMesh) firstMesh = child;
        });
        geometry = firstMesh ? firstMesh.geometry : null;
      }
    } catch (err) {
      console.error('3D yukleme hatasi:', err);
      return;
    }

    if (!geometry) return;

    // Mevcut mesh'i kaldir
    if (three.mesh) {
      three.scene.remove(three.mesh);
      three.mesh.geometry.dispose();
      three.mesh.material.dispose();
      three.mesh = null;
    }

    // Normalleri hesapla (gorsel kalite icin)
    geometry.computeVertexNormals();

    // Material: ahsap rengi
    const material = new THREE.MeshStandardMaterial({
      color: 0xd4a574,
      roughness: 0.7,
      metalness: 0.05,
      flatShading: false,
    });

    const mesh = new THREE.Mesh(geometry, material);

    // Modeli ortala ve olcekle (sahnede oturuk olacak sekilde)
    geometry.computeBoundingBox();
    const box = geometry.boundingBox;
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z);
    const scale = 2.0 / maxDim;
    mesh.scale.setScalar(scale);

    const center = new THREE.Vector3();
    box.getCenter(center);
    mesh.position.copy(center).multiplyScalar(-scale);

    three.scene.add(mesh);
    three.mesh = mesh;

    // Camera'yi modele uyumlandir
    three.camera.position.set(3, 2, 3);
    three.controls.target.set(0, 0, 0);
    three.controls.autoRotate = true;
    three.controls.update();
  };

  reader.readAsArrayBuffer(file);
}

function clear3DViewer() {
  if (!three) return;
  if (three.mesh) {
    three.scene.remove(three.mesh);
    three.mesh.geometry.dispose();
    three.mesh.material.dispose();
    three.mesh = null;
  }
  // Empty placeholder'i geri koy
  if (three.animFrame) cancelAnimationFrame(three.animFrame);
  three.renderer.dispose();
  dom.viewer3d.innerHTML = '<div class="viewer-empty">Model yükleyince burada görünecek</div>';
  three = null;
}

// =====================================================================
// Init
// =====================================================================
document.addEventListener('DOMContentLoaded', () => {
  setupDropzone();
});

// =====================================================================
// Process (Üret butonu)
// =====================================================================
const dom2 = {
  btnProcess:    $('btn-process'),
  btnLabel:      document.querySelector('#btn-process .btn-label'),
  btnSpinner:    document.querySelector('#btn-process .btn-spinner'),
  processError:  $('process-error'),
  resultEmpty:   $('result-empty'),
  resultContent: $('result-content'),
  reportGrid:    $('report-grid'),
  imgGrid:       $('img-grid'),
  imgOverlay:    $('img-overlay'),
  plateTbody:    $('plate-tbody'),
  plateCount:    $('plate-count'),
  btnDownload:   $('btn-download'),
};


function getFormParams() {
  // Eksen
  const axisRadio = document.querySelector('input[name="axis"]:checked');
  const axis = axisRadio ? axisRadio.value : 'X';

  // Format
  const formats = [];
  if ($('fmt-dxf').checked) formats.push('dxf');
  if ($('fmt-svg').checked) formats.push('svg');

  return {
    session_id: state.sessionId,
    axis: axis,
    size_axis: $('size-axis').value,
    size_mm: parseFloat($('size').value),
    thickness_mm: parseFloat($('thickness').value),
    kerf_mm: parseFloat($('kerf').value),
    pin_diameter_mm: parseFloat($('pin-diameter').value),
    edge_tick: $('edge-tick').checked,
    formats: formats,
  };
}


async function runProcess() {
  if (!state.sessionId) {
    showProcessError('Please upload a model first');
    return;
  }

  const params = getFormParams();

  if (params.formats.length === 0) {
    showProcessError('Select at least one output format (DXF or SVG)');
    return;
  }

  // UI: spinner ac, butonu kilitle
  state.processing = true;
  hideProcessError();
  setButtonLoading(true);

  try {
    const res = await fetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    const data = await res.json();

    if (!res.ok || !data.success) {
      showProcessError(data.error || 'Processing failed');
      return;
    }

    showResults(data);
  } catch (err) {
    showProcessError('Server error: ' + err.message);
  } finally {
    state.processing = false;
    setButtonLoading(false);
  }
}


function setButtonLoading(loading) {
  if (loading) {
    dom2.btnProcess.disabled = true;
    dom2.btnLabel.textContent = 'Processing...';
    show(dom2.btnSpinner);
  } else {
    dom2.btnProcess.disabled = !state.sessionId;
    dom2.btnLabel.textContent = 'Generate';
    hide(dom2.btnSpinner);
  }
}


function showProcessError(msg) {
  dom2.processError.textContent = msg;
  show(dom2.processError);
}

function hideProcessError() {
  hide(dom2.processError);
  dom2.processError.textContent = '';
}


function showResults(data) {
  // Result empty -> result content
  hide(dom2.resultEmpty);
  show(dom2.resultContent);

  // 1. Rapor grid (ozet istatistikler)
  const r = data.slice_report;
  const ext = r.mesh_extents_mm;
  dom2.reportGrid.innerHTML = `
    <div class="stat">
      <span class="stat-label">Plates</span>
      <span class="stat-value">${r.non_empty_count}</span>
    </div>
    <div class="stat">
      <span class="stat-label">Axis</span>
      <span class="stat-value">${r.slice_axis}</span>
    </div>
    <div class="stat">
      <span class="stat-label">Thickness</span>
      <span class="stat-value">${r.plywood_thickness} mm</span>
    </div>
    <div class="stat">
      <span class="stat-label">Size (mm)</span>
      <span class="stat-value">${fmt(ext[0], 0)}×${fmt(ext[1], 0)}×${fmt(ext[2], 0)}</span>
    </div>
  `;

  // 2. Preview gorseller (cache busting icin timestamp ekle)
  const ts = Date.now();
  if (data.preview_urls.grid) {
    dom2.imgGrid.src = data.preview_urls.grid + '?t=' + ts;
  }
  if (data.preview_urls.overlay) {
    dom2.imgOverlay.src = data.preview_urls.overlay + '?t=' + ts;
  }

  // 3. Plaka tablosu
  dom2.plateTbody.innerHTML = '';
  for (const plate of data.plate_summary) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${plate.index.toString().padStart(2, '0')}</td>
      <td>${plate.parts}</td>
      <td>${plate.width_mm} × ${plate.height_mm}</td>
      <td>${plate.pins}</td>
    `;
    dom2.plateTbody.appendChild(tr);
  }
  dom2.plateCount.textContent = `${data.plate_summary.length} plates`;

  // 4. Download linki
  dom2.btnDownload.href = data.download_url;

  // 5. Sonuc bolumune scroll
  dom2.resultContent.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Üret butonu event listener
dom2.btnProcess.addEventListener('click', runProcess);

// =====================================================================
// Nesting UI
// =====================================================================

const domN = {
  btnNest:        $('btn-nest'),
  btnNestLabel:   document.querySelector('#btn-nest .btn-nest-label'),
  btnNestSpinner: document.querySelector('#btn-nest .btn-nest-spinner'),
  nestError:      $('nest-error'),
  nestResult:     $('nest-result'),
  nestReportGrid: $('nest-report-grid'),
  btnNestDl:      $('btn-nest-download'),
  preserveGrain:  $('preserve-grain'),
  nestingGap:     $('nesting-gap'),
  sheetW:         $('sheet-w'),
  sheetH:         $('sheet-h'),
  customRow:      $('custom-sheet-row'),
};


// Sheet size radio → custom row goster/gizle
document.querySelectorAll('input[name="sheet-size"]').forEach(radio => {
  radio.addEventListener('change', () => {
    const isCustom = radio.value === 'custom' && radio.checked;
    domN.customRow.style.display = isCustom ? 'grid' : 'none';
  });
});


function getSheetSize() {
  const selected = document.querySelector('input[name="sheet-size"]:checked');
  const val = selected ? selected.value : 'A3';
  const sizes = {
    'A4': [210, 297],
    'A3': [297, 420],
    'custom': [
      parseFloat(domN.sheetW.value) || 297,
      parseFloat(domN.sheetH.value) || 420,
    ],
  };
  return sizes[val] || [297, 420];
}


function getNestingParams() {
  const [sw, sh] = getSheetSize();
  return {
    session_id: state.sessionId,
    // Mevcut slice parametrelerini de gonder (pipeline tekrar calisacak)
    ...getFormParams(),
    // Nesting
    run_nesting: true,
    nesting_sheet_width: sw,
    nesting_sheet_height: sh,
    nesting_gap: parseFloat(domN.nestingGap.value) || 2.0,
    nesting_rotation: !domN.preserveGrain.checked,
    nesting_preserve_grain: domN.preserveGrain.checked,
  };
}


function setNestButtonLoading(loading) {
  if (loading) {
    domN.btnNest.disabled = true;
    domN.btnNestLabel.textContent = 'Processing...';
    show(domN.btnNestSpinner);
  } else {
    domN.btnNest.disabled = !state.sessionId;
    domN.btnNestLabel.textContent = 'Nest & Export';
    hide(domN.btnNestSpinner);
  }
}


function showNestError(msg) {
  domN.nestError.textContent = msg;
  show(domN.nestError);
}

function hideNestError() {
  hide(domN.nestError);
  domN.nestError.textContent = '';
}


function showNestResult(nesting, session_id) {
  if (!nesting) return;

  // Rapor grid
  domN.nestReportGrid.innerHTML = `
    <div class="stat">
      <span class="stat-label">Sheets</span>
      <span class="stat-value">${nesting.sheet_count}</span>
    </div>
    <div class="stat">
      <span class="stat-label">Placed</span>
      <span class="stat-value">${nesting.placed_items}/${nesting.total_items}</span>
    </div>
    <div class="stat">
      <span class="stat-label">Unplaced</span>
      <span class="stat-value" style="color:${nesting.unplaced_items > 0 ? '#ef4444' : '#10b981'}">
        ${nesting.unplaced_items}
      </span>
    </div>
    <div class="stat">
      <span class="stat-label">Avg use</span>
      <span class="stat-value">${nesting.avg_utilization}%</span>
    </div>
  `;

  // Download linki — nesting ZIP icin ayri endpoint yok, ana download URL'i kullan
  // (pipeline nesting dosyalarini da output'a yaziyor, ZIP'e giriyor)
  domN.btnNestDl.href = `/api/download/${session_id}`;
  domN.btnNestDl.download = `nested_sheets_${session_id.slice(0, 8)}.zip`;

  show(domN.nestResult);
  domN.nestResult.scrollIntoView({ behavior: 'smooth', block: 'start' });
}


async function runNesting() {
  if (!state.sessionId) {
    showNestError('Please upload and process a model first');
    return;
  }

  hideNestError();
  hide(domN.nestResult);
  setNestButtonLoading(true);

  try {
    const params = getNestingParams();
    const res = await fetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    const data = await res.json();

    if (!res.ok || !data.success) {
      showNestError(data.error || 'Nesting failed');
      return;
    }

    // Slice sonuclarini da guncelle
    showResults(data);

    // Nesting sonucunu goster
    if (data.nesting) {
      showNestResult(data.nesting, data.session_id);
    } else {
      showNestError('Nesting result not returned from server');
    }

  } catch (err) {
    showNestError('Server error: ' + err.message);
  } finally {
    setNestButtonLoading(false);
  }
}


// Nest butonu event listener
domN.btnNest.addEventListener('click', runNesting);


// Generate tamamlaninca Nest butonunu aktif et
const _origShowResults = showResults;
// showResults zaten tanimli, nest butonunu aktif etmek icin wrap et
const _showResultsOrig = showResults;
window._nestActivate = function() {
  if (state.sessionId) {
    domN.btnNest.disabled = false;
  }
};

// Generate butonunun click handler'ini guncelle
dom2.btnProcess.removeEventListener('click', runProcess);
dom2.btnProcess.addEventListener('click', async () => {
  await runProcess();
  window._nestActivate();
});
