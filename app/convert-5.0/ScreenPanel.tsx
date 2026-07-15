"use client";

import { useEffect, useState } from "react";
import type { Screen } from "./taxonomy5";

// Reproduce the Whimsical placement exactly: the viewBox is the crop window
// into the (possibly much taller) source image.
function viewBoxOf(screen: Screen): string {
  return screen.view_box ?? `0 0 ${screen.image_width || screen.width} ${screen.image_height || screen.height}`;
}

function ScreenImage({ screen, className }: { screen: Screen; className?: string }) {
  const [failed, setFailed] = useState(false);
  // SVG <image> error events are unreliable across browsers; preload with an
  // HTMLImageElement to detect dead Whimsical URLs.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFailed(false);
    const probe = new Image();
    probe.onerror = () => setFailed(true);
    probe.src = screen.url;
    return () => {
      probe.onerror = null;
    };
  }, [screen.url]);

  if (failed) {
    return <div className="c5-screen-placeholder">Tela indisponível (URL do mapa expirou)</div>;
  }
  const parts = viewBoxOf(screen).split(/\s+/).map(Number);
  const [, , vw, vh] = parts;
  return (
    <svg
      className={className}
      viewBox={viewBoxOf(screen)}
      style={{ aspectRatio: `${vw || 375} / ${vh || 812}` }}
      preserveAspectRatio="xMidYMid meet"
      role="img"
    >
      <image
        href={screen.url}
        x="0"
        y="0"
        width={screen.image_width || screen.width}
        height={screen.image_height || screen.height}
      />
    </svg>
  );
}

export function ScreenPanel({ screens }: { screens: Screen[] }) {
  const [index, setIndex] = useState(0);
  const [lightbox, setLightbox] = useState(false);
  const count = screens.length;
  const safeIndex = count === 0 ? 0 : Math.min(index, count - 1);

  useEffect(() => {
    if (!lightbox) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setLightbox(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightbox]);

  if (count === 0) {
    return (
      <div className="c5-screen-placeholder">
        Nenhuma tela associada a este screenName no SVG
      </div>
    );
  }
  const current = screens[safeIndex];
  return (
    <div className="c5-screen-panel">
      <button
        type="button"
        className="c5-screen-frame"
        onClick={() => setLightbox(true)}
        title="Ampliar tela"
      >
        <ScreenImage screen={current} className="c5-screen-img" />
      </button>
      {count > 1 && (
        <div className="c5-screen-nav">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setIndex((safeIndex - 1 + count) % count)}
            aria-label="Tela anterior"
          >
            ‹
          </button>
          <span className="c5-screen-count">
            {safeIndex + 1} / {count}
          </span>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setIndex((safeIndex + 1) % count)}
            aria-label="Próxima tela"
          >
            ›
          </button>
        </div>
      )}
      {lightbox && (
        <div className="c5-lightbox" onClick={() => setLightbox(false)} role="presentation">
          <ScreenImage screen={current} className="c5-lightbox-img" />
        </div>
      )}
    </div>
  );
}
