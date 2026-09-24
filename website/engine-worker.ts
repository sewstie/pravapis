import { convertText } from './engine';

self.onmessage = ({ data }) => {
  try {
    self.postMessage({ id: data.id, result: convertText(data.text, data.mode) });
  } catch {
    // Never log input or reflect submitted text in an error.
    self.postMessage({ id: data.id, error: 'engine' });
  }
};
