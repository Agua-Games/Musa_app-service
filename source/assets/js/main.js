/* ==========================================================================
   MUSA — main UI logic.
   All data access goes through MusaAPI (assets/js/api.js), which speaks the
   REST contract documented in docs/ and currently falls back to the local
   mock catalog. No view code here knows where the data comes from.
   ========================================================================== */
(() => {
  "use strict";

  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const brl = (n) => "R$ " + n.toLocaleString("pt-BR");

  /* ---------------------------------------------------------------- nav -- */
  const nav = $("#nav");
  addEventListener("scroll", () => nav.classList.toggle("scrolled", scrollY > 40), { passive: true });
  $("#navBurger").addEventListener("click", () => $("#navLinks").classList.toggle("mobile-open"));
  $$("#navLinks a").forEach((a) => a.addEventListener("click", () => $("#navLinks").classList.remove("mobile-open")));

  /* ------------------------------------------------------- scroll reveal -- */
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
  }, { threshold: 0.12 });

  /* Accessibility / test hook: skip entrance motion when reduced motion is
     requested (?fx=off also forces it — used by the visual regression pass). */
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches ||
                        new URLSearchParams(location.search).has("fxoff");
  if (new URLSearchParams(location.search).has("shot")) document.body.classList.add("shot-mode");
  const watchFx = reducedMotion
    ? () => $$(".fx:not(.in), .fx-img:not(.in)").forEach((el) => el.classList.add("in"))
    : () => $$(".fx:not(.in), .fx-img:not(.in)").forEach((el) => io.observe(el));
  watchFx();

  /* -------------------------------------------------------------- toast -- */
  const toast = (msg) => {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._h);
    t._h = setTimeout(() => t.classList.remove("show"), 2600);
  };

  /* ====================================================== COLLECTIONS ==== */
  async function renderCollections() {
    const cols = await MusaAPI.listCollections();
    const grid = $("#collectionsGrid");
    const tierLabel = { bronze: "Tier I · Photo", silver: "Tier II · 3D", gold: "Tier III · Twin" };
    const href = { bronze: "#bronze-gallery", silver: "#gallery-3d", gold: "#digital-twin" };
    grid.innerHTML = cols.map((c) => {
      const n = window.MUSA_MOCK.items.filter((i) => i.colecao === c.id && i.website_status === "published").length;
      return `
      <a class="collection-card fx" href="${href[c.tier]}">
        <img src="${c.cover}" alt="${c.title}" loading="lazy" />
        <div class="cc-body">
          <span class="cc-tier">${tierLabel[c.tier]}</span>
          <h3 class="serif">${c.title}</h3>
          <p>${c.description}</p>
          <span class="cc-go">Enter · ${n} pieces</span>
        </div>
      </a>`;
    }).join("");
    watchFx();
  }

  /* ==================================================== THE ROOM (WALL) == */
  const wallState = { spot: null, idx: 0 };
  const wallModal = $("#wallModal");

  async function renderWall() {
    const spots = window.MUSA_MOCK.wallHotspots || [];
    $("#wallSpots").innerHTML = spots.map((s) => `
      <button class="wall-spot" style="left:${s.x}%;top:${s.y}%" data-spot="${s.id}"
              aria-label="${s.label}">
        <span class="dot"></span>
        <span class="tag">${s.label.split("·").pop().trim()}<small>${s.label}</small></span>
        ${s.items.length > 1 ? `<span class="n">${s.items.length} pieces</span>` : ""}
      </button>`).join("");
    $$("#wallSpots .wall-spot").forEach((b) =>
      b.addEventListener("click", () => openWallSpot(b.dataset.spot)));
  }

  function wallItem() {
    const id = wallState.spot.items[wallState.idx];
    return window.MUSA_MOCK.items.find((i) => i.asset_id === id);
  }

  function paintWallPopup() {
    const i = wallItem();
    const n = wallState.spot.items.length;
    $("#wfImg").src = i.image;
    $("#wfImg").alt = i.titulo;
    $("#wfArea").textContent = `${wallState.spot.label} · ${i.asset_id}`;
    $("#wfTitle").textContent = i.titulo;
    $("#wfAuthor").textContent = `${i.autor} · ${i.data}`;
    $("#wfFicha").innerHTML = `
      <div><dt>Material</dt><dd>${i.material}</dd></div>
      <div><dt>Dimensions</dt><dd>${i.dimensoes}</dd></div>
      <div><dt>Collection</dt><dd>${i.colecao}${i.subcolecao ? " / " + i.subcolecao : ""}</dd></div>
      <div><dt>3D status</dt><dd>${i.model_status}</dd></div>`;
    $("#wfDesc").textContent = i.descricao;
    $("#wfPrev").hidden = n < 2;
    $("#wfNext").hidden = n < 2;
    $("#wfCounter").textContent = n > 1 ? `${wallState.idx + 1} / ${n}` : "";
    const has3d = i.model_viewer === "three_js" && i.model_status === "available";
    $("#wf3d").hidden = !has3d;
  }

  function openWallSpot(spotId, idx = 0) {
    wallState.spot = window.MUSA_MOCK.wallHotspots.find((s) => s.id === spotId);
    wallState.idx = idx;
    paintWallPopup();
    wallModal.classList.add("open");
    document.body.style.overflow = "hidden";
  }
  function closeWallSpot() {
    wallModal.classList.remove("open");
    document.body.style.overflow = "";
  }
  $("#wallClose").addEventListener("click", closeWallSpot);
  wallModal.addEventListener("click", (e) => { if (e.target === wallModal) closeWallSpot(); });
  $("#wfPrev").addEventListener("click", () => {
    wallState.idx = (wallState.idx - 1 + wallState.spot.items.length) % wallState.spot.items.length;
    paintWallPopup();
  });
  $("#wfNext").addEventListener("click", () => {
    wallState.idx = (wallState.idx + 1) % wallState.spot.items.length;
    paintWallPopup();
  });
  $("#wf3d").addEventListener("click", () => {
    const i = wallItem();
    closeWallSpot();
    openViewer(i.asset_id);
  });
  $("#wfRecord").addEventListener("click", () => {
    const i = wallItem();
    closeWallSpot();
    if (i.model_viewer === "three_js" || i.model_viewer === "kit_stream" || i.model_status !== "unavailable") openViewer(i.asset_id);
    else {
      // Photography-only record: open its bronze lightbox.
      openLightbox(i.asset_id);
    }
  });
  addEventListener("keydown", (e) => {
    if (!wallModal.classList.contains("open")) return;
    if (e.key === "ArrowLeft") $("#wfPrev").click();
    if (e.key === "ArrowRight") $("#wfNext").click();
  });

  /* ==================================================== BRONZE GALLERY === */
  async function renderBronze() {
    const items = (await MusaAPI.listItems("old-masters")).filter((i) => i.featured_on.includes("bronze-gallery"));
    $("#bronzeGrid").innerHTML = items.map((i, idx) => `
      <figure class="bronze-item fx" data-id="${i.asset_id}" style="transition-delay:${idx * 60}ms">
        <img src="${i.image}" alt="${i.titulo}" loading="lazy" />
        <figcaption><span class="zoomtag">Click to zoom</span><strong>${i.titulo}</strong>${i.autor}, ${i.data}</figcaption>
      </figure>`).join("");
    $$("#bronzeGrid .bronze-item").forEach((el) => el.addEventListener("click", () => openLightbox(el.dataset.id)));
    watchFx();
  }

  /* Lightbox with zoom / pan / maximize */
  const lb = $("#lightbox"), lbImg = $("#lbImg"), lbStage = $("#lbStage");
  let lbScale = 1, lbX = 0, lbY = 0, lbDrag = null;

  function lbApply() {
    lbImg.style.transform = `translate(${lbX}px, ${lbY}px) scale(${lbScale})`;
    lbImg.style.cursor = lbScale > 1 ? "grab" : "zoom-in";
  }
  function openLightbox(id) {
    const item = window.MUSA_MOCK.items.find((i) => i.asset_id === id);
    lbImg.src = item.image;
    lbImg.alt = item.titulo;
    $("#lbCap").innerHTML = `<strong>${item.titulo}</strong>${item.autor} · ${item.data} · ${item.material}`;
    lbScale = 1; lbX = 0; lbY = 0; lbApply();
    lb.classList.add("open");
    document.body.style.overflow = "hidden";
  }
  const closeLightbox = () => { lb.classList.remove("open"); document.body.style.overflow = ""; };
  $("#lbClose").addEventListener("click", closeLightbox);
  $("#lbZoomIn").addEventListener("click", () => { lbScale = Math.min(6, lbScale * 1.4); lbApply(); });
  $("#lbZoomOut").addEventListener("click", () => { lbScale = Math.max(1, lbScale / 1.4); if (lbScale === 1) { lbX = 0; lbY = 0; } lbApply(); });
  $("#lbReset").addEventListener("click", () => { lbScale = 1; lbX = 0; lbY = 0; lbApply(); });
  $("#lbFull").addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else lbStage.requestFullscreen?.().catch(() => toast("Fullscreen not available here"));
  });
  lbImg.addEventListener("wheel", (e) => {
    e.preventDefault();
    lbScale = Math.min(6, Math.max(1, lbScale * (e.deltaY < 0 ? 1.15 : 0.87)));
    if (lbScale === 1) { lbX = 0; lbY = 0; }
    lbApply();
  }, { passive: false });
  lbImg.addEventListener("pointerdown", (e) => {
    lbDrag = { x: e.clientX - lbX, y: e.clientY - lbY };
    lbImg.setPointerCapture(e.pointerId);
    lbImg.style.cursor = "grabbing";
  });
  lbImg.addEventListener("pointermove", (e) => {
    if (!lbDrag) return;
    lbX = e.clientX - lbDrag.x; lbY = e.clientY - lbDrag.y; lbApply();
  });
  lbImg.addEventListener("pointerup", () => { lbDrag = null; lbApply(); });
  lb.addEventListener("click", (e) => { if (e.target === lb) closeLightbox(); });

  /* ==================================================== SILVER GALLERY === */
  async function renderSilver() {
    const cols = ["classical-antiquities", "decorative-arts"];
    const items = [];
    for (const c of cols) items.push(...(await MusaAPI.listItems(c)));
    const shown = items.filter((i) => i.featured_on.includes("silver-gallery"));
    $("#silverGrid").innerHTML = shown.map((i, idx) => `
      <div class="silver-item fx" data-id="${i.asset_id}" style="transition-delay:${idx * 60}ms">
        <img src="${i.image}" alt="${i.titulo}" loading="lazy" />
        <span class="silver-badge ${i.model_status}">${i.model_status === "processing" ? "3D · in pipeline" : i.model_viewer === "kit_stream" ? "Streamed twin" : "Interactive 3D"}</span>
        <div class="si-label"><h3 class="serif">${i.titulo}</h3><span>${i.autor} · ${i.data}</span></div>
      </div>`).join("");
    $$("#silverGrid .silver-item").forEach((el) => el.addEventListener("click", () => openViewer(el.dataset.id)));
    watchFx();
  }

  /* 3D viewer modal ------------------------------------------------------- */
  const vm = $("#viewerModal");
  let currentItem = null;

  function ensureViewer(timeout = 3000) {
    return new Promise((resolve) => {
      if (window.MusaItemViewer) return resolve(true);
      const t0 = Date.now();
      (function poll() {
        if (window.MusaItemViewer) return resolve(true);
        if (Date.now() - t0 > timeout) return resolve(false);
        setTimeout(poll, 100);
      })();
    });
  }

  async function openViewer(id) {
    currentItem = await MusaAPI.getItem(id);
    const i = currentItem;
    vm.classList.add("open");
    document.body.style.overflow = "hidden";

    // panes
    $("#paneDetails").innerHTML = `
      <p class="eyebrow">${i.asset_id} · ${i.colecao}</p>
      <h3 class="serif">${i.titulo}</h3>
      <p class="author">${i.autor}</p>
      <dl class="ficha">
        <div><dt>Date</dt><dd>${i.data}</dd></div>
        <div><dt>Material</dt><dd>${i.material}</dd></div>
        <div><dt>Dimensions</dt><dd>${i.dimensoes}</dd></div>
        <div><dt>Collection</dt><dd>${i.colecao}</dd></div>
        <div><dt>3D status</dt><dd>${i.model_status}</dd></div>
        <div><dt>Viewer</dt><dd>${i.model_viewer || "—"}</dd></div>
      </dl>
      <p class="viewer-desc">${i.descricao}</p>`;

    $("#paneSource").innerHTML = `
      <p class="eyebrow">Provenance & pipeline</p>
      <h3 class="serif" style="font-size:22px">Scan source</h3>
      <dl class="ficha">
        <div><dt>Formats</dt><dd>${(i.model_formats || []).join(", ") || "photo only"}</dd></div>
        <div><dt>Delivery</dt><dd>${i.model_primary || "—"}</dd></div>
        ${i.model_source ? `<div><dt>Source</dt><dd><a href="${i.model_source}" target="_blank" rel="noopener" style="color:var(--gold)">Sketchfab / museum record ↗</a></dd></div>` : ""}
      </dl>
      <div class="sketchfab-slot" style="margin-top:18px">
        A Sketchfab embed slot lives here for externally-hosted scans
        (configure a model id in <code>assets/js/main.js → SKETCHFAB_EMBED_ID</code>).
        <iframe data-sketchfab loading="lazy" title="Sketchfab embed" hidden></iframe>
      </div>`;

    // View pane content depends on the viewer the record declares.
    const view = $("#paneView");
    if (i.model_viewer === "three_js" && i.model_status === "available") {
      view.innerHTML = `<div id="vmMount" style="position:absolute;inset:0"></div>`;
      $("#vmLoading").style.display = "grid";
      $("#vmFallback").style.display = "none";
      const ok = await ensureViewer();
      if (ok && window.MusaItemViewer) {
        window.MusaItemViewer.load(i, $("#vmMount"), $("#vmLoading"), $("#vmFallback"));
      } else {
        $("#vmLoading").style.display = "none";
        const f = $("#vmFallback");
        f.style.display = "grid";
        f.innerHTML = "The WebGL viewer could not load (Three.js CDN unreachable).<br/>The record card still carries the full provenance of this piece.";
      }
    } else if (i.model_viewer === "kit_stream") {
      view.innerHTML = `<div class="kit-placeholder" style="margin:4px">
        <p class="eyebrow" style="margin-bottom:10px">Omniverse Kit App streaming</p>
        This piece is delivered in production via the Omniverse Kit App Streaming pipeline
        (<code>model_viewer: kit_stream</code>). The embedded stream session would initialize here:
        <br/><br/>▸ session request → <code>GET /streaming/session</code><br/>▸ QoS metrics surfaced in the HUD
      </div>`;
    } else if (i.model_status === "processing") {
      view.innerHTML = `<div class="kit-placeholder" style="margin:4px">
        <p class="eyebrow" style="margin-bottom:10px">In the 3D pipeline</p>
        Photogrammetry for this piece is in progress. The <code>model_status</code> field flips to
        <code>available</code> when the optimized GLB lands on the CDN, and this slot becomes a live viewer.
      </div>`;
    } else {
      view.innerHTML = `<div class="kit-placeholder" style="margin:4px">This piece is published as photography only — no 3D model is attached to its record yet.</div>`;
    }
    switchTab("view");
  }

  function closeViewer() {
    vm.classList.remove("open");
    document.body.style.overflow = "";
    if (window.MusaItemViewer) window.MusaItemViewer.dispose();
  }
  $("#vmClose").addEventListener("click", closeViewer);
  vm.addEventListener("click", (e) => { if (e.target === vm) closeViewer(); });

  function switchTab(name) {
    $$(".viewer-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    ["View", "Details", "Source"].forEach((n) => $("#pane" + n).classList.toggle("hidden", n.toLowerCase() !== name));
  }
  $$(".viewer-tabs button").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));

  /* ============================================================ CINEMA === */
  let films = [];
  async function renderCinema() {
    films = await MusaAPI.listFilms();
    $("#playlist").innerHTML = films.map((f, idx) => `
      <div class="playlist-item ${idx === 0 ? "active" : ""}" data-id="${f.id}">
        <img src="${f.poster}" alt="${f.title}" loading="lazy" />
        <div>
          <p class="status ${f.status === "upcoming" ? "upcoming" : ""}">${f.status === "now-showing" ? "● Now showing" : "◷ " + f.premiere}</p>
          <h4>${f.title}</h4>
          <p>${f.director} · ${f.year} · ${f.duration}</p>
        </div>
      </div>`).join("");
    $$("#playlist .playlist-item").forEach((el) => el.addEventListener("click", () => playFilm(el.dataset.id)));
    const first = films.find((f) => f.status === "now-showing") || films[0];
    selectFilm(first.id, false);
  }

  const video = $("#playerVideo");
  function selectFilm(id, autoplay = true) {
    const f = films.find((x) => x.id === id);
    $$("#playlist .playlist-item").forEach((el) => el.classList.toggle("active", el.dataset.id === id));
    const q = $("#pbQuality").value === "auto" ? "1080p" : $("#pbQuality").value;
    video.src = f.sources[q] || Object.values(f.sources)[0];
    $("#ptTitle").textContent = f.title;
    $("#ptMeta").textContent = `${f.director} · ${f.year} · ${f.duration}`;
    $("#player").classList.add("paused");
    $("#pbPlay").textContent = "▶";
    if (autoplay) video.play().catch(() => {});
  }
  function playFilm(id) { selectFilm(id, true); }

  $("#pbPlay").addEventListener("click", () => {
    if (video.paused) { video.play(); } else { video.pause(); }
  });
  video.addEventListener("play", () => { $("#player").classList.remove("paused"); $("#pbPlay").textContent = "❚❚"; });
  video.addEventListener("pause", () => { $("#player").classList.add("paused"); $("#pbPlay").textContent = "▶"; });
  video.addEventListener("timeupdate", () => {
    if (video.duration) {
      $("#pbFill").style.width = (video.currentTime / video.duration * 100) + "%";
      const m = Math.floor(video.currentTime / 60), s = String(Math.floor(video.currentTime % 60)).padStart(2, "0");
      $("#pbTime").textContent = `${m}:${s}`;
    }
  });
  $("#pbProgress").addEventListener("click", (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    if (video.duration) video.currentTime = ((e.clientX - r.left) / r.width) * video.duration;
  });
  $("#pbQuality").addEventListener("change", () => {
    const t = video.currentTime, p = video.paused;
    selectFilm(films.find((f) => $("#ptTitle").textContent === f.title)?.id || films[0].id, false);
    video.currentTime = t;
    if (!p) video.play();
    toast("Quality ladder is a scaffold — ABR manifests plug in here");
  });
  $("#pbCc").addEventListener("click", () => toast("Subtitle tracks plug into the streaming manifest"));
  $("#pbFs").addEventListener("click", () => {
    const p = $("#player");
    if (document.fullscreenElement) document.exitFullscreen(); else p.requestFullscreen?.();
  });

  /* ============================================================= STORE == */
  const cart = new Map(); // id -> qty
  async function renderStore() {
    const products = await MusaAPI.listProducts();
    const tags = ["All", ...new Set(products.map((p) => p.tag))];
    $("#storeFilters").innerHTML = tags.map((t, i) => `<button class="${i === 0 ? "active" : ""}" data-tag="${t}">${t}</button>`).join("");
    $$("#storeFilters button").forEach((b) => b.addEventListener("click", () => {
      $$("#storeFilters button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      drawProducts(products, b.dataset.tag);
    }));
    drawProducts(products, "All");
  }
  function drawProducts(products, tag) {
    const list = tag === "All" ? products : products.filter((p) => p.tag === tag);
    $("#storeGrid").innerHTML = list.map((p) => `
      <div class="product">
        <div class="p-img"><img src="${p.image}" alt="${p.name}" loading="lazy" /></div>
        <div class="p-body">
          <p class="p-tag">${p.tag}</p>
          <h3 class="serif">${p.name}</h3>
          <div class="p-foot"><span class="price">${brl(p.price)}</span>
            <button class="add" data-id="${p.id}">${cart.has(p.id) ? "In cart ✓" : "Add to cart"}</button></div>
        </div>
      </div>`).join("");
    $$("#storeGrid .add").forEach((b) => b.addEventListener("click", () => {
      cart.set(b.dataset.id, (cart.get(b.dataset.id) || 0) + 1);
      b.textContent = "In cart ✓"; b.classList.add("added");
      updateCart();
      toast("Added to cart");
    }));
  }
  function updateCart() {
    const products = window.MUSA_MOCK.products;
    let count = 0, total = 0, rows = "";
    for (const [id, qty] of cart) {
      const p = products.find((x) => x.id === id);
      if (!p) continue;
      count += qty; total += p.price * qty;
      rows += `<div class="cart-line">
        <img src="${p.image}" alt="" /><div><b style="font-weight:500">${p.name}</b><br/><span style="color:var(--paper-faint);font-size:12px">${brl(p.price)}</span></div>
        <div class="qty"><button data-dec="${id}">−</button><span>${qty}</span><button data-inc="${id}">+</button></div>
      </div>`;
    }
    $("#cartCount").textContent = count;
    $("#cartItems").innerHTML = rows || `<p class="cart-empty">The cart is empty.<br/>Everything here is scaffolding for the commerce module.</p>`;
    $("#cartTotal").textContent = brl(total);
    $$("#cartItems [data-inc]").forEach((b) => b.addEventListener("click", () => { cart.set(b.dataset.inc, cart.get(b.dataset.inc) + 1); updateCart(); }));
    $$("#cartItems [data-dec]").forEach((b) => b.addEventListener("click", () => {
      const q = cart.get(b.dataset.dec) - 1;
      q <= 0 ? cart.delete(b.dataset.dec) : cart.set(b.dataset.dec, q);
      updateCart();
    }));
  }
  const drawer = $("#cartDrawer"), scrim = $("#scrim");
  const openCart = () => { drawer.classList.add("open"); scrim.classList.add("show"); updateCart(); };
  const closeCart = () => { drawer.classList.remove("open"); scrim.classList.remove("show"); };
  $("#cartOpen").addEventListener("click", openCart);
  $("#cartClose").addEventListener("click", closeCart);
  scrim.addEventListener("click", closeCart);
  $("#checkoutBtn").addEventListener("click", () => toast("Checkout is a stub — the commerce module plugs in here"));

  /* ============================================================= PLANS == */
  let chosenTier = "bronze";
  const chosenModules = new Set();
  async function renderPlans() {
    const { tiers, modules } = await MusaAPI.plans();
    $("#tiersGrid").innerHTML = tiers.map((t) => `
      <div class="tier-card ${t.popular ? "popular" : ""}" data-tier="${t.id}">
        ${t.popular ? `<span class="t-badge">Most chosen</span>` : ""}
        <p class="t-name">${t.name}</p>
        <h3 class="serif">${t.title}</h3>
        <p class="t-blurb">${t.blurb}</p>
        <p class="t-price">${brl(t.price)}<small> /mo</small></p>
        <ul>${t.features.map((f) => `<li>${f}</li>`).join("")}</ul>
        <button class="btn ${t.id === chosenTier ? "solid" : ""}" data-pick="${t.id}">${t.id === chosenTier ? "Selected" : "Choose " + t.name}</button>
      </div>`).join("");
    $$("#tiersGrid [data-pick]").forEach((b) => b.addEventListener("click", () => { chosenTier = b.dataset.pick; renderPlans(); updateTotal(); }));

    $("#modulesGrid").innerHTML = modules.map((m) => `
      <label class="module ${chosenModules.has(m.id) ? "on" : ""}">
        <input type="checkbox" data-mod="${m.id}" ${chosenModules.has(m.id) ? "checked" : ""} />
        <span><h4>${m.name}</h4><p>${m.desc}</p></span>
        <span class="m-price">${brl(m.price)}<small>${m.unit}</small></span>
      </label>`).join("");
    $$("#modulesGrid input").forEach((c) => c.addEventListener("change", () => {
      c.checked ? chosenModules.add(c.dataset.mod) : chosenModules.delete(c.dataset.mod);
      c.closest(".module").classList.toggle("on", c.checked);
      updateTotal();
    }));
    updateTotal();
  }
  function updateTotal() {
    const { tiers, modules } = window.MUSA_MOCK.plans;
    const tier = tiers.find((t) => t.id === chosenTier);
    const mods = modules.filter((m) => chosenModules.has(m.id));
    const sum = tier.price + mods.reduce((a, m) => a + m.price, 0);
    $("#totalLabel").textContent = tier.name + " · " + tier.title;
    $("#totalModules").textContent = mods.length ? "+ " + mods.map((m) => m.name).join(" · ") : "No modules selected";
    $("#totalPrice").textContent = brl(sum);
  }
  $("#proposalBtn").addEventListener("click", () => {
    const { tiers, modules } = window.MUSA_MOCK.plans;
    const tier = tiers.find((t) => t.id === chosenTier);
    const mods = modules.filter((m) => chosenModules.has(m.id));
    const body = encodeURIComponent(
      `Hello MUSA,\n\nWe would like a proposal for the ${tier.name} tier (${tier.title})` +
      (mods.length ? ` with the modules: ${mods.map((m) => m.name).join(", ")}.` : ".") +
      `\n\nVenue:\nCollection size:\n`);
    location.href = `mailto:hello@musa.example?subject=MUSA proposal — ${tier.name} tier&body=${body}`;
  });

  /* ============================================================= ADMIN == */
  const loginModal = $("#loginModal");

  function openLogin() { loginModal.classList.add("open"); $("#loginErr").textContent = ""; }
  function closeLogin() { loginModal.classList.remove("open"); }
  $("#navLogin").addEventListener("click", (e) => {
    e.preventDefault();
    MusaAPI.session ? enterAdmin() : openLogin();
  });
  $("#footLogin").addEventListener("click", (e) => { e.preventDefault(); MusaAPI.session ? enterAdmin() : openLogin(); });
  loginModal.addEventListener("click", (e) => { if (e.target === loginModal) closeLogin(); });
  $$(".demo-chip").forEach((c) => c.addEventListener("click", () => {
    $("#loginEmail").value = c.dataset.email;
    $("#loginPass").value = "demo";
    $("#loginForm").requestSubmit();
  }));
  $("#loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await MusaAPI.login($("#loginEmail").value.trim(), $("#loginPass").value);
      closeLogin();
      enterAdmin();
      toast("Welcome, " + MusaAPI.session.name);
    } catch (err) {
      $("#loginErr").textContent = err.message;
    }
  });
  $("#logoutBtn").addEventListener("click", () => {
    MusaAPI.logout();
    $("#admin").classList.remove("open");
    $("#navLogin").textContent = "Sign in";
    toast("Signed out");
  });

  function enterAdmin() {
    const s = MusaAPI.session;
    $("#admin").classList.add("open");
    $("#navLogin").textContent = "Dashboard";
    $("#adminName").textContent = s.name + " — " + s.org;
    $("#adminRole").textContent = s.role === "musa" ? "MUSA team member" : "Venue owner · client tier";
    $("#adminAvatar").textContent = s.name[0];
    $("#adminSub").textContent = s.note;
    setView(s.role === "musa" ? "musa" : "client");
    fbReset();
    refreshStats();
    $("#admin").scrollIntoView({ behavior: "smooth" });
  }

  function setView(view) {
    // Two admin tiers — a client account cannot open the MUSA team console.
    const s = MusaAPI.session;
    const allowed = s && (s.role === "musa" || view === "client");
    $$("#roleSwitch button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
    $("#adminClient").style.display = view === "client" && allowed ? "" : "none";
    $("#adminMusa").style.display = view === "musa" && allowed ? "" : "none";
    if (!allowed) toast("That console requires MUSA team credentials — try team@musa.demo");
  }
  $$("#roleSwitch button").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));

  /* Folder-style collection browser -------------------------------------- */
  const fb = { path: [], selected: new Set(), currentItem: null };

  function fbReset() { fb.path = []; fb.selected = new Set(); fb.currentItem = null; renderFb(); }

  function fbLocation() {
    // path: [] root | ["col"] collection | ["col","sub"] subcollection
    const [colId, subId] = fb.path;
    const col = window.MUSA_MOCK.collections.find((c) => c.id === colId);
    const sub = col?.subcollections.find((s) => s.id === subId);
    return { col, sub };
  }

  function renderFb() {
    const { col, sub } = fbLocation();
    const list = $("#fbList");
    const crumb = $("#fbCrumb");

    if (!col) {
      crumb.innerHTML = "<b>acervo/</b>";
      $("#fbUp").style.display = "none";
      list.innerHTML = window.MUSA_MOCK.collections.map((c) => {
        const n = window.MUSA_MOCK.items.filter((i) => i.colecao === c.id).length;
        return fbRow({ icon: "🗀", name: c.title, small: c.description, meta: `${n} items`, status: c.tier, id: "col:" + c.id });
      }).join("");
    } else if (!sub) {
      crumb.innerHTML = `<b>acervo/</b>${col.id}/`;
      $("#fbUp").style.display = "";
      const subs = col.subcollections.map((s) => {
        const n = window.MUSA_MOCK.items.filter((i) => i.colecao === col.id && i.subcolecao === s.id).length;
        return fbRow({ icon: "🗀", name: s.title, small: "Subcollection", meta: `${n} items`, status: "", id: "sub:" + s.id });
      }).join("");
      const loose = window.MUSA_MOCK.items.filter((i) => i.colecao === col.id && !i.subcolecao);
      list.innerHTML = subs + loose.map((i) => fbItemRow(i)).join("");
    } else {
      crumb.innerHTML = `<b>acervo/</b>${col.id}/${sub.id}/`;
      $("#fbUp").style.display = "";
      const items = window.MUSA_MOCK.items.filter((i) => i.colecao === col.id && i.subcolecao === sub.id);
      list.innerHTML = items.map((i) => fbItemRow(i)).join("") ||
        `<p class="cart-empty">Empty subcollection.</p>`;
    }

    // wire rows
    $$("#fbList .fb-row[data-nav]").forEach((r) => r.addEventListener("click", (e) => {
      if (e.target.matches("input")) return;
      fb.path.push(r.dataset.nav);
      fb.selected.clear();
      renderFb();
    }));
    $$("#fbList .fb-row[data-item]").forEach((r) => {
      r.addEventListener("click", (e) => {
        if (e.target.matches("input")) return;
        selectItem(r.dataset.item);
        $$("#fbList .fb-row").forEach((x) => x.classList.remove("selected"));
        r.classList.add("selected");
      });
    });
    $$("#fbList input[type=checkbox]").forEach((c) => c.addEventListener("change", () => {
      c.checked ? fb.selected.add(c.value) : fb.selected.delete(c.value);
      updateFbBar();
    }));
    updateFbBar();
  }

  function fbRow({ icon, name, small, meta, status, id }) {
    // "col:x" rows live at root and push the collection id; "sub:x" rows push
    // the subcollection id (the collection is already in the path).
    const seg = id.slice(4);
    return `
    <div class="fb-row" data-nav="${seg}" data-kind="${id.startsWith("col:") ? "col" : "sub"}">
      <span style="width:15px"></span><span class="fi">${icon}</span>
      <span class="fname">${name}<small>${small}</small></span>
      <span class="fmeta">${meta}</span>
      <span class="fstatus">${status}</span>
    </div>`;
  }

  function fbItemRow(i) {
    return `
    <div class="fb-row" data-item="${i.asset_id}">
      <input type="checkbox" value="${i.asset_id}" ${fb.selected.has(i.asset_id) ? "checked" : ""} />
      <span class="fi">🗎</span>
      <span class="fname">${i.titulo}<small>${i.asset_id} · ${i.autor}</small></span>
      <span class="fmeta">${i.model_status}</span>
      <span style="display:flex;gap:10px;align-items:center">
        ${i.hero ? `<span class="fhero">★ hero</span>` : ""}
        <span class="fstatus ${i.website_status}">${i.website_status}</span>
      </span>
    </div>`;
  }

  function updateFbBar() {
    const n = fb.selected.size;
    $("#fbSelection").textContent = n ? `${n} selected` : "Nothing selected";
    ["#fbPublish", "#fbUnpublish", "#fbHeroOn", "#fbHeroOff"].forEach((s) => { $(s).disabled = !n; });
  }

  $("#fbUp").addEventListener("click", () => { fb.path.pop(); fb.selected.clear(); renderFb(); });

  async function bulkPatch(patchFn, doneMsg) {
    for (const id of fb.selected) {
      await MusaAPI.saveItem({ asset_id: id, ...patchFn(window.MUSA_MOCK.items.find((i) => i.asset_id === id)) });
    }
    fb.selected.clear();
    renderFb(); refreshStats();
    toast(doneMsg);
  }
  $("#fbPublish").addEventListener("click", () => bulkPatch(() => ({ website_status: "published" }), "Published to the website"));
  $("#fbUnpublish").addEventListener("click", () => bulkPatch(() => ({ website_status: "draft" }), "Demoted to draft — hidden from visitors"));
  $("#fbHeroOn").addEventListener("click", () => bulkPatch(() => ({ hero: true }), "Promoted to hero pieces"));
  $("#fbHeroOff").addEventListener("click", () => bulkPatch(() => ({ hero: false }), "Removed from hero pieces"));

  function selectItem(id) {
    const i = window.MUSA_MOCK.items.find((x) => x.asset_id === id);
    if (!i) return;
    fb.currentItem = i;
    $("#ipImg").src = i.image;
    $("#ipId").textContent = `${i.asset_id} · ${i.colecao}${i.subcolecao ? " / " + i.subcolecao : ""}`;
    $("#ipTitle").textContent = i.titulo;
    $("#ipAuthor").textContent = `${i.autor} · ${i.data} · ${i.material}`;
    $("#ipStatus").value = i.website_status;
    $("#ipHero").checked = !!i.hero;
  }
  $("#ipStatus").addEventListener("change", async () => {
    if (!fb.currentItem) return;
    await MusaAPI.saveItem({ asset_id: fb.currentItem.asset_id, website_status: $("#ipStatus").value });
    renderFb(); refreshStats();
    toast("Visibility updated (POST /items)");
  });
  $("#ipHero").addEventListener("change", async () => {
    if (!fb.currentItem) return;
    await MusaAPI.saveItem({ asset_id: fb.currentItem.asset_id, hero: $("#ipHero").checked });
    renderFb(); refreshStats();
    toast($("#ipHero").checked ? "Hero piece ★" : "Hero removed");
  });

  function refreshStats() {
    const items = window.MUSA_MOCK.items;
    const heroes = items.filter((i) => i.hero).length;
    const pub = items.filter((i) => i.website_status === "published").length;
    const models = items.filter((i) => i.model_status === "available").length;
    $("#amHero").textContent = `${heroes} / 50`;
    $("#amHeroBar").style.width = Math.min(100, heroes / 50 * 100) + "%";
    $("#amPublished").textContent = `${pub} of ${items.length}`;
    $("#amPubBar").style.width = (pub / items.length * 100) + "%";
    $("#amModels").textContent = `${models} · 1 processing`;
    $("#amModelBar").style.width = Math.min(100, models / items.length * 100) + "%";
  }

  /* ======================================================== AI ASSISTANT = */
  const chatPanel = $("#chatPanel"), chatLog = $("#chatLog");
  function openChat() { chatPanel.classList.add("open"); $("#chatInput").focus(); }
  $("#chatClose").addEventListener("click", () => chatPanel.classList.remove("open"));

  function addMsg(text, who, suggest) {
    const div = document.createElement("div");
    div.className = "chat-msg " + who;
    div.textContent = text;
    if (suggest) {
      const s = document.createElement("span");
      s.className = "suggest";
      s.textContent = "→ Open “" + suggest.title + "” in the 3D gallery";
      s.addEventListener("click", () => { chatPanel.classList.remove("open"); openViewer(suggest.id); });
      div.appendChild(s);
    }
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
  }
  function addTyping() {
    const d = document.createElement("div");
    d.className = "chat-msg bot";
    d.innerHTML = `<span class="chat-typing"><i></i><i></i><i></i></span>`;
    chatLog.appendChild(d);
    chatLog.scrollTop = chatLog.scrollHeight;
    return d;
  }

  async function ask(question) {
    if (!question.trim()) return;
    openChat();
    addMsg(question, "user");
    $("#assistantInput").value = "";
    $("#chatInput").value = "";
    const t = addTyping();
    const res = await MusaAPI.assistantAsk(question, { museumId: "musa-demo" });
    t.remove();
    const sug = res.suggestedArtifacts?.[0]
      ? { id: res.suggestedArtifacts[0].id, title: res.suggestedArtifacts[0].title }
      : null;
    addMsg(res.answer, "bot", sug);
  }
  $("#assistantForm").addEventListener("submit", (e) => { e.preventDefault(); ask($("#assistantInput").value); });
  $("#chatForm").addEventListener("submit", (e) => { e.preventDefault(); ask($("#chatInput").value); });
  $$(".assistant-hints button").forEach((b) => b.addEventListener("click", () => ask(b.dataset.q)));

  /* ============================================================== MISC === */
  addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeLightbox(); closeViewer(); closeWallSpot(); closeLogin(); closeCart(); chatPanel.classList.remove("open"); }
  });

  /* =============================================================== INIT == */
  renderCollections();
  renderWall();
  renderBronze();
  renderSilver();
  renderCinema();
  renderStore();
  renderPlans();
  updateCart();
})();
