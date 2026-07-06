"use client";

import { useEffect, useState } from "react";

export type Bbox = { x1: number; y1: number; x2: number; y2: number };

export function getBbox(row: Record<string, unknown>): Bbox | null {
  const x1 = row["_bbox_x1"];
  const y1 = row["_bbox_y1"];
  const x2 = row["_bbox_x2"];
  const y2 = row["_bbox_y2"];
  if (typeof x1 === "number" && typeof y1 === "number" && typeof x2 === "number" && typeof y2 === "number") {
    return { x1, y1, x2, y2 };
  }
  return null;
}

export function cropSvgString(svgContent: string, bbox: Bbox, padding: number): string {
  const x = bbox.x1 - padding;
  const y = bbox.y1 - padding;
  const width = bbox.x2 - bbox.x1 + padding * 2;
  const height = bbox.y2 - bbox.y1 + padding * 2;
  const viewBox = `${x} ${y} ${width} ${height}`;

  return svgContent.replace(/<svg\b([^>]*)>/, (_match, attrs: string) => {
    const cleanedAttrs = attrs
      .replace(/\s*viewBox="[^"]*"/i, "")
      .replace(/\s*width="[^"]*"/i, "")
      .replace(/\s*height="[^"]*"/i, "");
    return `<svg${cleanedAttrs} viewBox="${viewBox}" width="${width}" height="${height}">`;
  });
}

function djb2(str: string): string {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 33) ^ str.charCodeAt(i);
  }
  return (hash >>> 0).toString(36);
}

const blobCache = new Map<string, string>();

export function clearSvgCropCache(): void {
  for (const url of blobCache.values()) {
    URL.revokeObjectURL(url);
  }
  blobCache.clear();
}

export function useSvgCropUrl(svgContent: string | null, bbox: Bbox | null, padding: number): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!svgContent || !bbox) {
      setUrl(null);
      return;
    }
    const key = `${djb2(svgContent)}:${bbox.x1}:${bbox.y1}:${bbox.x2}:${bbox.y2}:${padding}`;
    const cached = blobCache.get(key);
    if (cached) {
      setUrl(cached);
      return;
    }
    const cropped = cropSvgString(svgContent, bbox, padding);
    const blob = new Blob([cropped], { type: "image/svg+xml" });
    const blobUrl = URL.createObjectURL(blob);
    blobCache.set(key, blobUrl);
    setUrl(blobUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [svgContent, bbox?.x1, bbox?.y1, bbox?.x2, bbox?.y2, padding]);

  return url;
}
