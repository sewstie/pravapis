// Mirrors src/pravapis/dataversion.py exactly — same file, same hash function, so the
// hash this build computes and the hash pravapis.dataversion.compute_data_hash()
// computes must agree byte for byte. Deliberately NOT a glob: data/MANIFEST is the one
// place "the data" is enumerated, and reordering or under/over-reading it would change
// the hash without changing a single byte of actual data.

import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";

export interface ManifestEntry {
  /** Path as written in data/MANIFEST, relative to data/. */
  relPath: string;
  /** Resolved absolute path. */
  absPath: string;
}

function parseListing(raw: string): string[] {
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith("#"));
}

export async function readManifest(dataDir: string): Promise<ManifestEntry[]> {
  const raw = await readFile(path.join(dataDir, "MANIFEST"), "utf-8");
  return parseListing(raw).map((relPath) => ({
    relPath,
    absPath: path.join(dataDir, relPath),
  }));
}

export async function readDataVersion(dataDir: string): Promise<string> {
  const raw = await readFile(path.join(dataDir, "VERSION"), "utf-8");
  const line = raw.split(/\r?\n/).find((ln) => ln.trim() && !ln.trim().startsWith("#"));
  const version = line?.trim() ?? "";
  if (!/^\d+\.\d+\.\d+$/.test(version)) {
    throw new Error(`data/VERSION: ${JSON.stringify(version)} is not a semver triple`);
  }
  return version;
}

/** Sha256 over every MANIFEST-listed file's raw bytes, in MANIFEST order — the same
 * computation as pravapis.dataversion.compute_data_hash(). */
export async function computeDataHash(entries: ManifestEntry[]): Promise<string> {
  const digest = createHash("sha256");
  for (const entry of entries) {
    digest.update(await readFile(entry.absPath));
  }
  return digest.digest("hex");
}
