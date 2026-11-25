import fs from "node:fs";
import path from "node:path";
import type { BenchmarkResults } from "./types";

export function loadResults(): BenchmarkResults {
  const filePath = path.join(process.cwd(), "public", "results.json");
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing ${filePath}. Run npm run sync-results first.`);
  }
  const raw = fs.readFileSync(filePath, "utf8");
  return JSON.parse(raw) as BenchmarkResults;
}
