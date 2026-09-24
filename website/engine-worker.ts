// Handles conversion requests in a browser worker. Returns results or a generic error without exposing submitted text in errors or logs.
import { convertText } from './engine';

self.onmessage = ({ data }) => {
  try {
    self.postMessage({ id: data.id, result: convertText(data.text, data.mode) });
  } catch {
    self.postMessage({ id: data.id, error: 'engine' });
  }
};
