# Deploying pravapis as `/api/convert` in the Paznaj Next.js app

This is an optional Python integration for other applications. The [Pravapis website](https://pravapis.vercel.app/)
runs the JavaScript package in the browser and deploys as static files. The former
root Python function is retained at `deploy/vercel/standalone/convert.py` for
separate API development and tests.

One Vercel project, one domain: a Python serverless function sits next to the Next.js
app. No separate service, no CORS.

This exporter still vendors raw YAML/TSV sources and builds the `Converter` at cold
start, unlike the optional standalone adapter, which
now loads a single precompiled `data/pravapis-<hash>.bin`. Porting this export to the
same artifact has not been done — it is a real follow-up, not a design choice.

## Build the files

From the pravapis repo:

```bash
python scripts/export_vercel.py /path/to/paznaj          # e.g. E:\coding\project
```

This writes into the Paznaj repo root:

```
paznaj/
├── requirements.txt                 # Python deps for the function (pinned)
└── api/
    ├── convert.py                   # the function → POST /api/convert
    └── _pravapis/                    # vendored; "_" = not a function
        ├── VERSION                  # pravapis commit it was exported from
        ├── pravapis/                 # runtime subset: pipeline, rules, lexicon store, stress
        └── data/
            ├── lexicon.marisa       # compiled from data/lexicon/*.tsv
            ├── rules/*.yaml
            └── stress/              # GrammarDB first-stress tables + CC BY-SA attribution
```

Re-run the export after every pravapis change; do not edit `api/_pravapis/` by hand. The
existing Next.js routes in `src/app/api/` are untouched; Next.js owns `src/app/api/*`,
Vercel's Python runtime owns the root `api/*.py` files.

## Size

| Part | Size |
|---|---|
| `api/convert.py` | 4.8 KB |
| vendored code | 68.7 KB |
| `lexicon.marisa` | 21.2 KB |
| rules YAML | 13.7 KB |
| stress tables | 626.4 KB |
| **payload total** | **734.8 KB** |
| pip deps installed (regex, marisa-trie, PyYAML, pydantic + pydantic-core, manylinux cp312) | 17.7 MB |

Measured on the exported files and on the manylinux wheels unpacked. The 640 KB stress
table fits comfortably; no subset is needed. pydantic (6.8 MB installed) is only there
because `pravapis.config` uses it and could be dropped later if size ever matters.

**Keep the rest of the repo out of the function bundle.** Paznaj's `public/` is 78 MB of
audio. Suggested `vercel.json` (merge with your own config):

```json
{
  "functions": {
    "api/convert.py": {
      "excludeFiles": "{public,src,node_modules,.next,scripts}/**"
    }
  }
}
```

## Contract

`POST /api/convert` with `Content-Type: application/json`:

```json
{ "text": "Снег і свет", "direction": "taraskievica" }
```

- `direction`: `"taraskievica"` (default) or `"narkamauka"`
- `script`: only `"cyrillic"`; `"latin"` (Łacinka) returns 422
- `text`: at most 50,000 characters

`200`:

```json
{ "result": "Сьнег і сьвет", "direction": "taraskievica",
  "stats": { "identity": 0, "lexicon": 0, "rule": 2, "model": 0, "unknown": 1 } }
```

Errors are `{"error": "..."}` with 400 (bad JSON, bad field), 405 (not POST), 413 (too
long), 415 (not JSON), 422 (Łacinka requested). Responses carry `Cache-Control: no-store`.

The converter is built once per cold start (~270 ms locally: imports plus loading the
lexicon, rules and stress tables) and reused by every request on that instance. Warm,
in-process: p50 0.23 ms for a 130-byte sentence, 3.3 ms for a 1.9 KB paragraph (local
Windows desktop; Vercel hardware and network latency not included).

## Switching the client

`src/lib/orthography.js` already posts `{text, script}` and reads `data.result`, so the
switch is the URL:

```js
const response = await fetch("/api/convert", { ... body: JSON.stringify({ text, script }) });
```

Łacinka output (`script: "latin"`) has no pravapis equivalent yet; keep the current route
for that case or hide the option. The current `/api/taraskievica` route scrapes
baltoslav.eu, which should not stay as a data source.

## Local development

`next dev` does not run Python functions. Use `vercel dev` for the whole project, or test
the function alone:

```bash
python -c "import sys; sys.path.insert(0, 'api'); from http.server import HTTPServer; \
from convert import handler; HTTPServer(('127.0.0.1', 5328), handler).serve_forever()"
curl -s localhost:5328 -H 'content-type: application/json' -d '{"text":"снег"}'
```

`tests/test_vercel_export.py` in the pravapis repo exports into a temp dir, serves the real
handler and checks every status code.

## Licence

`api/_pravapis/data/stress/` is derived from GrammarDB (Aleś Bułojčyk, Uładzimir Koščanka),
CC BY-SA 4.0; its README carries the attribution and must ship with it.
