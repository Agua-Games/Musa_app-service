/**
 * MUSA — zero-dependency static dev server.
 * Forwards --host / --port (or -H / -p) CLI arguments, e.g.:
 *   npm run dev -- --host 127.0.0.1 --port 7100
 */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL(".", import.meta.url));

const args = process.argv.slice(2);
const arg = (names, dflt) => {
  for (const n of names) {
    const i = args.indexOf(n);
    if (i !== -1 && args[i + 1]) return args[i + 1];
  }
  return dflt;
};
const HOST = arg(["--host", "-H"], "0.0.0.0");
const PORT = Number(arg(["--port", "-p"], 7100));

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
  ".svg": "image/svg+xml", ".webp": "image/webp",
  ".glb": "model/gltf-binary", ".gltf": "model/gltf+json",
  ".mp4": "video/mp4", ".webm": "video/webm", ".ico": "image/x-icon",
};

const server = createServer(async (req, res) => {
  try {
    let path = decodeURIComponent(new URL(req.url, "http://x").pathname);
    if (path.endsWith("/")) path += "index.html";
    const file = normalize(join(ROOT, path));
    if (!file.startsWith(normalize(ROOT))) { res.writeHead(403); return res.end(); }
    const body = await readFile(file);
    res.writeHead(200, {
      "Content-Type": MIME[extname(file).toLowerCase()] || "application/octet-stream",
      "Cache-Control": "no-cache",
    });
    res.end(body);
  } catch {
    res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    res.end("404 — not found");
  }
});

server.listen(PORT, HOST, () => {
  console.log(`MUSA frontend dev server → http://${HOST}:${PORT}/`);
});
