// The engine version every entry point reports. Kept separate so "." and "./names"
// don't need to import from each other just to share a constant — each subpath's
// bundle stays limited to what it actually uses.
export const ENGINE_VERSION = "0.1.0";
