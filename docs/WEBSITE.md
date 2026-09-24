# Pravapis website

The public site is static HTML and shared CSS. Orthography and script conversion runs
in a module worker, using the pinned published `pravapis` JavaScript package. The
website has no Python runtime, API function, database, or analytics. Submitted text
stays in browser memory. Theme is the only preference written to local storage.

## Run and build

Requires Node.js 18 or newer.

```sh
npm ci --prefix website
npm run dev --prefix website
```

Open <http://127.0.0.1:5329>. Static page sources live in `public/`. `website/engine.ts`
adapts the published package's orthography and transliteration exports; the build
bundles this adapter and its data as `public/assets/engine-worker.js`.

```sh
npm run build --prefix website
```

The build emits static files and Vercel Build Output API v3 configuration into
`.vercel/output/`. Its routing maps `/en/` and `/developers/` to their index files.
Preview deployments receive an `X-Robots-Tag: noindex, nofollow` header; production
deployments remain indexable. The Python Vercel adapter was moved to
`deploy/vercel/standalone/` for optional use in other applications. Vercel builds only
the JavaScript website.

The website pins `pravapis` 0.1.1, verified against the current published package.
It includes the proper-name dictionary. The package omits the Python engine's stress
table, so several context-sensitive `не` / `без` → `ня` / `бяз` forms can differ.
This is documented in the interface and in `js/scripts/known-gaps.json`.

The bilingual feedback form drafts bug reports, incorrect spellings, and proposals.
It copies the report locally and opens GitHub Issues without putting report text in a
URL or sending anything automatically. The reporter reviews and pastes the report;
GitHub issues are public when submitted.

The build includes the code and data license index and the GrammarDB morphology data
attribution under `public/assets/licenses/`. Code is MIT; data carries source-specific
licenses. The social preview can be regenerated with `npm run social --prefix website`
after installing the Playwright browser for the local machine.
