/**
 * MUSA — Tier II interactive item viewer (Silver).
 *
 * Loads the item's `model_primary` (GLB delivery format per the contract) into
 * a WebGL stage with museum-style lighting: key/fill/rim spots on a dark
 * pedestal. The viewer is chosen by the record's `model_viewer` field
 * (`three_js` here; `kit_stream` renders a streaming placeholder in main.js).
 */
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

let renderer, scene, camera, controls, raf = null, resizeObs = null, current = null;

function frameObject(obj, camera, controls, padding = 2.3) {
  const box = new THREE.Box3().setFromObject(obj);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z) || 1;
  const fov = camera.fov * (Math.PI / 180);
  const dist = (maxDim / (2 * Math.tan(fov / 2))) * padding;
  camera.position.set(center.x + dist * 0.85, center.y + dist * 0.45, center.z + dist * 0.85);
  camera.near = maxDim / 100;
  camera.far = maxDim * 40;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

function initStage(mount, loadingEl) {
  const w = mount.clientWidth || 600, h = mount.clientHeight || 500;
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); // perf cap
  renderer.setSize(w, h);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  mount.appendChild(renderer.domElement);

  scene = new THREE.Scene();
  // Subtle environment for PBR reflections without an HDR download.
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  camera = new THREE.PerspectiveCamera(38, w / h, 0.01, 100);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.9;
  controls.minDistance = 0.4;
  controls.maxDistance = 12;

  // Museum lighting rig
  scene.add(new THREE.AmbientLight(0xfff2df, 0.35));
  const key = new THREE.SpotLight(0xffe9c4, 120, 0, Math.PI / 5, 0.45, 1.6);
  key.position.set(3, 5, 2.5);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024); // keep the shadow map small
  scene.add(key);
  const fill = new THREE.SpotLight(0xcfd8e8, 40, 0, Math.PI / 4, 0.6, 1.8);
  fill.position.set(-4, 3, -1);
  scene.add(fill);
  const rim = new THREE.DirectionalLight(0xd8b878, 1.1);
  rim.position.set(0, 2.5, -4);
  scene.add(rim);

  // Pedestal
  const pedestal = new THREE.Mesh(
    new THREE.CylinderGeometry(0.62, 0.68, 0.08, 64),
    new THREE.MeshStandardMaterial({ color: 0x1c1a16, roughness: 0.35, metalness: 0.25 })
  );
  pedestal.position.y = -0.541;
  pedestal.receiveShadow = true;
  scene.add(pedestal);

  resizeObs = new ResizeObserver(() => {
    if (!mount.clientWidth) return;
    camera.aspect = mount.clientWidth / mount.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(mount.clientWidth, mount.clientHeight);
  });
  resizeObs.observe(mount);
}

function animate() {
  raf = requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

window.MusaItemViewer = {
  /** Load a record card's GLB into the modal stage. */
  load(item, mount, loadingEl, fallbackEl) {
    this.dispose();
    try {
      initStage(mount, loadingEl);
    } catch (err) {
      loadingEl.style.display = "none";
      fallbackEl.style.display = "grid";
      fallbackEl.innerHTML = "WebGL is unavailable in this browser.<br/>" + err.message;
      return;
    }

    loadingEl.style.display = "grid";
    loadingEl.textContent = "Loading “" + item.titulo + "”…";

    // Never leave the stage stuck on "Preparing the piece": if the loader
    // neither resolves nor fails (a stalled fetch), surface a fallback.
    let settled = false;
    const guard = setTimeout(() => {
      if (settled) return;
      settled = true;
      loadingEl.style.display = "none";
      fallbackEl.style.display = "grid";
      fallbackEl.innerHTML =
        "The 3D asset is taking too long to load.<br/>" +
        "The record card still carries the full provenance of this piece.";
    }, 30000);

    new GLTFLoader().load(
      item.model_primary,
      (gltf) => {
        settled = true; clearTimeout(guard);
        const model = gltf.scene;
        model.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
        scene.add(model);
        frameObject(model, camera, controls);
        loadingEl.style.display = "none";
        animate();
      },
      (ev) => {
        if (ev.total) loadingEl.textContent = `Loading “${item.titulo}”… ${Math.round(ev.loaded / ev.total * 100)}%`;
      },
      (err) => {
        settled = true; clearTimeout(guard);
        console.error("GLB load failed", err);
        loadingEl.style.display = "none";
        fallbackEl.style.display = "grid";
        fallbackEl.innerHTML =
          "The 3D asset could not be fetched (" + (item.model_primary || "no model") + ").<br/>" +
          "In production it is served from the asset CDN; the record card remains available.";
      }
    );
  },

  /** Stop rendering and release the stage (called when the modal closes). */
  dispose() {
    if (raf) cancelAnimationFrame(raf);
    raf = null;
    if (resizeObs) { resizeObs.disconnect(); resizeObs = null; }
    if (renderer) {
      renderer.dispose();
      renderer.domElement?.remove();
      renderer = null; scene = null; camera = null; controls = null;
    }
  }
};
