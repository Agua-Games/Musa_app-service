/**
 * MUSA — sample collection catalog (frontend mock data).
 *
 * This data follows the contract in `schemas/ficha.schema.json`
 * (see docs/adr/0001-camada-de-acervo.md). In production it is served
 * by the collection API (`GET /collections`, `GET /collections/{id}/items`,
 * `GET /items/{id}`); while the backend milestone is pending, the frontend
 * API layer (assets/js/api.js) serves this in-memory catalog and exposes the
 * exact same shapes, so no view code changes when the REST backend lands.
 *
 * Website-only presentation fields (image, tier, hero, website_status) are
 * layered on top of the contract fields and managed from the admin browser.
 */
window.MUSA_MOCK = {

  museum: {
    id: "musa-demo",
    name: "MUSA Atelier Museum",
    tagline: "A demo venue running on the MUSA app-service",
    tier: "gold"
  },

  collections: [
    {
      id: "old-masters",
      title: "Old Masters",
      description: "Dutch and Flemish painting of the Golden Age, alongside French Impressionism.",
      cover: "assets/img/art-night-watch.jpg",
      tier: "bronze",
      subcollections: [
        { id: "dutch-golden-age", title: "Dutch Golden Age" },
        { id: "impressionism", title: "Impressionism" }
      ]
    },
    {
      id: "classical-antiquities",
      title: "Classical Antiquities",
      description: "Sculpture and vessels from ancient Egypt, Greece and Rome.",
      cover: "assets/img/art-venus.jpg",
      tier: "silver",
      subcollections: [
        { id: "egypt", title: "Egypt" },
        { id: "greece", title: "Greece" }
      ]
    },
    {
      id: "decorative-arts",
      title: "Decorative Arts & Armor",
      description: "Fashion, light and steel — the applied arts collection.",
      cover: "assets/img/art-corset.jpg",
      tier: "silver",
      subcollections: [
        { id: "fashion", title: "Fashion" },
        { id: "arms-armor", title: "Arms & Armor" }
      ]
    },
    {
      id: "gallery-rooms",
      title: "Permanent Galleries (Digital Twin)",
      description: "Rooms of the venue, mirrored online as an explorable digital twin.",
      cover: "assets/img/twin-wall.jpg",
      tier: "gold",
      subcollections: [
        { id: "room-a", title: "Room A — Northern Masters" }
      ]
    }
  ],

  items: [
    {
      asset_id: "OA-001",
      titulo: "Girl with a Pearl Earring",
      autor: "Johannes Vermeer",
      data: "1665",
      material: "Oil on canvas",
      dimensoes: "44.5 × 39 cm",
      descricao: "A tronie — a study of a girl in exotic dress, turned over her shoulder toward the viewer. The pearl is painted with two strokes of lead white.",
      colecao: "old-masters",
      subcolecao: "dutch-golden-age",
      tags: ["painting", "dutch", "golden-age", "portrait"],
      image: "assets/img/art-pearl-earring.jpg",
      tier: "bronze",
      hero: true,
      website_status: "published",
      model_status: "unavailable",
      featured_on: ["bronze-gallery"]
    },
    {
      asset_id: "OA-002",
      titulo: "The Milkmaid",
      autor: "Johannes Vermeer",
      data: "1658",
      material: "Oil on canvas",
      dimensoes: "45.5 × 41 cm",
      descricao: "A kitchen maid pouring milk, rendered with Vermeer's signature northern light and quiet geometry.",
      colecao: "old-masters",
      subcolecao: "dutch-golden-age",
      tags: ["painting", "dutch", "genre"],
      image: "assets/img/art-milkmaid.jpg",
      tier: "bronze",
      hero: false,
      website_status: "published",
      model_status: "unavailable",
      featured_on: ["bronze-gallery"]
    },
    {
      asset_id: "OA-003",
      titulo: "The Night Watch",
      autor: "Rembrandt van Rijn",
      data: "1642",
      material: "Oil on canvas",
      dimensoes: "363 × 437 cm",
      descricao: "Rembrandt's monumental civic guard portrait — movement, shadow and gilded light at civic scale.",
      colecao: "old-masters",
      subcolecao: "dutch-golden-age",
      tags: ["painting", "dutch", "baroque"],
      image: "assets/img/art-night-watch.jpg",
      tier: "bronze",
      hero: true,
      website_status: "published",
      model_status: "unavailable",
      featured_on: ["bronze-gallery"]
    },
    {
      asset_id: "OA-004",
      titulo: "Water Lilies",
      autor: "Claude Monet",
      data: "1906",
      material: "Oil on canvas",
      dimensoes: "89.9 × 94.1 cm",
      descricao: "One panel of Monet's obsessive, decades-long meditation on his garden pond at Giverny.",
      colecao: "old-masters",
      subcolecao: "impressionism",
      tags: ["painting", "french", "impressionism"],
      image: "assets/img/art-water-lilies.jpg",
      tier: "bronze",
      hero: false,
      website_status: "published",
      model_status: "unavailable",
      featured_on: ["bronze-gallery"]
    },
    {
      asset_id: "OA-005",
      titulo: "Self-Portrait",
      autor: "Vincent van Gogh",
      data: "1889",
      material: "Oil on canvas",
      dimensoes: "65 × 54 cm",
      descricao: "Painted in Saint-Rémy-de-Provence while the artist was a patient at the asylum — swirling ultramarine and violet.",
      colecao: "old-masters",
      subcolecao: "impressionism",
      tags: ["painting", "dutch", "post-impressionism", "portrait"],
      image: "assets/img/art-vangogh-self.jpg",
      tier: "bronze",
      hero: false,
      website_status: "published",
      model_status: "unavailable",
      featured_on: ["bronze-gallery"]
    },

    {
      asset_id: "AN-001",
      titulo: "Venus de Milo",
      autor: "Alexandros of Antioch (attrib.)",
      data: "-130",
      material: "Parian marble",
      dimensoes: "204 cm",
      descricao: "Hellenistic marble statue of Aphrodite, discovered on Milos in 1820. This 3D scan was published CC0 by the National Gallery of Denmark (SMK) via the Sketchfab cultural-heritage programme.",
      colecao: "classical-antiquities",
      subcolecao: "greece",
      tags: ["sculpture", "greek", "hellenistic", "3d"],
      image: "assets/img/art-venus.jpg",
      tier: "silver",
      hero: true,
      website_status: "published",
      model_primary: "assets/models/venus-de-milo.glb",
      model_source: "https://sketchfab.com/3d-models/venus-de-milo-statuestexturingchallenge-smk-2983d92ac4e744f485492580ca7629f2",
      model_formats: ["glb"],
      model_viewer: "three_js",
      model_status: "available",
      featured_on: ["silver-gallery"]
    },
    {
      asset_id: "AN-002",
      titulo: "Black-figure Amphora",
      autor: "Unknown (Attic workshop)",
      data: "-540",
      material: "Terracotta, black-figure",
      dimensoes: "42 × 26 cm",
      descricao: "Storage amphora with black-figure panels. Photogrammetry scheduled — 3D pipeline in progress.",
      colecao: "classical-antiquities",
      subcolecao: "greece",
      tags: ["ceramics", "greek", "archaic"],
      image: "assets/img/art-greek-amphora.jpg",
      tier: "silver",
      hero: false,
      website_status: "published",
      model_status: "processing",
      featured_on: ["silver-gallery"]
    },
    {
      asset_id: "AN-003",
      titulo: "Statue of the Goddess Taweret",
      autor: "Unknown",
      data: "-1400",
      material: "Greywacke",
      dimensoes: "74 cm",
      descricao: "The hippo-headed household goddess Taweret, protector of mothers and children. Historic archive photograph, Cairo Museum.",
      colecao: "classical-antiquities",
      subcolecao: "egypt",
      tags: ["sculpture", "egypt", "new-kingdom"],
      image: "assets/img/art-egyptian-statue.jpg",
      tier: "silver",
      hero: false,
      website_status: "published",
      model_status: "unavailable",
      featured_on: ["silver-gallery"]
    },
    {
      asset_id: "AN-004",
      titulo: "Bust of Nefertiti",
      autor: "Thutmose (workshop, attrib.)",
      data: "-1345",
      material: "Painted limestone, stucco",
      dimensoes: "47 cm",
      descricao: "The iconic painted limestone bust of queen Nefertiti, Amarna period. Photography of the original is subject to museum policy; shown here as a study image.",
      colecao: "classical-antiquities",
      subcolecao: "egypt",
      tags: ["sculpture", "egypt", "amarna"],
      image: "assets/img/art-nefertiti.jpg",
      tier: "silver",
      hero: true,
      website_status: "published",
      model_status: "unavailable",
      featured_on: ["silver-gallery"]
    },

    {
      asset_id: "DA-001",
      titulo: "Antique Corset",
      autor: "Atelier Cécile (demo attribution)",
      data: "1880",
      material: "Silk, whalebone, metal",
      dimensoes: "58 × 42 cm",
      descricao: "Structured evening corset demonstrating 19th-century couture construction. Interactive 3D study model.",
      colecao: "decorative-arts",
      subcolecao: "fashion",
      tags: ["fashion", "textile", "19th-century", "3d"],
      image: "assets/img/art-corset.jpg",
      tier: "silver",
      hero: false,
      website_status: "published",
      model_primary: "assets/models/antique-corset.glb",
      model_formats: ["glb"],
      model_viewer: "three_js",
      model_status: "available",
      featured_on: ["silver-gallery"]
    },
    {
      asset_id: "DA-002",
      titulo: "Samurai Helmet (Kabuto)",
      autor: "Unknown armorer",
      data: "1600",
      material: "Lacquered iron, silk",
      dimensoes: "38 × 30 cm",
      descricao: "Battle-worn kabuto with crest. Surface study model with full PBR texture set.",
      colecao: "decorative-arts",
      subcolecao: "arms-armor",
      tags: ["armor", "japan", "edo", "3d"],
      image: "assets/img/art-helmet.jpg",
      tier: "silver",
      hero: false,
      website_status: "published",
      model_primary: "assets/models/samurai-helmet.glb",
      model_formats: ["glb"],
      model_viewer: "three_js",
      model_status: "available",
      featured_on: ["silver-gallery"]
    },
    {
      asset_id: "DA-003",
      titulo: "Edo-period Lantern",
      autor: "Unknown",
      data: "1750",
      material: "Iron, washi, lacquer",
      dimensoes: "52 × 28 cm",
      descricao: "Travel lantern with internal candle mount. Rendered via Omniverse Kit App streaming in production — shown as a stream placeholder in this scaffold.",
      colecao: "decorative-arts",
      subcolecao: "arms-armor",
      tags: ["object", "japan", "edo", "3d"],
      image: "assets/img/art-lantern.jpg",
      tier: "silver",
      hero: false,
      website_status: "published",
      model_primary: "assets/models/lantern.glb",
      model_formats: ["glb", "usd"],
      model_viewer: "kit_stream",
      model_status: "available",
      featured_on: ["silver-gallery"]
    },

    {
      asset_id: "GR-001",
      titulo: "Room A — Northern Masters (Digital Twin)",
      autor: "MUSA digital twin pipeline",
      data: "2026",
      material: "WebGL scene",
      dimensoes: "12 × 8 m",
      descricao: "Explorable digital twin of the venue's main gallery, with framed works and sculpture pedestals.",
      colecao: "gallery-rooms",
      subcolecao: "room-a",
      tags: ["digital-twin", "room", "webgl"],
      image: "assets/img/twin-wall.jpg",
      tier: "gold",
      hero: true,
      website_status: "published",
      model_primary: "twin:room-a",
      model_formats: ["glb"],
      model_viewer: "three_js",
      model_status: "available",
      featured_on: ["digital-twin"]
    },

    {
      asset_id: "ARC-001",
      titulo: "Attic Red-figure Kylix",
      autor: "Onesimos (circle, attrib.)",
      data: "-490",
      material: "Terracotta, red-figure",
      dimensoes: "32 cm Ø",
      descricao: "Drinking cup attributed to the circle of Onesimos. Not yet published to the website — visible in the admin browser only.",
      colecao: "classical-antiquities",
      subcolecao: "greece",
      tags: ["ceramics", "greek", "archaic"],
      image: "assets/img/art-greek-amphora.jpg",
      tier: "bronze",
      hero: false,
      website_status: "draft",
      model_status: "unavailable",
      featured_on: []
    }
  ],

  /* ------------------------------------------------------------------ */
  /* Film programme — served by the streaming module in production.      */
  /* ------------------------------------------------------------------ */
  films: [
    {
      id: "f-metropolis",
      title: "Metropolis",
      director: "Fritz Lang",
      year: "1927",
      duration: "2h 33m",
      synopsis: "The silent-era cornerstone of science-fiction cinema — a dystopia of workers, machines and catacombs.",
      poster: "assets/img/film-metropolis.jpg",
      status: "now-showing",
      sources: { "1080p": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                 "720p":  "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4" }
    },
    {
      id: "f-nosferatu",
      title: "Nosferatu — A Symphony of Horror",
      director: "F. W. Murnau",
      year: "1922",
      duration: "1h 34m",
      synopsis: "The unauthorised Dracula adaptation that defined screen vampires and German Expressionist shadow.",
      poster: "assets/img/film-nosferatu.jpg",
      status: "upcoming",
      premiere: "Fri 20:00 — Restoration DCP",
      sources: { "1080p": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4" }
    },
    {
      id: "f-modern-times",
      title: "Modern Times",
      director: "Charlie Chaplin",
      year: "1936",
      duration: "1h 27m",
      synopsis: "Chaplin's tramp versus the assembly line — a farewell to silence and a satire of industrial modernity.",
      poster: "assets/img/film-modern-times.jpg",
      status: "upcoming",
      premiere: "Sat 18:00 — 35mm print",
      sources: { "1080p": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4" }
    }
  ],

  /* ------------------------------------------------------------------ */
  /* Store — scaffolding catalog; plugs into the commerce service later. */
  /* ------------------------------------------------------------------ */
  products: [
    { id: "p-01", name: "Night Watch — Exhibition Poster", price: 89,  image: "assets/img/art-night-watch.jpg", tag: "Prints", stock: 42 },
    { id: "p-02", name: "Pearl Earring — Fine Art Print", price: 129, image: "assets/img/art-pearl-earring.jpg", tag: "Prints", stock: 30 },
    { id: "p-03", name: "Venus de Milo — Plaster Cast, 24 cm", price: 349, image: "assets/img/art-venus.jpg", tag: "Sculpture", stock: 12 },
    { id: "p-04", name: "MUSA Cotton Tote — Water Lilies", price: 79,  image: "assets/img/art-water-lilies.jpg", tag: "Merchandise", stock: 120 },
    { id: "p-05", name: "Gallery Mug — Van Gogh Self-Portrait", price: 59, image: "assets/img/art-vangogh-self.jpg", tag: "Merchandise", stock: 85 },
    { id: "p-06", name: "Amphora Silk Scarf", price: 189, image: "assets/img/art-greek-amphora.jpg", tag: "Textile", stock: 25 },
    { id: "p-07", name: "Golden Age Exhibition Catalogue", price: 149, image: "assets/img/art-milkmaid.jpg", tag: "Books", stock: 60 },
    { id: "p-08", name: "Nefertiti Enamel Pin Set", price: 45,  image: "assets/img/art-nefertiti.jpg", tag: "Merchandise", stock: 200 }
  ],

  /* ------------------------------------------------------------------ */
  /* Plans & modules — mirrors docs/Musa_design document_v1.0.md §Pricing */
  /* Prices in BRL (R$).                                                 */
  /* ------------------------------------------------------------------ */
  plans: {
    tiers: [
      {
        id: "bronze", name: "Bronze", title: "Digital Museum", price: 597,
        blurb: "A complete online home for your collection.",
        features: ["Full responsive venue website", "2D catalog with high-quality photos", "Search & filters by collection / period", "Technical record cards per item", "Cloud backup", "Owner admin panel"]
      },
      {
        id: "silver", name: "Silver", title: "Interactive Museum", price: 1197,
        blurb: "Your hero pieces, in the round.",
        features: ["Everything in Bronze", "Up to 50 hero pieces on rotation", "Interactive 3D models (WebGL)", "Exploded-view study mode", "AR on visitors' phones", "Thematic virtual galleries", "Automatic OCR import of new items"], popular: true
      },
      {
        id: "gold", name: "Gold", title: "Immersive Museum", price: 3197,
        blurb: "The whole venue, mirrored online.",
        features: ["Everything in Silver", "Full digital twin of the venue", "Every piece modeled in 3D", "Narrated guided virtual tour", "Immersive room scenes", "On-site interactive displays synced", "Permanent data export for archiving"]
      }
    ],
    modules: [
      { id: "m-assistant", name: "Virtual AI Assistant", price: 249, unit: "/mo",
        desc: "Conversational guide answering visitor questions about the collection, on site and online." },
      { id: "m-displays", name: "On-location Interactive Displays", price: 300, unit: "/mo",
        desc: "Sync with kiosks and touchscreens inside the venue (pairing & content push)." },
      { id: "m-streaming", name: "Art-Cinema Streaming", price: 400, unit: "/mo",
        desc: "Online screening room with scheduled programmes, playlists and DRM-ready delivery." },
      { id: "m-twin-items", name: "Digital Twin — Additional Items", price: 90, unit: "/item/mo",
        desc: "Extend the twin with new modeled pieces, added to rooms on demand." },
      { id: "m-twin-areas", name: "Digital Twin — Additional Areas", price: 650, unit: "/area/mo",
        desc: "Scan and publish extra rooms, wings or outdoor areas of the venue." },
      { id: "m-store", name: "Integrated Web Store", price: 180, unit: "/mo",
        desc: "Sell tickets, prints and merchandising with the venue's own branding." },
      { id: "m-api", name: "Data Export API", price: 400, unit: "/mo",
        desc: "REST/GraphQL export of records for archival and third-party systems (OAI-PMH ready)." },
      { id: "m-multilingual", name: "Multilingual Visitor Layer", price: 150, unit: "/mo",
        desc: "Interface and assistant answers in up to 8 languages for international audiences." }
    ]
  },

  /* ------------------------------------------------------------------ */
  /* Gallery-wall hotspots — clickable areas over the room backdrop      */
  /* photo (percent coordinates). Each area reveals one or more records. */
  /* Served by /collections/{id}/items in production.                    */
  /* ------------------------------------------------------------------ */
  wallHotspots: [
    { id: "wall-west-1", x: 7,  y: 50, label: "West wall · Portraits",      items: ["OA-001", "OA-002"] },
    { id: "wall-center", x: 54, y: 49, label: "Center hang · Golden Age",   items: ["OA-003", "OA-004", "OA-005"] },
    { id: "wall-east",   x: 80, y: 47, label: "East wall · Color studies",  items: ["AN-004", "DA-001"] },
    { id: "wall-plinth", x: 92, y: 50, label: "Plinth · Sculpture in 3D",   items: ["AN-001"] }
  ],

  /* Demo identities for the login panel (two admin tiers). */
  accounts: [
    { email: "owner@musa.demo", password: "demo", role: "client", name: "Helena Duarte", org: "MUSA Atelier Museum",
      note: "Tier: client admin — the museum owner. Manages own collections, hero pieces and website visibility." },
    { email: "team@musa.demo", password: "demo", role: "musa", name: "MUSA Operations", org: "MUSA team",
      note: "Tier: Musa team member. Cross-venue oversight, modules, billing and pipeline status." }
  ]
};
