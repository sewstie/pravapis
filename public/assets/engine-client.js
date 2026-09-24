// A worker keeps conversion off the main thread. No submitted text leaves the browser.
export function createEngineClient() {
  let worker = null, pending = null, sequence = 0;
  function cancel() {
    if (pending) {
      const { reject } = pending;
      pending = null;
      worker?.terminate();
      worker = null;
      reject(new DOMException('Cancelled', 'AbortError'));
    }
  }
  function dispose() {
    cancel();
    worker?.terminate();
    worker = null;
  }
  function run(text, mode) {
    cancel();
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      try {
        if (!worker) {
          worker = new Worker(new URL('./engine-worker.js', import.meta.url), { type: 'module' });
          worker.onmessage = ({ data }) => {
            if (!pending || data.id !== pending.id) return;
            const task = pending;
            pending = null;
            if (data.error || typeof data.result?.text !== 'string') task.reject(new Error('engine'));
            else task.resolve(data.result);
          };
          worker.onerror = event => {
            event.preventDefault();
            const task = pending;
            pending = null;
            worker?.terminate();
            worker = null;
            task?.reject(new Error('engine'));
          };
        }
        pending = { id, resolve, reject };
        worker.postMessage({ id, text, mode });
      } catch {
        pending = null;
        worker?.terminate();
        worker = null;
        reject(new Error('engine'));
      }
    });
  }
  return { run, cancel, dispose };
}
