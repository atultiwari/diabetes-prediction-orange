"use client";

import { useMemo, useState } from "react";
import {
  BatchPredictionResult,
  ModelSchema,
  bundledBatchCsvUrl,
} from "@/app/api-client";

interface Props {
  schema: ModelSchema;
  result: BatchPredictionResult;
  /**
   * When the upload-mode flow has the original file in scope, this callback
   * fires when the user clicks "Download all predictions" so the parent can
   * stream the full CSV from the upload endpoint.
   */
  onDownloadUploadCsv?: () => Promise<void> | void;
  downloadingUploadCsv?: boolean;
}

function prettyLabel(name: string): string {
  if (!name) return name;
  const spaced = name.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function asNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

export function BatchResultsTable({
  schema,
  result,
  onDownloadUploadCsv,
  downloadingUploadCsv,
}: Props) {
  const [previewLimit, setPreviewLimit] = useState(20);
  const classes = useMemo(
    () => schema.target.values ?? Object.keys(result.summary.predicted_class_counts),
    [schema, result],
  );
  const visible = result.rows.slice(0, previewLimit);

  const accuracyPct =
    result.summary.accuracy === null
      ? null
      : (result.summary.accuracy * 100).toFixed(1);

  const csvHref =
    result.source === "bundled" && result.dataset_id
      ? bundledBatchCsvUrl(result.model_id, result.dataset_id)
      : null;

  return (
    <div className="flex flex-col gap-4">
      <div className="surface flex flex-col gap-3 p-5">
        <div className="flex items-baseline justify-between">
          <h3 className="text-base font-semibold tracking-tight">Batch summary</h3>
          {csvHref ? (
            <a
              href={csvHref}
              download
              className="rounded-lg bg-ink px-3 py-1.5 text-xs font-medium text-canvas transition hover:bg-ink/90"
            >
              Download all predictions (CSV)
            </a>
          ) : onDownloadUploadCsv ? (
            <button
              type="button"
              onClick={() => void onDownloadUploadCsv()}
              disabled={downloadingUploadCsv}
              className="rounded-lg bg-ink px-3 py-1.5 text-xs font-medium text-canvas transition hover:bg-ink/90 disabled:opacity-60"
            >
              {downloadingUploadCsv ? "Preparing…" : "Download all predictions (CSV)"}
            </button>
          ) : null}
        </div>

        <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-[0.7rem] uppercase tracking-wider text-ink-subtle">Rows processed</dt>
            <dd className="font-semibold tabular-nums">{result.summary.rows_processed}</dd>
          </div>
          <div>
            <dt className="text-[0.7rem] uppercase tracking-wider text-ink-subtle">Rows skipped</dt>
            <dd className="font-semibold tabular-nums">{result.summary.rows_skipped}</dd>
          </div>
          <div>
            <dt className="text-[0.7rem] uppercase tracking-wider text-ink-subtle">Accuracy</dt>
            <dd className="font-semibold tabular-nums">
              {accuracyPct === null ? "—" : `${accuracyPct}%`}
            </dd>
          </div>
          <div>
            <dt className="text-[0.7rem] uppercase tracking-wider text-ink-subtle">Source</dt>
            <dd className="font-semibold">
              {result.source === "bundled" ? result.dataset_id : "Uploaded CSV"}
            </dd>
          </div>
        </dl>

        <div className="flex flex-wrap gap-2 text-xs">
          {classes.map((c) => (
            <span
              key={c}
              className="rounded-full bg-canvas-soft px-3 py-1 text-ink-muted shadow-ring"
            >
              <span className="font-mono">{c}</span>:&nbsp;
              {result.summary.predicted_class_counts[c] ?? 0} predicted ·{" "}
              {(((result.summary.average_probabilities[c] ?? 0) * 100)).toFixed(1)}%
              avg p
            </span>
          ))}
        </div>

        {result.summary.confusion_matrix && classes.length > 0 && (
          <div className="overflow-x-auto">
            <table className="mt-1 w-full max-w-md text-xs">
              <caption className="mb-1 text-left text-[0.7rem] uppercase tracking-wider text-ink-subtle">
                Confusion matrix (rows: true, cols: predicted)
              </caption>
              <thead>
                <tr className="text-ink-subtle">
                  <th className="w-20"></th>
                  {classes.map((c) => (
                    <th key={c} className="px-2 py-1 text-right font-mono font-medium">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {classes.map((trueCls) => (
                  <tr key={trueCls} className="border-t border-canvas-soft/80">
                    <th className="px-2 py-1 text-left font-mono font-medium text-ink-muted">{trueCls}</th>
                    {classes.map((predCls) => {
                      const n = result.summary.confusion_matrix?.[trueCls]?.[predCls] ?? 0;
                      const onDiagonal = trueCls === predCls;
                      return (
                        <td
                          key={predCls}
                          className={`px-2 py-1 text-right tabular-nums ${
                            onDiagonal ? "font-semibold text-ink" : "text-ink-muted"
                          }`}
                        >
                          {n}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {result.summary.skipped_reasons.length > 0 && (
          <details className="text-xs text-ink-muted">
            <summary className="cursor-pointer">
              Skipped row details ({result.summary.skipped_reasons.length})
            </summary>
            <ul className="mt-1 space-y-0.5 font-mono">
              {result.summary.skipped_reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </details>
        )}
      </div>

      <div className="surface overflow-hidden">
        <div className="flex items-baseline justify-between border-b border-canvas-soft/80 px-5 py-3">
          <h3 className="text-sm font-semibold tracking-tight">
            Preview ({Math.min(previewLimit, result.rows.length)} of {result.rows.length})
            {result.rows_truncated ? " — server cap" : ""}
          </h3>
          <div className="flex items-center gap-2 text-xs">
            <label className="text-ink-subtle">Show</label>
            <select
              value={previewLimit}
              onChange={(e) => setPreviewLimit(Number(e.target.value))}
              className="rounded-md bg-canvas px-2 py-1 text-xs shadow-ring outline-none"
            >
              {[10, 20, 50, 100, 250].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead className="bg-canvas-soft/60 text-left text-ink-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Row</th>
                {schema.inputs.map((inp) => (
                  <th key={inp.name} className="px-3 py-2 font-medium" title={inp.name}>
                    {prettyLabel(inp.name)}
                  </th>
                ))}
                <th className="px-3 py-2 font-medium">Predicted</th>
                {classes.map((c) => (
                  <th key={c} className="px-3 py-2 font-medium font-mono">
                    p({c})
                  </th>
                ))}
                <th className="px-3 py-2 font-medium">True</th>
                <th className="px-3 py-2 font-medium">Correct</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <tr key={row.row_index} className="border-t border-canvas-soft/60">
                  <td className="px-3 py-1.5 tabular-nums text-ink-subtle">{row.row_index}</td>
                  {schema.inputs.map((inp) => {
                    const v = row.inputs[inp.name];
                    const display =
                      inp.type === "continuous"
                        ? (asNumber(v)?.toFixed(2) ?? String(v ?? ""))
                        : String(v ?? "");
                    return (
                      <td key={inp.name} className="px-3 py-1.5 tabular-nums">
                        {display}
                      </td>
                    );
                  })}
                  <td className="px-3 py-1.5 font-medium">{row.predicted_class}</td>
                  {classes.map((c) => (
                    <td key={c} className="px-3 py-1.5 tabular-nums">
                      {((row.probabilities[c] ?? 0) * 100).toFixed(1)}%
                    </td>
                  ))}
                  <td className="px-3 py-1.5 text-ink-muted">{row.true_class ?? "—"}</td>
                  <td className="px-3 py-1.5">
                    {row.correct === null ? (
                      <span className="text-ink-subtle">—</span>
                    ) : row.correct ? (
                      <span className="font-medium text-ok-ink">✓</span>
                    ) : (
                      <span className="font-medium text-warn-ink">✗</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
