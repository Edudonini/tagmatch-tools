import { beforeEach, describe, expect, it, vi } from "vitest";
import { IDBFactory } from "fake-indexeddb";

type Store = typeof import("./sessionStore");

const MAP = {
  svgText: "<svg viewBox=\"0 0 10 10\"><rect/></svg>",
  fileName: "jornada_fatura.svg",
  spec: [
    { name: "screen_view", sn: "/app/home", event_order: 1 },
    { name: "interaction", sn: "/app/home", event_order: 2 },
  ],
  report: { screens: 1 },
};

const LOGS = {
  logs: [{ name_norm: "screen_view" }, { name_norm: "click" }, { name_norm: "view" }],
  report: { files: [] },
  fileNames: ["a.log", "b.log"],
};

async function freshStore(): Promise<Store> {
  vi.resetModules();
  return import("./sessionStore");
}

beforeEach(() => {
  globalThis.indexedDB = new IDBFactory();
  sessionStorage.clear();
});

describe("sessionStore", () => {
  it("starts empty", async () => {
    const store = await freshStore();
    expect(await store.loadSession()).toEqual({ map: null, logs: null });
    expect(store.getSnapshot()).toEqual({ map: null, logs: null });
  });

  it("round-trips a saved map across a reload (same tab)", async () => {
    const store = await freshStore();
    await store.saveMap(MAP);
    // F5: module state is gone, sessionStorage id + IndexedDB survive.
    const store2 = await freshStore();
    const { map } = await store2.loadSession();
    expect(map).toEqual(MAP);
    expect(store2.getSnapshot().map).toEqual({
      fileName: "jornada_fatura.svg",
      eventCount: 2,
    });
  });

  it("updateMapSpec overwrites the spec and persists it", async () => {
    const store = await freshStore();
    await store.saveMap(MAP);
    const edited = [{ name: "screen_view", sn: "/app/home", event_order: 1 }];
    await store.updateMapSpec(edited);
    const store2 = await freshStore();
    const { map } = await store2.loadSession();
    expect(map?.spec).toEqual(edited);
    expect(map?.svgText).toBe(MAP.svgText);
    expect(store2.getSnapshot().map?.eventCount).toBe(1);
  });

  it("updateMapSpec without a loaded map is a no-op", async () => {
    const store = await freshStore();
    await store.updateMapSpec([{ name: "x" }]);
    expect((await store.loadSession()).map).toBeNull();
  });

  it("round-trips saved logs and exposes meta", async () => {
    const store = await freshStore();
    await store.saveLogs(LOGS);
    const store2 = await freshStore();
    expect((await store2.loadSession()).logs).toEqual(LOGS);
    expect(store2.getSnapshot().logs).toEqual({ fileCount: 2, eventCount: 3 });
  });

  it("clearMap removes only the map; clearLogs removes only the logs", async () => {
    const store = await freshStore();
    await store.saveMap(MAP);
    await store.saveLogs(LOGS);
    await store.clearMap();
    expect(store.getSnapshot()).toEqual({
      map: null,
      logs: { fileCount: 2, eventCount: 3 },
    });
    await store.clearLogs();
    expect(store.getSnapshot()).toEqual({ map: null, logs: null });
    // both cleared from disk too
    const store2 = await freshStore();
    expect(await store2.loadSession()).toEqual({ map: null, logs: null });
  });

  it("clearAll removes everything", async () => {
    const store = await freshStore();
    await store.saveMap(MAP);
    await store.saveLogs(LOGS);
    await store.clearAll();
    const store2 = await freshStore();
    expect(await store2.loadSession()).toEqual({ map: null, logs: null });
  });

  it("keeps fresh records from other (possibly live) tabs", async () => {
    const store = await freshStore();
    await store.saveMap(MAP);
    const oldId = sessionStorage.getItem("tagmatch:session-id");
    expect(oldId).toBeTruthy();

    // New tab: fresh session id, same IndexedDB. It must NOT wipe the
    // first tab's fresh records — two open tabs are independent sessions.
    sessionStorage.clear();
    const store2 = await freshStore();
    expect((await store2.loadSession()).map).toBeNull();

    // The first tab's records survived: going back to the old id still loads the map.
    sessionStorage.setItem("tagmatch:session-id", oldId!);
    const store3 = await freshStore();
    expect((await store3.loadSession()).map).toEqual(MAP);
  });

  it("garbage-collects stale records from closed sessions", async () => {
    const store = await freshStore();
    // Plant a stale record under a foreign session id directly via raw IndexedDB.
    await new Promise<void>((resolve, reject) => {
      const req = indexedDB.open("tagmatch-tools", 1);
      req.onupgradeneeded = () => {
        req.result.createObjectStore("session");
      };
      req.onsuccess = () => {
        const put = req.result
          .transaction("session", "readwrite")
          .objectStore("session")
          .put(
            {
              t: Date.now() - 25 * 60 * 60 * 1000,
              v: { fileName: "old.svg", spec: [], report: {} },
            },
            "dead-session:map"
          );
        put.onsuccess = () => {
          req.result.close();
          resolve();
        };
        put.onerror = () => reject(put.error);
      };
      req.onerror = () => reject(req.error);
    });

    // Hydrating under the current session id garbage-collects the stale record.
    await store.loadSession();
    const keys = await new Promise<IDBValidKey[]>((resolve, reject) => {
      const req = indexedDB.open("tagmatch-tools", 1);
      req.onsuccess = () => {
        const get = req.result
          .transaction("session")
          .objectStore("session")
          .getAllKeys();
        get.onsuccess = () => {
          req.result.close();
          resolve(get.result);
        };
        get.onerror = () => reject(get.error);
      };
      req.onerror = () => reject(req.error);
    });
    expect(keys).not.toContain("dead-session:map");
  });

  it("treats corrupt records as an empty session", async () => {
    const store = await freshStore();
    await store.saveMap(MAP);
    const id = sessionStorage.getItem("tagmatch:session-id")!;
    // Corrupt the map record directly.
    await new Promise<void>((resolve, reject) => {
      const req = indexedDB.open("tagmatch-tools", 1);
      req.onsuccess = () => {
        const put = req.result
          .transaction("session", "readwrite")
          .objectStore("session")
          .put("not-an-object", `${id}:map`);
        put.onsuccess = () => resolve();
        put.onerror = () => reject(put.error);
      };
      req.onerror = () => reject(req.error);
    });
    const store2 = await freshStore();
    expect((await store2.loadSession()).map).toBeNull();
  });

  it("notifies subscribers on every mutation", async () => {
    const store = await freshStore();
    const cb = vi.fn();
    store.subscribe(cb);
    await store.saveMap(MAP);
    expect(cb).toHaveBeenCalled();
    const calls = cb.mock.calls.length;
    await store.clearMap();
    expect(cb.mock.calls.length).toBeGreaterThan(calls);
  });

  it("falls back to in-memory when IndexedDB is unavailable", async () => {
    // @ts-expect-error — simulate an environment without IndexedDB
    delete globalThis.indexedDB;
    const store = await freshStore();
    await store.saveMap(MAP);
    expect((await store.loadSession()).map).toEqual(MAP);
    expect(store.getSnapshot().map?.eventCount).toBe(2);
  });

  it("touches own records' envelope timestamps on hydrate, so a long-lived tab isn't GC'd by a sibling tab", async () => {
    const store = await freshStore();
    // Establish the current session id.
    await store.loadSession();
    const id = sessionStorage.getItem("tagmatch:session-id")!;
    const oldT = Date.now() - 23 * 60 * 60 * 1000;

    // Plant a map for the CURRENT session id directly via raw IndexedDB with
    // an old-but-not-stale envelope, in the same {t, v} format the store writes.
    await new Promise<void>((resolve, reject) => {
      const req = indexedDB.open("tagmatch-tools", 1);
      req.onupgradeneeded = () => {
        req.result.createObjectStore("session");
      };
      req.onsuccess = () => {
        const tx = req.result.transaction("session", "readwrite");
        const objStore = tx.objectStore("session");
        objStore.put(
          { t: oldT, v: { fileName: MAP.fileName, spec: MAP.spec, report: MAP.report } },
          `${id}:map`
        );
        objStore.put({ t: oldT, v: MAP.svgText }, `${id}:svg`);
        tx.oncomplete = () => {
          req.result.close();
          resolve();
        };
        tx.onerror = () => reject(tx.error);
      };
      req.onerror = () => reject(req.error);
    });

    // Load a fresh module instance and hydrate.
    const store2 = await freshStore();
    await store2.loadSession();

    // Read the raw record back and assert its timestamp was refreshed.
    const record = await new Promise<{ t: number; v: unknown }>((resolve, reject) => {
      const req = indexedDB.open("tagmatch-tools", 1);
      req.onsuccess = () => {
        const get = req.result.transaction("session").objectStore("session").get(`${id}:map`);
        get.onsuccess = () => {
          req.result.close();
          resolve(get.result);
        };
        get.onerror = () => reject(get.error);
      };
      req.onerror = () => reject(req.error);
    });
    expect(Date.now() - record.t).toBeLessThan(60_000);

    const store3 = await freshStore();
    expect((await store3.loadSession()).map).toEqual(MAP);
  });

  it("rowsToSpecFile / logsToFile wrap rows as JSON files", async () => {
    const store = await freshStore();
    const spec = store.rowsToSpecFile(MAP.spec);
    expect(spec.name).toBe("spec.json");
    expect(JSON.parse(await spec.text())).toEqual(MAP.spec);
    const logs = store.logsToFile(LOGS.logs);
    expect(logs.name).toBe("logs.json");
    expect(JSON.parse(await logs.text())).toEqual(LOGS.logs);
  });
});
