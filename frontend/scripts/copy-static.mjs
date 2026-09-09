// `next build` regenerates .next/standalone from scratch on every run,
// which drops the static assets the standalone server needs (see the
// frontend Dockerfile: the runtime image copies .next/static in as a
// separate step). Running `next start` directly doesn't need this, but
// `node .next/standalone/server.js` does — that's how the prod Docker
// image and scripts/e2e-stack.sh serve the app. Doing the copy as part
// of `npm run build` keeps every invocation self-consistent.
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const staticDir = join(root, ".next", "static");
const standaloneStatic = join(root, ".next", "standalone", ".next", "static");

if (!existsSync(staticDir)) {
  console.error("copy-static: .next/static not found — did `next build` run?");
  process.exit(1);
}
mkdirSync(join(root, ".next", "standalone", ".next"), { recursive: true });
cpSync(staticDir, standaloneStatic, { recursive: true });
console.log("copy-static: synced .next/static into .next/standalone");
