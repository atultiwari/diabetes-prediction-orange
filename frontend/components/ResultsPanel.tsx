"use client";

import { ModelSchema, PredictionResult } from "@/app/api-client";
import { ContributionsChart } from "./ContributionsChart";

interface Props {
  schema: ModelSchema;
  result: PredictionResult;
}

// Editorial choice: amber for the *positive* class on a 2-class model, neutral
// for everything else. This is a styling cue, not a clinical claim — we never
// label the result as "good" or "bad".
function classToneClass(schema: ModelSchema, predicted: string): string {
  const values = schema.target.values ?? [];
  if (values.length === 2) {
    const positive = values[values.length - 1];
    if (predicted === positive) return "bg-warn-soft text-warn-ink";
  }
  return "bg-canvas-soft text-ink";
}

export function ResultsPanel({ schema, result }: Props) {
  const tone = classToneClass(schema, result.predicted_class);
  const classes = schema.target.values ?? Object.keys(result.probabilities);

  return (
    <section aria-live="polite" className="flex flex-col gap-5">
      <div className={`surface flex flex-col gap-4 p-6 ${tone}`}>
        <div>
          <div className="text-xs uppercase tracking-wider text-ink-subtle">Predicted class</div>
          <div className="mt-1 text-4xl font-semibold tracking-tight">
            {result.predicted_class}
          </div>
          <div className="mt-1 text-xs text-ink-subtle">
            target <span className="font-mono">{schema.target.name}</span>
          </div>
        </div>
        <div className="flex flex-col gap-2">
          {classes.map((cls) => {
            const p = result.probabilities[cls] ?? 0;
            const pct = (p * 100).toFixed(1);
            return (
              <div key={cls}>
                <div className="flex items-baseline justify-between text-xs text-ink-muted">
                  <span className="font-mono">{cls}</span>
                  <span className="tabular-nums">{pct}%</span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-canvas-soft">
                  <div className="prob-bar h-full" style={{ width: `${p * 100}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {result.contributions.length > 0 && (
        <ContributionsChart
          contributions={result.contributions}
          predictedClass={result.predicted_class}
        />
      )}

      <p className="px-1 text-[0.7rem] text-ink-subtle">
        Educational demo only. Not for clinical use.
      </p>
    </section>
  );
}
