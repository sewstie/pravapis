// Converts orthography and transliterates text with the published Pravapis package. Returns word-level change data only for Cyrillic results.
import { convert } from 'pravapis/names';
import { transliterate } from 'pravapis/translit';

export function convertText(text: string, mode: string) {
  if (typeof text !== 'string' || Array.from(text).length > 50000) throw new Error('limit');
  if (mode === 'unchanged') return { text, changes: [] };
  if (mode === 'narkamauka-latin') return { text: transliterate(convert(text, { to: 'narkamauka' }).text, 'lacinka') };
  if (mode === 'taraskievica' || mode === 'narkamauka') return convert(text, { to: mode });
  if (!['lacinka', 'official', 'lacinka-only', 'official-only'].includes(mode)) throw new Error('mode');
  const script = mode.startsWith('lacinka') ? 'lacinka' : 'official';
  const direction = script === 'lacinka' ? 'taraskievica' : 'narkamauka';
  const source = mode.endsWith('-only') ? text : convert(text, { to: direction }).text;
  const engineScript = script === 'official' ? 'official2007' : script;
  return { text: transliterate(source, engineScript), script, direction: mode.endsWith('-only') ? null : direction };
}
