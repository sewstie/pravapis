# Pravapis website

The public pages are static HTML and shared CSS. Orthography and script conversion
runs in a module worker, using the pinned published `pravapis` JavaScript package.
Converter text stays in browser memory. The separate feedback form sends only its
own fields to a Vercel Function, which appends them to a private Google Sheet.
Theme is the only preference written to local storage.

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

The build emits static files, a Node.js feedback function, and Vercel Build Output
API v3 configuration into `.vercel/output/`. Its routing maps `/en/` and
`/developers/` to their index files and `/api/feedback` to the private function.
Preview deployments receive an `X-Robots-Tag: noindex, nofollow` header; production
deployments remain indexable. The Python Vercel adapter was moved to
`deploy/vercel/standalone/` for optional use in other applications.

The website pins `pravapis` 0.1.1, verified against the current published package.
It includes the proper-name dictionary. That pinned release omits the Python engine's
stress table, so several context-sensitive `не` / `без` → `ня` / `бяз` forms can differ,
as documented in the interface. The current local `js/` source includes compact
GrammarDB stress tables and has no conformance gaps; the website will receive that
behavior when its package dependency and browser bundle are updated.

## Private feedback sheet

The bilingual form sends a bug report, spelling report, or proposal when the visitor
presses **Send feedback**. It sends the report type, summary, optional spelling pair,
details, and page path to `/api/feedback`. The converter input is never read by the
form. A successful append clears the form; a failed request keeps the text for retry.
The server limits body and field sizes and writes the report as literal cells using
the Google Sheets API's `RAW` input option.

To activate it for a new sheet:

1. Create a private Google Sheet in your account with a tab named `Feedback`.
   Put these seven headers in row 1: `Received (UTC)`, `Type`, `Summary`,
   `Original`, `Suggestion`, `Details`, `Page`.
2. In a [Google Cloud project](https://console.cloud.google.com/), enable the
   [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com).
   Create a service account and download a JSON private key. Share **only this sheet**
   with the service account's `client_email` as an Editor; do not make it public.
3. In the Vercel project settings, add `FEEDBACK_SHEET_ID` (the ID between `/d/` and
   `/edit` in the sheet URL) and `FEEDBACK_GOOGLE_SERVICE_ACCOUNT_JSON` (the full
   service account JSON) to the **Preview** and **Production** environments. Keep the
   JSON out of Git and browser code. Redeploy after adding the values; Vercel applies
   environment changes to new deployments. A missing configuration returns HTTP 503
   and the form keeps the visitor's text.
4. Submit a short test report from the preview URL and check that exactly one row
   appears. The page only displays success after Google confirms one appended row.

The function authenticates with a signed service-account assertion and asks only for
the Sheets scope. [Google's service-account guide](https://developers.google.com/identity/protocols/oauth2/service-account)
describes that exchange, and the [append API](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append)
defines the row operation. The sheet and key must be supplied by the site owner; the
repository contains no Google credentials.

The build includes the code and data license index and the GrammarDB morphology data
attribution under `public/assets/licenses/`. Code is MIT; data carries source-specific
licenses. The social preview can be regenerated with `npm run social --prefix website`
after installing the Playwright browser for the local machine.
