/**
 * MUSA — Tier III digital twin (Gold).
 *
 * A performant WebGL twin of "Room A — Northern Masters": procedural parquet
 * floor, plaster walls, framed collection works as textures, simple pedestal
 * sculptures, museum track lighting. Built from primitives only (~40 draw
 * calls, capped pixel ratio, 1024 shadow map) so it runs smoothly on modest
 * hardware — the production twin streams from the USD pipeline instead
 * (`model_viewer: kit_stream`).
 *
 * Clicking a work or sculpture opens its record in the HUD via the
 * `musa:twin-select` event consumed by main.js.
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const shell = document.getElementById("twinShell");
const info = document.getElementById("twinInfo");

const ROOM = { w: 16, d: 10, h: 4.2 };

/* ---------------------------------------------------- procedural floor -- */
function parquetTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 512;
  const g = c.getContext("2d");
  g.fillStyle = "#4a3826";
  g.fillRect(0, 0, 512, 512);
  const plank = 64;
  for (let y = 0; y < 512; y += plank) {
    const offset = (y / plank) % 2 ? plank : 0;
    for (let x = -plank; x < 512 + plank; x += plank * 2) {
      const tone = 58 + Math.random() * 22;
      g.fillStyle = `rgb(${tone + 14}, ${tone - 4}, ${tone - 22})`;
      g.fillRect(x + offset + 1, y + 1, plank * 2 - 2, plank - 2);
      g.strokeStyle = "rgba(0,0,0,0.25)";
      g.strokeRect(x + offset + 0.5, y + 0.5, plank * 2 - 1, plank - 1);
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(4, 2.5);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function plasterTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const g = c.getContext("2d");
  g.fillStyle = "#cfc6b4";
  g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 4000; i++) {
    g.fillStyle = `rgba(${120 + Math.random() * 60}, ${112 + Math.random() * 55}, ${96 + Math.random() * 45}, 0.05)`;
    g.fillRect(Math.random() * 256, Math.random() * 256, 2, 2);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/* ------------------------------------------------------------- builders -- */
function buildFrame(w, h, { gold = 0x8a6a34, depth = 0.07, bar = 0.075 } = {}) {
  const group = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({ color: gold, roughness: 0.32, metalness: 0.7 });
  const mk = (bw, bh, x, y) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(bw, bh, depth), mat);
    m.position.set(x, y, 0);
    group.add(m);
  };
  mk(w + bar * 2, bar, 0, h / 2 + bar / 2);
  mk(w + bar * 2, bar, 0, -h / 2 - bar / 2);
  mk(bar, h, -w / 2 - bar / 2, 0);
  mk(bar, h, w / 2 + bar / 2, 0);
  return group;
}

function buildPainting(loader, { file, w, h, meta }) {
  const group = new THREE.Group();
  const tex = loader.load("assets/img/" + file);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  const canvasMesh = new THREE.Mesh(
    new THREE.PlaneGeometry(w, h),
    new THREE.MeshStandardMaterial({ map: tex, roughness: 0.85 })
  );
  group.add(canvasMesh);
  group.add(buildFrame(w, h));
  group.userData.hotspot = meta;
  canvasMesh.userData.hotspot = meta;
  return group;
}

function buildStatue(kind, matStone) {
  // Abstract classical silhouettes from lathe geometry — cheap, elegant.
  const profile = [];
  const shapes = {
    figure: [[0.00, 0.0], [0.30, 0.02], [0.26, 0.10], [0.16, 0.32], [0.14, 0.55], [0.20, 0.78], [0.22, 0.92], [0.16, 1.06], [0.10, 1.12], [0.13, 1.22], [0.11, 1.32], [0.02, 1.38]],
    amphora: [[0.00, 0.0], [0.16, 0.02], [0.12, 0.10], [0.24, 0.30], [0.28, 0.52], [0.20, 0.74], [0.10, 0.86], [0.10, 0.96], [0.14, 1.00], [0.12, 1.05], [0.02, 1.06]]
  };
  (shapes[kind] || shapes.figure).forEach(([x, y]) => profile.push(new THREE.Vector2(x, y)));
  const m = new THREE.Mesh(new THREE.LatheGeometry(profile, 40), matStone);
  m.castShadow = m.receiveShadow = true;
  return m;
}

/* ---------------------------------------------------------------- init --- */
function init() {
  if (!shell) return;
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(shell.clientWidth, shell.clientHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  shell.prepend(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0a08);
  scene.fog = new THREE.Fog(0x0b0a08, 14, 30);

  const camera = new THREE.PerspectiveCamera(52, shell.clientWidth / shell.clientHeight, 0.1, 60);
  camera.position.set(0, 1.9, 4.4);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 1.5, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.minDistance = 2.2;
  controls.maxDistance = 8;
  controls.maxPolarAngle = Math.PI * 0.52;
  controls.minPolarAngle = Math.PI * 0.18;
  controls.enablePan = false;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.35;
  controls.addEventListener("start", () => { controls.autoRotate = false; clearTimeout(controls._t); });
  controls.addEventListener("end", () => { controls._t = setTimeout(() => (controls.autoRotate = true), 4000); });

  /* Room shell */
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(ROOM.w, ROOM.d),
    new THREE.MeshStandardMaterial({ map: parquetTexture(), roughness: 0.5, metalness: 0.08 })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  const wallMat = new THREE.MeshStandardMaterial({ map: plasterTexture(), roughness: 0.95 });
  const mkWall = (w, x, z, ry) => {
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(w, ROOM.h), wallMat);
    wall.position.set(x, ROOM.h / 2, z);
    wall.rotation.y = ry;
    wall.receiveShadow = true;
    scene.add(wall);
    // baseboard
    const bb = new THREE.Mesh(
      new THREE.BoxGeometry(w, 0.18, 0.03),
      new THREE.MeshStandardMaterial({ color: 0x2a241c, roughness: 0.5 })
    );
    bb.position.set(x, 0.09, z);
    bb.rotation.y = ry;
    bb.translateZ(0.012);
    scene.add(bb);
  };
  mkWall(ROOM.w, 0, -ROOM.d / 2, 0);            // north
  mkWall(ROOM.w, 0, ROOM.d / 2, Math.PI);       // south
  mkWall(ROOM.d, -ROOM.w / 2, 0, Math.PI / 2);  // west
  mkWall(ROOM.d, ROOM.w / 2, 0, -Math.PI / 2);  // east

  const ceiling = new THREE.Mesh(
    new THREE.PlaneGeometry(ROOM.w, ROOM.d),
    new THREE.MeshStandardMaterial({ color: 0x14120e, roughness: 1 })
  );
  ceiling.rotation.x = Math.PI / 2;
  ceiling.position.y = ROOM.h;
  scene.add(ceiling);

  /* Lighting — gallery track spots */
  scene.add(new THREE.AmbientLight(0xfff2df, 0.28));
  const hemi = new THREE.HemisphereLight(0xf3ede2, 0x201a12, 0.35);
  scene.add(hemi);

  const loader = new THREE.TextureLoader();
  const hotspots = [];

  const addTrackLight = (x, z, tx, tz, intensity = 55) => {
    const spot = new THREE.SpotLight(0xffe9c4, intensity, 9, Math.PI / 6.5, 0.5, 1.7);
    spot.position.set(x, ROOM.h - 0.15, z);
    spot.target.position.set(tx, 1.4, tz);
    spot.castShadow = true;
    spot.shadow.mapSize.set(1024, 1024);
    scene.add(spot, spot.target);
    // visible fixture
    const fixture = new THREE.Mesh(
      new THREE.CylinderGeometry(0.05, 0.07, 0.16, 12),
      new THREE.MeshStandardMaterial({ color: 0x191713, roughness: 0.4, metalness: 0.6 })
    );
    fixture.position.set(x, ROOM.h - 0.08, z);
    scene.add(fixture);
  };

  /* North wall — Dutch Golden Age */
  const north = [
    { file: "art-night-watch.jpg", w: 3.6, h: 2.7, x: -4.6, meta: { coll: "Old Masters / Dutch Golden Age", title: "The Night Watch", body: "Rembrandt van Rijn · 1642 · Oil on canvas · OA-003" } },
    { file: "art-pearl-earring.jpg", w: 1.35, h: 1.6, x: -1.6, meta: { coll: "Old Masters / Dutch Golden Age", title: "Girl with a Pearl Earring", body: "Johannes Vermeer · c. 1665 · Oil on canvas · OA-001" } },
    { file: "art-milkmaid.jpg", w: 1.35, h: 1.5, x: 0.4, meta: { coll: "Old Masters / Dutch Golden Age", title: "The Milkmaid", body: "Johannes Vermeer · c. 1658 · Oil on canvas · OA-002" } }
  ];
  north.forEach((p) => {
    const g = buildPainting(loader, p);
    g.position.set(p.x, 1.85, -ROOM.d / 2 + 0.06);
    scene.add(g);
    g.traverse((o) => o.userData.hotspot && hotspots.push(o));
    addTrackLight(p.x, -ROOM.d / 2 + 1.1, p.x, -ROOM.d / 2);
  });

  /* South wall — Impressionism */
  const south = [
    { file: "art-water-lilies.jpg", w: 2.2, h: 1.7, x: -3.4, meta: { coll: "Old Masters / Impressionism", title: "Water Lilies", body: "Claude Monet · 1906 · Oil on canvas · OA-004" } },
    { file: "art-vangogh-self.jpg", w: 1.3, h: 1.55, x: 3.2, meta: { coll: "Old Masters / Impressionism", title: "Self-Portrait", body: "Vincent van Gogh · 1889 · Oil on canvas · OA-005" } }
  ];
  south.forEach((p) => {
    const g = buildPainting(loader, { ...p, h: p.h });
    g.position.set(p.x, 1.8, ROOM.d / 2 - 0.06);
    g.rotation.y = Math.PI;
    scene.add(g);
    g.traverse((o) => o.userData.hotspot && hotspots.push(o));
    addTrackLight(p.x, ROOM.d / 2 - 1.1, p.x, ROOM.d / 2);
  });

  /* East wall — Antiquities photograph (Taweris) */
  const taw = buildPainting(loader, {
    file: "art-egyptian-statue.jpg", w: 1.15, h: 1.8,
    meta: { coll: "Classical Antiquities / Egypt", title: "Statue of the Goddess Taweret", body: "New Kingdom · Greywacke · Historic archive photo · AN-003" }
  });
  taw.position.set(ROOM.w / 2 - 0.06, 1.85, 0);
  taw.rotation.y = -Math.PI / 2;
  scene.add(taw);
  taw.traverse((o) => o.userData.hotspot && hotspots.push(o));
  addTrackLight(ROOM.w / 2 - 1.1, 0, ROOM.w / 2, 0);

  /* Sculpture pedestals */
  const matStone = new THREE.MeshStandardMaterial({ color: 0xb9b2a4, roughness: 0.6, metalness: 0.05 });
  const matPed = new THREE.MeshStandardMaterial({ color: 0x23201a, roughness: 0.35, metalness: 0.2 });
  const addSculpture = (x, z, kind, scale, meta) => {
    const ped = new THREE.Mesh(new THREE.BoxGeometry(0.7, 1.05, 0.7), matPed);
    ped.position.set(x, 0.525, z);
    ped.castShadow = ped.receiveShadow = true;
    scene.add(ped);
    const st = buildStatue(kind, matStone);
    st.scale.setScalar(scale);
    st.position.set(x, 1.05, z);
    scene.add(st);
    st.userData.hotspot = meta;
    ped.userData.hotspot = meta;
    hotspots.push(st, ped);
    addTrackLight(x, z + 1.2, x, z, 40);
  };
  addSculpture(2.2, -0.4, "figure", 1.15, { coll: "Classical Antiquities / Greece", title: "Venus de Milo (study cast)", body: "Parian marble · c. 130 BCE · Interactive 3D scan in the Silver gallery · AN-001" });
  addSculpture(-2.4, 1.1, "amphora", 1.3, { coll: "Classical Antiquities / Greece", title: "Black-figure Amphora (study)", body: "Attic workshop · c. 540 BCE · 3D pipeline in progress · AN-002" });

  /* Click-to-inspect (click = press without drag) */
  const ray = new THREE.Raycaster();
  const ptr = new THREE.Vector2();
  let downAt = null;
  renderer.domElement.addEventListener("pointerdown", (e) => (downAt = { x: e.clientX, y: e.clientY }));
  renderer.domElement.addEventListener("pointerup", (e) => {
    if (!downAt || Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 6) return;
    const r = renderer.domElement.getBoundingClientRect();
    ptr.x = ((e.clientX - r.left) / r.width) * 2 - 1;
    ptr.y = -((e.clientY - r.top) / r.height) * 2 + 1;
    ray.setFromCamera(ptr, camera);
    const hit = ray.intersectObjects(hotspots, false)[0];
    if (hit) {
      const m = hit.object.userData.hotspot;
      document.getElementById("twinInfoColl").textContent = m.coll;
      document.getElementById("twinInfoTitle").textContent = m.title;
      document.getElementById("twinInfoMeta").textContent = m.body;
      info.classList.add("show");
      clearTimeout(info._t);
      info._t = setTimeout(() => info.classList.remove("show"), 6000);
    } else {
      info.classList.remove("show");
    }
  });

  /* Resize + render loop (paused when off-screen) */
  const ro = new ResizeObserver(() => {
    if (!shell.clientWidth) return;
    camera.aspect = shell.clientWidth / shell.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(shell.clientWidth, shell.clientHeight);
  });
  ro.observe(shell);

  let running = true;
  new IntersectionObserver(([e]) => (running = e.isIntersecting), { threshold: 0.02 }).observe(shell);

  renderer.setAnimationLoop(() => {
    if (!running) return;
    controls.update();
    renderer.render(scene, camera);
  });
}

try {
  init();
  document.getElementById("twinQuality").innerHTML = "WebGL · realtime";
} catch (err) {
  console.error("Digital twin failed to start", err);
  const q = document.getElementById("twinQuality");
  if (q) q.innerHTML = "WebGL unavailable";
  shell.innerHTML += `<div style="position:absolute;inset:0;display:grid;place-items:center;color:var(--paper-dim);font-size:14px;padding:30px;text-align:center">The digital twin needs WebGL. In production this room streams from the USD pipeline.</div>`;
}
