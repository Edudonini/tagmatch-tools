"use client";

// Tab-session persistence for the loaded map and logs.
//
// All bulky payloads (SVG text, spec, report, logs) live in IndexedDB;
// sessionStorage holds only a random session id. Closing the tab kills the id,
// which orphans the IndexedDB records — they are garbage-collected on the next
// app load. If IndexedDB is unavailable, everything degrades to the in-memory
// cache (works, just doesn't survive F5).

export type SpecRow = Record<string, unknown>;
export type LogRow = Record<string, unknown>;
export type Report = Record<string, unknown>;

export type SessionMap = {
  svgText: string;
  fileName: string;
  spec: SpecRow[];
  report: Report;
};

export type SessionLogs = {
  logs: LogRow[];
  report: Report;
  fileNames: string[];
};

export type SessionMeta = {
  map: { fileName: string; eventCount: number } | null;
  logs: { fileCount: number; eventCount: number } | null;
};

type MapRecord = { fileName: string; spec: SpecRow[]; report: Report };

const DB_NAME = "tagmatch-tools";
const STORE_NAME = "session";
const SESSION_ID_KEY = "tagmatch:session-id";
const EMPTY_META: SessionMeta = { map: null, logs: null };

const cache: { map: SessionMap | null; logs: SessionLogs | null } = {
  map: null,
  logs: null,
};
let metaSnapshot: SessionMeta = EMPTY_META;
const listeners = new Set<() => void>();
let hydrationPromise: Promise<void> | null = null;
let dbPromise: Promise<IDBDatabase> | null = null;
let idbAvailable = true;

function sessionId(): string {
  try {
    let id = sessionStorage.getItem(SESSION_ID_KEY);
    if (!id) {
      id = globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
      sessionStorage.setItem(SESSION_ID_KEY, id);
    }
    return id;
  } catch {
    return "memory";
  }
}

function openDb(): Promise<IDBDatabase> {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      if (typeof indexedDB === "undefined") {
        reject(new Error("IndexedDB unavailable"));
        return;
      }
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        if (!req.result.objectStoreNames.contains(STORE_NAME)) {
          req.result.createObjectStore(STORE_NAME);
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error ?? new Error("IndexedDB open failed"));
    });
  }
  return dbPromise;
}

function requestToPromise<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("IndexedDB request failed"));
  });
}

async function idbGet(key: string): Promise<unknown> {
  const db = await openDb();
  return requestToPromise(db.transaction(STORE_NAME).objectStore(STORE_NAME).get(key));
}

async function idbPut(key: string, value: unknown): Promise<void> {
  const db = await openDb();
  await requestToPromise(
    db.transaction(STORE_NAME, "readwrite").objectStore(STORE_NAME).put(value, key)
  );
}

async function idbDelete(keys: string[]): Promise<void> {
  const db = await openDb();
  const store = db.transaction(STORE_NAME, "readwrite").objectStore(STORE_NAME);
  await Promise.all(keys.map((k) => requestToPromise(store.delete(k))));
}

async function idbGcOrphans(currentId: string): Promise<void> {
  const db = await openDb();
  const keys = await requestToPromise(
    db.transaction(STORE_NAME).objectStore(STORE_NAME).getAllKeys()
  );
  const orphans = keys.filter(
    (k): k is string => typeof k === "string" && !k.startsWith(`${currentId}:`)
  );
  if (orphans.length === 0) return;
  const store = db.transaction(STORE_NAME, "readwrite").objectStore(STORE_NAME);
  await Promise.all(orphans.map((k) => requestToPromise(store.delete(k))));
}

function isMapRecord(v: unknown): v is MapRecord {
  if (typeof v !== "object" || v === null) return false;
  const m = v as Record<string, unknown>;
  return (
    typeof m.fileName === "string" &&
    Array.isArray(m.spec) &&
    typeof m.report === "object" &&
    m.report !== null
  );
}

function isSessionLogs(v: unknown): v is SessionLogs {
  if (typeof v !== "object" || v === null) return false;
  const l = v as Record<string, unknown>;
  return (
    Array.isArray(l.logs) &&
    Array.isArray(l.fileNames) &&
    typeof l.report === "object" &&
    l.report !== null
  );
}

function refreshMeta(): void {
  metaSnapshot = {
    map: cache.map
      ? { fileName: cache.map.fileName, eventCount: cache.map.spec.length }
      : null,
    logs: cache.logs
      ? { fileCount: cache.logs.fileNames.length, eventCount: cache.logs.logs.length }
      : null,
  };
  listeners.forEach((l) => l());
}

async function persist(action: () => Promise<void>): Promise<void> {
  if (!idbAvailable) return;
  try {
    await action();
  } catch {
    idbAvailable = false;
  }
}

async function hydrate(): Promise<void> {
  const id = sessionId();
  try {
    await idbGcOrphans(id);
    const [mapRec, svgText, logsRec] = await Promise.all([
      idbGet(`${id}:map`),
      idbGet(`${id}:svg`),
      idbGet(`${id}:logs`),
    ]);
    if (isMapRecord(mapRec) && typeof svgText === "string") {
      cache.map = { ...mapRec, svgText };
    }
    if (isSessionLogs(logsRec)) {
      cache.logs = logsRec;
    }
  } catch {
    idbAvailable = false;
  }
  refreshMeta();
}

export function loadSession(): Promise<{
  map: SessionMap | null;
  logs: SessionLogs | null;
}> {
  if (!hydrationPromise) hydrationPromise = hydrate();
  return hydrationPromise.then(() => ({ map: cache.map, logs: cache.logs }));
}

export async function saveMap(data: SessionMap): Promise<void> {
  await loadSession();
  cache.map = data;
  refreshMeta();
  const id = sessionId();
  await persist(async () => {
    await idbPut(`${id}:svg`, data.svgText);
    await idbPut(`${id}:map`, {
      fileName: data.fileName,
      spec: data.spec,
      report: data.report,
    });
  });
}

export async function updateMapSpec(spec: SpecRow[]): Promise<void> {
  await loadSession();
  if (!cache.map) return;
  cache.map = { ...cache.map, spec };
  refreshMeta();
  const { fileName, report } = cache.map;
  const id = sessionId();
  await persist(() => idbPut(`${id}:map`, { fileName, spec, report }));
}

export async function saveLogs(data: SessionLogs): Promise<void> {
  await loadSession();
  cache.logs = data;
  refreshMeta();
  const id = sessionId();
  await persist(() => idbPut(`${id}:logs`, data));
}

export async function clearMap(): Promise<void> {
  await loadSession();
  cache.map = null;
  refreshMeta();
  const id = sessionId();
  await persist(() => idbDelete([`${id}:map`, `${id}:svg`]));
}

export async function clearLogs(): Promise<void> {
  await loadSession();
  cache.logs = null;
  refreshMeta();
  const id = sessionId();
  await persist(() => idbDelete([`${id}:logs`]));
}

export async function clearAll(): Promise<void> {
  await loadSession();
  cache.map = null;
  cache.logs = null;
  refreshMeta();
  const id = sessionId();
  await persist(() => idbDelete([`${id}:map`, `${id}:svg`, `${id}:logs`]));
}

export function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function getSnapshot(): SessionMeta {
  return metaSnapshot;
}

export function getServerSnapshot(): SessionMeta {
  return EMPTY_META;
}

export function rowsToSpecFile(rows: SpecRow[], name = "spec.json"): File {
  return new File([JSON.stringify(rows)], name, { type: "application/json" });
}

export function logsToFile(logs: LogRow[]): File {
  return new File([JSON.stringify(logs)], "logs.json", { type: "application/json" });
}
