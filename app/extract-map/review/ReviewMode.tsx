"use client";

import { useState } from "react";
import { EventReviewCard, type ReviewRow } from "./EventReviewCard";
import { useParsedSvg } from "./useParsedSvg";

type ReviewModeProps = {
  rows: ReviewRow[];
  svgContent: string | null;
  onChange: (rows: ReviewRow[]) => void;
  onExit: () => void;
};

export function ReviewMode({ rows, svgContent, onChange, onExit }: ReviewModeProps) {
  const [index, setIndex] = useState(0);
  const [reviewed, setReviewed] = useState<Set<number>>(new Set());
  const parsedRoot = useParsedSvg(svgContent);

  const clampedIndex = rows.length === 0 ? 0 : Math.min(index, rows.length - 1);
  const current = rows[clampedIndex];

  function updateCurrent(updated: ReviewRow) {
    const next = rows.slice();
    next[clampedIndex] = updated;
    onChange(next);
  }

  function goTo(newIndex: number) {
    setIndex(Math.max(0, Math.min(newIndex, rows.length - 1)));
  }

  function confirmAndNext() {
    setReviewed((prev) => new Set(prev).add(clampedIndex));
    goTo(clampedIndex + 1);
  }

  function deleteCurrent() {
    const next = rows.slice();
    next.splice(clampedIndex, 1);
    setReviewed((prev) => {
      const shifted = new Set<number>();
      for (const i of prev) {
        if (i < clampedIndex) shifted.add(i);
        else if (i > clampedIndex) shifted.add(i - 1);
      }
      return shifted;
    });
    onChange(next);
    if (clampedIndex >= next.length) {
      setIndex(Math.max(0, next.length - 1));
    }
  }

  function addEvent() {
    const maxOrder = rows.reduce((max, r) => {
      const n = Number(r.event_order);
      return Number.isFinite(n) && n > max ? n : max;
    }, 0);
    const blank: ReviewRow = { event_order: maxOrder + 1, name: "" };
    const next = [...rows, blank];
    onChange(next);
    setIndex(next.length - 1);
  }

  if (rows.length === 0) {
    return (
      <div className="panel review-empty">
        <p>No events left to review.</p>
        <div className="review-toolbar-actions">
          <button className="btn btn-primary" onClick={addEvent}>
            + Add event
          </button>
          <button className="btn btn-ghost" onClick={onExit}>
            Back to table
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="review-mode">
      <div className="review-toolbar">
        <span className="review-progress">
          {reviewed.size} of {rows.length} reviewed
        </span>
        <div className="review-toolbar-actions">
          <button className="btn btn-ghost" onClick={addEvent}>
            + Add event
          </button>
          <button className="btn btn-ghost" onClick={onExit}>
            Back to table
          </button>
        </div>
      </div>

      <EventReviewCard
        key={`${clampedIndex}:${rows.length}`}
        event={current}
        svgContent={svgContent}
        parsedRoot={parsedRoot}
        onUpdate={updateCurrent}
      />

      <div className="review-nav">
        <button className="btn btn-ghost" onClick={() => goTo(clampedIndex - 1)} disabled={clampedIndex === 0}>
          ← Prev
        </button>
        <span className="review-position">
          Event {clampedIndex + 1} of {rows.length}
        </span>
        <button className="btn btn-ghost" onClick={deleteCurrent}>
          Delete
        </button>
        <button
          className="btn btn-ghost"
          onClick={() => goTo(clampedIndex + 1)}
          disabled={clampedIndex === rows.length - 1}
        >
          Skip →
        </button>
        <button className="btn btn-primary" onClick={confirmAndNext}>
          Confirm &amp; Next →
        </button>
      </div>
    </div>
  );
}
