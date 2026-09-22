// Capitalisation patterns: detect one on the input word, re-apply it to the output.
// Mirrors src/pravapis/casing.py.

export type CaseForm = "lower" | "upper" | "title" | "mixed";

const isAlpha = (c: string): boolean => /\p{L}/u.test(c);
const isLower = (c: string): boolean => c === c.toLowerCase() && c !== c.toUpperCase();
const isUpper = (c: string): boolean => c === c.toUpperCase() && c !== c.toLowerCase();

export function detectCase(word: string): CaseForm {
  const letters = [...word].filter(isAlpha);
  if (letters.length === 0) return "lower";
  if (letters.every(isLower)) return "lower";
  if (isUpper(letters[0]!) && letters.slice(1).every(isLower)) return "title";
  if (letters.every(isUpper)) {
    // A single capital letter ("Я", "У") is ambiguous; treat it as title so
    // "У Менску" does not come back as "У МЕНСКУ".
    return letters.length === 1 ? "title" : "upper";
  }
  return "mixed";
}

export function applyCase(word: string, form: CaseForm): string {
  switch (form) {
    case "lower":
      return word;
    case "upper":
      return word.toUpperCase();
    case "title": {
      for (let i = 0; i < word.length; i++) {
        if (isAlpha(word[i]!)) {
          return word.slice(0, i) + word[i]!.toUpperCase() + word.slice(i + 1);
        }
      }
      return word;
    }
    case "mixed":
      return word;
  }
}

/** Give `target` (lowercase) the capitalisation pattern of `source`. */
export function recase(source: string, target: string): string {
  return applyCase(target, detectCase(source));
}
