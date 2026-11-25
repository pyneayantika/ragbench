import fs from "node:fs";
import path from "node:path";

const src = path.resolve(process.cwd(), "..", "results", "results.json");
const destDir = path.resolve(process.cwd(), "public");
const dest = path.join(destDir, "results.json");

if (!fs.existsSync(src)) {
  console.error(`Missing source file: ${src}`);
  process.exit(1);
}

fs.mkdirSync(destDir, { recursive: true });
fs.copyFileSync(src, dest);
console.log(`Synced ${src} -> ${dest}`);
