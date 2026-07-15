"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { nextStepsFor } from "./nextStepsResolver";
import { getServerSnapshot, getSnapshot, subscribe } from "./sessionStore";

export function NextSteps({ tool }: { tool: "extract-map" | "extract-logs" }) {
  const meta = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const steps = nextStepsFor(tool, !!meta.map, !!meta.logs);
  if (steps.length === 0) return null;

  return (
    <section className="next-steps" aria-label="Próximo passo">
      <div className="next-steps-label">Próximo passo</div>
      <div className="next-steps-cards">
        {steps.map((step) => (
          <div className="next-step" key={step.href}>
            <Link href={step.href} className="next-step-main">
              <span className="next-step-name">{step.label}</span>
              <span className="next-step-arrow">→</span>
            </Link>
            {step.hint && step.hintHref && (
              <Link href={step.hintHref} className="next-step-hint">
                {step.hint} →
              </Link>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
