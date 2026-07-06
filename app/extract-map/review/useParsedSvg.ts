"use client";

import { useMemo } from "react";

export function useParsedSvg(svgContent: string | null): SVGSVGElement | null {
  return useMemo(() => {
    if (!svgContent) return null;
    const doc = new DOMParser().parseFromString(svgContent, "image/svg+xml");
    const root = doc.documentElement;
    if (root.tagName.toLowerCase() !== "svg") return null;
    return root as unknown as SVGSVGElement;
  }, [svgContent]);
}
