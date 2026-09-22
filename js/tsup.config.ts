import { defineConfig } from "tsup";

export default defineConfig({
  entry: {
    index: "src/index.ts",
    translit: "src/translit.ts",
    names: "src/names.ts",
  },
  format: ["esm", "cjs"],
  dts: true,
  splitting: false,
  sourcemap: false,
  clean: true,
  target: "es2022",
  outDir: "dist",
  // core.json/names.json/translit.json/chars.json are JSON *modules*, imported with
  // `with { type: "json" }` — esbuild inlines them into the bundle at build time, so
  // dist/ ships plain JS with the data baked in, not a runtime fetch/read of the
  // generated/ files (which stay gitignored and dev-only).
});
