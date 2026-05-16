"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  BatchPredictionResult,
  DatasetSummary,
  ModelSchema,
  batchPredictBundled,
  batchPredictUpload,
  listDatasets,
  uploadBatchCsv,
} from "@/app/api-client";
import { BatchResultsTable } from "./BatchResultsTable";

interface Props {
  schema: ModelSchema;
}

type Mode = "bundled" | "upload";

const DEFAULT_LIMIT = 50;

export function BatchPredictPanel({ schema }: Props) {
  const [datasets, setDatasets] = useState<DatasetSummary[] | null>(null);
  const [loadingDatasets, setLoadingDatasets] = useState(false);
  const [mode, setMode] = useState<Mode>("bundled");
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const [limit, setLimit] = useState<number>(DEFAULT_LIMIT);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BatchPredictionResult | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [downloadingUploadCsv, setDownloadingUploadCsv] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingDatasets(true);
    listDatasets({ noStore: true })
      .then((d) => {
        if (cancelled) return;
        setDatasets(d);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Failed to load datasets");
      })
      .finally(() => {
        if (!cancelled) setLoadingDatasets(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Reset on model change
  useEffect(() => {
    setResult(null);
    setError(null);
    setUploadFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schema.model_id]);

  const compatibleDatasets = useMemo(
    () =>
      (datasets ?? []).filter((d) =>
        d.compatible_model_ids.includes(schema.model_id),
      ),
    [datasets, schema.model_id],
  );

  // Default the dataset selection to the first compatible one
  useEffect(() => {
    if (mode !== "bundled") return;
    if (compatibleDatasets.length === 0) {
      setSelectedDatasetId("");
      return;
    }
    if (!compatibleDatasets.some((d) => d.dataset_id === selectedDatasetId)) {
      setSelectedDatasetId(compatibleDatasets[0].dataset_id);
    }
  }, [compatibleDatasets, mode, selectedDatasetId]);

  async function runBundled() {
    if (!selectedDatasetId) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await batchPredictBundled(schema.model_id, {
        dataset_id: selectedDatasetId,
        limit,
      });
      setResult(r);
    } catch (e) {
      setError(messageFor(e));
    } finally {
      setRunning(false);
    }
  }

  async function runUpload() {
    if (!uploadFile) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await batchPredictUpload(schema.model_id, uploadFile, {
        limit,
      });
      setResult(r);
    } catch (e) {
      setError(messageFor(e));
    } finally {
      setRunning(false);
    }
  }

  async function handleUploadCsvDownload() {
    if (!uploadFile) return;
    setDownloadingUploadCsv(true);
    try {
      const blob = await uploadBatchCsv(schema.model_id, uploadFile);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const safeName = uploadFile.name.replace(/\.csv$/i, "");
      a.href = url;
      a.download = `${schema.model_id} on ${safeName} - predictions.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(messageFor(e));
    } finally {
      setDownloadingUploadCsv(false);
    }
  }

  const noCompatibleBundled =
    !loadingDatasets && compatibleDatasets.length === 0;

  return (
    <section className="flex flex-col gap-4">
      <div className="surface p-5">
        <header className="mb-4 flex items-baseline justify-between">
          <h2 className="text-lg font-semibold tracking-tight label-pretty">
            Batch prediction
          </h2>
          <div className="text-xs text-ink-subtle">
            Run a CSV through the model and see accuracy on rows that include a true label.
          </div>
        </header>

        <div className="mb-4 inline-flex gap-1 rounded-lg bg-canvas-soft p-1 shadow-ring">
          {(
            [
              { value: "bundled", label: "Bundled dataset" },
              { value: "upload", label: "Upload a CSV" },
            ] as const
          ).map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setMode(opt.value)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                mode === opt.value
                  ? "bg-canvas text-ink shadow-card"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {mode === "bundled" ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className="block text-xs font-medium text-ink-muted">
                Dataset
              </label>
              {noCompatibleBundled ? (
                <p className="mt-1 text-sm text-ink-muted">
                  No bundled dataset matches this model&apos;s inputs.
                </p>
              ) : (
                <select
                  value={selectedDatasetId}
                  onChange={(e) => setSelectedDatasetId(e.target.value)}
                  disabled={loadingDatasets || running}
                  className="mt-1 w-full rounded-lg bg-canvas px-3 py-2 text-sm text-ink shadow-ring outline-none transition focus:shadow-[inset_0_0_0_2px_theme(colors.accent.DEFAULT)]"
                >
                  {compatibleDatasets.map((d) => (
                    <option key={d.dataset_id} value={d.dataset_id}>
                      {d.dataset_id} ({d.n_rows.toLocaleString()} rows
                      {d.target_column ? ` · true ${d.target_column}` : ""})
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div className="w-32">
              <label className="block text-xs font-medium text-ink-muted">
                Rows
              </label>
              <input
                type="number"
                min={1}
                max={1000}
                value={limit}
                onChange={(e) => setLimit(Math.max(1, Number(e.target.value) || 1))}
                disabled={running}
                className="mt-1 w-full rounded-lg bg-canvas px-3 py-2 text-sm text-ink shadow-ring outline-none transition focus:shadow-[inset_0_0_0_2px_theme(colors.accent.DEFAULT)]"
              />
            </div>
            <button
              type="button"
              onClick={runBundled}
              disabled={!selectedDatasetId || running}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-fg shadow-card transition hover:brightness-105 disabled:opacity-50"
            >
              {running ? "Running…" : "Run batch"}
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label className="block text-xs font-medium text-ink-muted">
                CSV file
              </label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                disabled={running}
                className="mt-1 block w-full text-sm text-ink file:mr-3 file:rounded-md file:border-0 file:bg-canvas-soft file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-ink hover:file:bg-canvas"
              />
              <p className="mt-1 text-[0.7rem] text-ink-subtle">
                Required columns:{" "}
                <span className="font-mono">
                  {schema.inputs.map((i) => i.name).join(", ")}
                </span>
                . Target column <span className="font-mono">{schema.target.name}</span>{" "}
                is optional but enables accuracy.
              </p>
            </div>
            <div className="w-32">
              <label className="block text-xs font-medium text-ink-muted">
                Rows
              </label>
              <input
                type="number"
                min={1}
                max={1000}
                value={limit}
                onChange={(e) => setLimit(Math.max(1, Number(e.target.value) || 1))}
                disabled={running}
                className="mt-1 w-full rounded-lg bg-canvas px-3 py-2 text-sm text-ink shadow-ring outline-none transition focus:shadow-[inset_0_0_0_2px_theme(colors.accent.DEFAULT)]"
              />
            </div>
            <button
              type="button"
              onClick={runUpload}
              disabled={!uploadFile || running}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-fg shadow-card transition hover:brightness-105 disabled:opacity-50"
            >
              {running ? "Running…" : "Run on upload"}
            </button>
          </div>
        )}

        {error && (
          <div role="alert" className="mt-3 rounded-md bg-warn-soft px-3 py-2 text-xs text-warn-ink">
            {error}
          </div>
        )}
      </div>

      {result && (
        <BatchResultsTable
          schema={schema}
          result={result}
          onDownloadUploadCsv={
            result.source === "upload" && uploadFile
              ? handleUploadCsvDownload
              : undefined
          }
          downloadingUploadCsv={downloadingUploadCsv}
        />
      )}
    </section>
  );
}

function messageFor(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "Batch prediction failed.";
}
