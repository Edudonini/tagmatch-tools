"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import {
  clearLogs,
  clearMap,
  getServerSnapshot,
  getSnapshot,
  subscribe,
} from "./sessionStore";

/** Session chips (loaded map / logs). Rendered inside the AppShell top bar. */
export function SessionBar() {
  const meta = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  if (!meta.map && !meta.logs) return null;

  return (
    <div className="session-chips">
      {meta.map && (
        <span className="session-chip">
          <Link href="/extract-map" className="session-chip-link">
            🗺️ {meta.map.fileName} · {meta.map.eventCount} eventos
          </Link>
          <button
            className="session-chip-clear"
            onClick={() => void clearMap()}
            aria-label="Limpar mapa da sessão"
          >
            ✕
          </button>
        </span>
      )}
      {meta.logs && (
        <span className="session-chip">
          <Link href="/extract-logs" className="session-chip-link">
            📋 {meta.logs.fileCount} log{meta.logs.fileCount === 1 ? "" : "s"} ·{" "}
            {meta.logs.eventCount} eventos
          </Link>
          <button
            className="session-chip-clear"
            onClick={() => void clearLogs()}
            aria-label="Limpar logs da sessão"
          >
            ✕
          </button>
        </span>
      )}
    </div>
  );
}
