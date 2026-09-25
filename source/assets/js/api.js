/**
 * MUSA — frontend API layer.
 *
 * Contract-first access to the collection backend. Every method documents the
 * REST resource it targets (see docs/Musa_design document_technical-specs_v1.1.md §6.1
 * and §6.4). Three ways to serve the same shapes:
 *
 *   - "mock": the in-browser catalog (window.MUSA_MOCK) — the platform demo;
 *   - "live" + static: the builder-emitted JSON files under api/ (ADR 0008,
 *     M1.1) — what client sites run today, read-only;
 *   - "live" (dynamic): the MUSA backend — same envelope, writes enabled.
 *
 * The builder emits data/runtime.js with the client's config; main.js applies
 * it at boot via MusaAPI.configure(window.MUSA_RUNTIME).
 *
 * Live responses must match the card contract (schemas/card.schema.json).
 */
const MusaAPI = (() => {
  const state = {
    mode: "mock",                 // "mock" | "live"
    baseUrl: "/api/v1",           // collection API root (REST)
    static: false,                // live mode against builder-emitted JSON files
    token: null,                  // JWT once auth exists (§7.1)
    session: null                 // current identity, set by login()
  };

  const clone = (o) => JSON.parse(JSON.stringify(o));
  const mock = () => window.MUSA_MOCK;

  // "/collections/x/items" -> "/collections/x/items.json" (the static API is
  // a tree of JSON files; query strings only exist on /search, handled there).
  const staticPath = (path) => path.replace(/\?.*$/, "") + ".json";

  async function request(path, options = {}) {
    const url = state.baseUrl + (state.static ? staticPath(path) : path);
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
        ...(options.headers || {})
      }
    });
    if (!res.ok) {
      const err = new Error(`MusaAPI ${res.status} on ${path}`);
      err.status = res.status;
      throw err;
    }
    const body = await res.json();
    // The API envelope is { data, meta } everywhere (docs/api-estatica.md).
    return body && typeof body === "object" && "data" in body && "meta" in body ? body.data : body;
  }

  // The static API is the gated build output: a missing file IS "not found".
  async function requestOrNull(path) {
    try {
      return await request(path);
    } catch (err) {
      if (err.status === 404) return undefined;
      throw err;
    }
  }

  async function via(path, liveCall, mockCall) {
    if (state.mode === "live") return liveCall(path);
    // Simulate network latency so the UI's loading states are exercised.
    await new Promise((r) => setTimeout(r, 120));
    return clone(mockCall());
  }

  // Writes, auth and the assistant need the dynamic backend (M1.4+). On a
  // static client site they fall back to the in-browser catalog so the admin
  // demo keeps working — with a clear note that nothing persists.
  const staticReadOnly = () => state.mode === "live" && state.static;

  /* Tokenizing mirrors builder/musa_build/api.py: lowercase, split on
     non-word characters, drop tokens shorter than 2. */
  const tokenize = (text) => text.toLowerCase().split(/[^\w]+/u).filter((t) => t.length >= 2);

  let searchIndexPromise = null;
  async function staticSearch(query) {
    searchIndexPromise = searchIndexPromise || request("/search");
    const index = await searchIndexPromise;
    const tokens = tokenize(query);
    if (!tokens.length) return [];
    let ids = null;
    for (const token of tokens) {
      const bucket = index.terms[token] || [];
      ids = ids === null ? bucket.slice() : ids.filter((id) => bucket.includes(id));
    }
    let hits = (ids || []).map((id) => index.items[id]).filter(Boolean);
    if (!hits.length) {
      // Fallback: substring over the slim records (the mock's semantics),
      // so informal queries still answer something. Semantics arrive in M2.
      const q = query.toLowerCase();
      hits = Object.values(index.items).filter((i) =>
        [i.titulo, i.autor, ...(i.tags || [])].join(" ").toLowerCase().includes(q));
    }
    return hits;
  }

  return {
    configure(opts) { Object.assign(state, opts); },
    get session() { return state.session; },

    /* ---- Collection API (§6.1) ---------------------------------------- */

    /** GET /collections — list collections and subcollections. */
    listCollections() {
      return via("/collections", () => request("/collections"), () => mock().collections);
    },

    /** GET /collections/{id}/items — list items, optionally filtered. */
    listItems(collectionId, { includeDrafts = false } = {}) {
      return via(
        `/collections/${collectionId}/items`,
        // A collection with no file is a collection this build didn't publish —
        // an empty list, not an exception (drafts/above-tier must not leak).
        async () => (await requestOrNull(`/collections/${collectionId}/items`)) || [],
        () => mock().items.filter((i) => i.colecao === collectionId &&
          (includeDrafts || i.website_status === "published"))
      );
    },

    /** GET /items/{id} — full record card for one piece. */
    getItem(assetId) {
      return via(`/items/${assetId}`, () => requestOrNull(`/items/${assetId}`),
        () => mock().items.find((i) => i.asset_id === assetId));
    },

    /** GET /search?q= — term index in static mode; semantic (RAG) at scale. */
    search(query) {
      return via(`/search?q=${encodeURIComponent(query)}`,
        () => (state.static ? staticSearch(query) : request(`/search?q=${encodeURIComponent(query)}`)),
        () => {
          const q = query.toLowerCase();
          return mock().items.filter((i) =>
            [i.titulo, i.autor, i.descricao, ...(i.tags || [])].join(" ").toLowerCase().includes(q));
        });
    },

    /** POST /items — create or update an item (write path; backend-of-scale). */
    saveItem(patch) {
      if (staticReadOnly()) {
        return Promise.reject(new Error(
          "The static API is read-only — this change needs the MUSA backend (M1.4). Nothing was persisted."));
      }
      return via("/items", () => request("/items", { method: "POST", body: JSON.stringify(patch) }),
        () => {
          const item = mock().items.find((i) => i.asset_id === patch.asset_id);
          if (item) Object.assign(item, patch);
          return item;
        });
    },

    /* ---- Assistant API (§6.4) ------------------------------------------ */

    /**
     * POST /assistant/ask — ask a question about the collection.
     * Live payload: { question, context: { collectionIds, ageGroup } }
     * Live response: { answer, suggestedArtifacts }
     */
    async assistantAsk(question, context = {}) {
      if (state.mode === "live" && !state.static) {
        return request("/assistant/ask", { method: "POST", body: JSON.stringify({ question, context }) });
      }
      // Static sites run the local stand-in: the LLM pipeline is a backend module.
      await new Promise((r) => setTimeout(r, 450)); // assistant "thinking"
      return mockAssistantAnswer(question);
    },

    /* ---- Auth (backend: Payload native auth + JWT, §7.1) ---------------- */
    /** POST /auth/login — demo login against local identities for now. */
    async login(email, password) {
      if (state.mode === "live" && !state.static) {
        const res = await request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
        state.token = res.token;
        state.session = res.user;
        return res.user;
      }
      await new Promise((r) => setTimeout(r, 350));
      const acc = mock().accounts.find((a) => a.email === email && a.password === password);
      if (!acc) throw new Error("Invalid credentials (demo accounts are listed on the login panel).");
      state.session = { email: acc.email, role: acc.role, name: acc.name, org: acc.org, note: acc.note };
      return state.session;
    },

    logout() { state.session = null; if (state.mode === "live") state.token = null; },

    /* ---- Service layer (scaffolds; modules & billing backend later) ----- */
    /* Static sites serve these sections from the generated catalog — the
       cinema/store/plans endpoints only exist on the dynamic backend. */
    listFilms()    { return via("/cinema/programme", () => state.static ? mock().films : request("/cinema/programme"), () => mock().films); },
    listProducts() { return via("/store/products",   () => state.static ? mock().products : request("/store/products"),   () => mock().products); },
    plans()        { return via("/plans",            () => state.static ? mock().plans : request("/plans"),            () => mock().plans); }
  };

  /** Local stand-in for the RAG assistant until the LLM pipeline exists. */
  function mockAssistantAnswer(question) {
    const q = question.toLowerCase();
    const hits = (window.MUSA_MOCK.items || []).filter((i) => i.website_status === "published");
    const find = (...words) => hits.find((i) =>
      words.some((w) => (i.titulo + " " + i.autor + " " + (i.tags || []).join(" ")).toLowerCase().includes(w)));

    let answer, artifact = null;
    if (find("venus", "aphrodite", "milo")) { /* fallthrough below */ }
    if (/(venus|aphrodite|milo)/.test(q)) {
      const it = find("venus", "aphrodite");
      answer = "The Venus de Milo is the centerpiece of our Classical Antiquities collection — a Parian marble Aphrodite from c. 130 BCE, scanned in 3D so you can study her from every angle in the Silver gallery.";
      artifact = it;
    } else if (/(vermeer|pearl|milkmaid)/.test(q)) {
      const it = find("pearl", "milkmaid");
      answer = "Johannes Vermeer is represented by two works in the Old Masters collection: the Girl with a Pearl Earring (c. 1665) and The Milkmaid (c. 1658). Both are on view in the photo gallery below.";
      artifact = it;
    } else if (/(rembrandt|night watch)/.test(q)) {
      answer = "Rembrandt's The Night Watch (1642) anchors the Dutch Golden Age room — 363 × 437 cm of shadow, movement and gilded civic pride. Open its record card for dimensions and materials.";
      artifact = find("night watch");
    } else if (/(3d|model|scan|rotate)/.test(q)) {
      answer = "Pieces with interactive 3D models live in the Silver-tier gallery: Venus de Milo, the antique corset and the samurai helmet. Click any card there to open the WebGL viewer.";
    } else if (/(tour|visit|ticket|hour|open)/.test(q)) {
      answer = "The venue is open Tue–Sun, 10:00–18:00. A guided virtual tour of Room A is available in the Digital Twin section — the full narrated tour ships with the Gold tier.";
    } else if (/(film|cinema|screening|movie)/.test(q)) {
      answer = "This week's art-cinema programme: Metropolis (now showing), The Cabinet of Dr. Caligari and Nosferatu premiering Friday and Saturday. See the Screening Room section for times.";
    } else if (/(ticket|store|buy|shop|souvenir|merch)/.test(q)) {
      answer = "The museum store carries exhibition posters, plaster casts, textiles and catalogues — take a look at the Store section. Online checkout plugs into the commerce module.";
    } else {
      answer = "I can tell you about the collections, the 3D gallery, the digital twin, film screenings, visiting hours and the store. Try: “Which pieces have 3D models?”";
    }
    return {
      answer,
      suggestedArtifacts: artifact ? [{ id: artifact.asset_id, title: artifact.titulo }] : []
    };
  }
})();
