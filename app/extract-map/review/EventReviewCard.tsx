"use client";

import { useState } from "react";
import { badgeClass, badgeLabel } from "../../_lib/ResultsPanel";
import { useSvgCropUrl, getBbox } from "./useSvgCropUrl";
import { SvgLightbox } from "./SvgLightbox";

export type ReviewRow = Record<string, unknown>;

type EventReviewCardProps = {
  event: ReviewRow;
  svgContent: string | null;
  parsedRoot: SVGSVGElement | null;
  onUpdate: (updated: ReviewRow) => void;
};

const PRIMARY_FIELDS = ["event_order", "name"];
const GA_FIELDS_FIRST = ["sn", "ct", "ac", "lb"];
// Derived/metadata fields: hidden from the card (pure noise for a human
// reviewer), but preserved untouched in the row data and downloads.
const HIDDEN_FIELDS = ["spec_id", "raw_lines", "confidence_score"];

function isHiddenField(key: string): boolean {
  return key.startsWith("_") || key.endsWith("_regex") || HIDDEN_FIELDS.includes(key);
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function EventReviewCard({ event, svgContent, parsedRoot, onUpdate }: EventReviewCardProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  // Fields added via "+ Add field" start out empty, and would otherwise be
  // immediately hidden by the populated-fields-only filter below (making the
  // button appear to do nothing). Keep manually-added keys visible until the
  // reviewer removes them, regardless of whether they've typed a value yet.
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set());
  const bbox = getBbox(event);
  const cropUrl = useSvgCropUrl(svgContent, bbox, 20);

  // Only populated fields are shown - most events carry few parameters, and
  // empty fields are noise. GA core fields (sn/ct/ac/lb) always sort first.
  const fieldEntries = Object.entries(event)
    .filter(
      ([key, value]) =>
        !PRIMARY_FIELDS.includes(key) &&
        !isHiddenField(key) &&
        (revealedKeys.has(key) || (value !== null && value !== undefined && String(value) !== ""))
    )
    .sort(([a], [b]) => {
      const ia = GA_FIELDS_FIRST.indexOf(a);
      const ib = GA_FIELDS_FIRST.indexOf(b);
      if (ia !== -1 && ib !== -1) return ia - ib;
      if (ia !== -1) return -1;
      if (ib !== -1) return 1;
      return 0;
    });

  function updateField(key: string, value: string) {
    const next = { ...event, [key]: value };
    // Keep the derived regex companion in sync so downloads never carry a
    // stale pattern for an edited value (the full platform re-derives these
    // server-side on save; this tool has no save step, so sync inline).
    const regexKey = `${key}_regex`;
    if (regexKey in event && String(event[regexKey] ?? "") !== "") {
      next[regexKey] = `^${escapeRegex(value)}$`;
    }
    onUpdate(next);
  }

  function addField() {
    let n = 1;
    while (`new_field_${n}` in event) n++;
    const newKey = `new_field_${n}`;
    setRevealedKeys((prev) => new Set(prev).add(newKey));
    onUpdate({ ...event, [newKey]: "" });
  }

  function removeField(key: string) {
    const next = { ...event };
    delete next[key];
    onUpdate(next);
  }

  function renameField(oldKey: string, newKey: string) {
    if (!newKey || newKey === oldKey) return;
    const next: ReviewRow = {};
    for (const [k, v] of Object.entries(event)) {
      next[k === oldKey ? newKey : k] = v;
    }
    // Carry the "stay visible while empty" flag over to the new key, or a
    // freshly-renamed blank field (e.g. right after "+ Add field") would
    // vanish the instant it's renamed, before the reviewer can fill in a value.
    setRevealedKeys((prev) => {
      if (!prev.has(oldKey)) return prev;
      const nextSet = new Set(prev);
      nextSet.delete(oldKey);
      nextSet.add(newKey);
      return nextSet;
    });
    onUpdate(next);
  }

  return (
    <div className="panel review-card">
      <div className="review-card-preview">
        {cropUrl ? (
          <img
            src={cropUrl}
            alt="Event location preview"
            className="review-crop-img"
            onClick={() => setLightboxOpen(true)}
          />
        ) : (
          <div className="review-crop-placeholder">No visual preview for this event</div>
        )}
      </div>

      <div className="review-card-fields">
        <div className="review-primary-fields">
          <label className="review-field-label">
            event_order
            <input
              className="review-field-input"
              value={String(event.event_order ?? "")}
              onChange={(e) => updateField("event_order", e.target.value)}
            />
          </label>
          <label className="review-field-label">
            name
            <span className={`badge ${badgeClass(event.name)}`}>
              <span className="dot" />
              {badgeLabel(event.name)}
            </span>
            <input
              className="review-field-input"
              value={String(event.name ?? "")}
              onChange={(e) => updateField("name", e.target.value)}
            />
          </label>
        </div>

        <div className="review-kv-list">
          {fieldEntries.map(([key, value]) => (
            <div className="review-kv-row" key={key}>
              <input
                className="review-kv-key"
                defaultValue={key}
                onBlur={(e) => renameField(key, e.target.value)}
              />
              <input
                className="review-kv-value"
                value={String(value ?? "")}
                onChange={(e) => updateField(key, e.target.value)}
              />
              <button
                className="btn btn-ghost review-kv-remove"
                onClick={() => removeField(key)}
                aria-label={`Remove ${key}`}
              >
                ✕
              </button>
            </div>
          ))}
          <button className="btn btn-ghost" onClick={addField}>
            + Add field
          </button>
        </div>
      </div>

      {lightboxOpen && parsedRoot && bbox && (
        <SvgLightbox parsedRoot={parsedRoot} bbox={bbox} padding={60} onClose={() => setLightboxOpen(false)} />
      )}
    </div>
  );
}
