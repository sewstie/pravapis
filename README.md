# pravapis

Converts Belarusian text between **Narkamaŭka** (the standard spelling) and
**Taraškievica** (the pre-1933 spelling, still used today by some diaspora media and
independent publishers), and transliterates between Cyrillic and the Łacinka Latin
script. Available as a Python package, an npm package, and a browser-based website.

```
Снег і план сістэмы → Сьнег і плян сыстэмы
```

## Install

```bash
npm install pravapis
```

```bash
pip install pravapis
```

## Usage

```js
import { convert } from "pravapis";

const result = convert("Снег і план сістэмы", { to: "taraskievica" });
console.log(result.text); // "Сьнег і плян сыстэмы"
```

```python
from pravapis import convert

result = convert("Снег і план сістэмы", {"to": "taraskievica"})
print(result.text)  # "Сьнег і плян сыстэмы"
```

## How accurate is it?

On held-out text, pravapis makes about three in four of the changes it should (74.5%
recall) and is right 96% of the time it does act (precision), on the direction it's
tested most. See [docs/ACCURACY.md](docs/ACCURACY.md) for the full breakdown —
per-alternation numbers, confidence intervals, and what's still missing.

## How it works

pravapis checks each word against a dictionary of known exceptions and loanwords
first, then against a set of hand-written spelling rules — each one citing the exact
section of the 2005 spelling codification it implements — and leaves a word alone if
neither has an answer for it. A separate small list marks which word-stems are foreign
borrowings, because Belarusian's spelling rules for borrowed words don't apply to
native words that merely look similar. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for the full design.

## Learn more

- [Website development](docs/WEBSITE.md) — the bilingual static site, JavaScript worker, and Vercel build

- [Full API reference](docs/API.md) — the response contract, the Python library, the CLI, the HTTP API
- [docs/ACCURACY.md](docs/ACCURACY.md) — recall, precision, and known gaps, measured
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — how the converter, the data, and the npm port are built
- [CONTRIBUTING.md](CONTRIBUTING.md) — dev setup, growing the lexicon, running the test suite
- [LICENSE](LICENSE)

## License

MIT for the code ([LICENSE](LICENSE)). The data under `data/` has its own split by
source, documented in [data/LICENSE](data/LICENSE).