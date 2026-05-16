"use client";

import { Contribution } from "@/app/api-client";

interface Props {
  contributions: Contribution[];
  predictedClass: string;
}

function prettyLabel(name: string): string {
  if (!name) return name;
  const spaced = name.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

export function ContributionsChart({ contributions, predictedClass }: Props) {
  if (contributions.length === 0) return null;
  const maxAbs = Math.max(...contributions.map((c) => Math.abs(c.contribution)), 1e-9);

  return (
    <div className="surface p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-base font-semibold tracking-tight label-pretty">Top contributors</h3>
        <span
          className="text-[0.7rem] text-ink-subtle"
          title={`Higher = pushed result toward ${predictedClass}`}
        >
          relative to <span className="font-mono">{predictedClass}</span>
        </span>
      </div>
      <ul className="space-y-3" role="list">
        {contributions.map((c) => {
          const positive = c.contribution >= 0;
          const widthPct = Math.max(2, Math.round((Math.abs(c.contribution) / maxAbs) * 100));
          return (
            <li key={c.feature} className="grid grid-cols-[1fr,2fr] items-center gap-3">
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-ink label-pretty">
                  {prettyLabel(c.feature)}
                </div>
                <div className="truncate font-mono text-[0.7rem] text-ink-subtle">
                  {c.feature} = {String(c.input_value ?? "—")}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-canvas-soft">
                  <div
                    className={positive ? "contrib-bar-pos" : "contrib-bar-neg"}
                    style={{
                      width: `${widthPct}%`,
                      height: "100%",
                      borderRadius: "9999px",
                      marginLeft: positive ? "auto" : 0,
                    }}
                  />
                </div>
                <span
                  className={`w-14 text-right text-xs tabular-nums ${
                    positive ? "text-warn-ink" : "text-ink-muted"
                  }`}
                >
                  {positive ? "+" : ""}
                  {c.contribution.toFixed(2)}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
