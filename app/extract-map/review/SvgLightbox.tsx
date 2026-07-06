"use client";

import { useEffect, useRef } from "react";
import type { Bbox } from "./useSvgCropUrl";

type SvgLightboxProps = {
  parsedRoot: SVGSVGElement;
  bbox: Bbox;
  padding: number;
  onClose: () => void;
};

export function SvgLightbox({ parsedRoot, bbox, padding, onClose }: SvgLightboxProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const clone = parsedRoot.cloneNode(true) as SVGSVGElement;
    const x = bbox.x1 - padding;
    const y = bbox.y1 - padding;
    const width = bbox.x2 - bbox.x1 + padding * 2;
    const height = bbox.y2 - bbox.y1 + padding * 2;
    clone.setAttribute("viewBox", `${x} ${y} ${width} ${height}`);
    clone.setAttribute("width", "100%");
    clone.setAttribute("height", "100%");
    container.appendChild(clone);

    return () => {
      container.removeChild(clone);
    };
  }, [parsedRoot, bbox.x1, bbox.y1, bbox.x2, bbox.y2, padding]);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div className="lightbox-overlay" onClick={onClose}>
      <div className="lightbox-content" ref={containerRef} onClick={(e) => e.stopPropagation()} />
      <button className="btn btn-ghost lightbox-close" onClick={onClose}>
        Close ✕
      </button>
    </div>
  );
}
