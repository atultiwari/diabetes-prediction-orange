export type InputType = "continuous" | "categorical";

export interface TargetSpec {
  name: string;
  type: InputType;
  values?: string[] | null;
}

export interface InputSpec {
  name: string;
  type: InputType;
  values?: string[] | null;
}

export interface ModelSchema {
  model_id: string;
  algorithm: string;
  target: TargetSpec;
  inputs: InputSpec[];
  supports_contributions: boolean;
  source: "bundled" | "uploaded";
}

export interface Contribution {
  feature: string;
  input_value: number | string | null;
  contribution: number;
}

export interface PredictionResult {
  predicted_class: string;
  probabilities: Record<string, number>;
  contributions: Contribution[];
}

/**
 * Two base URLs:
 *
 * - Client (browser): empty string, so `/api/foo` is relative to the current
 *   origin. In production it stays inside the public domain; Next.js rewrites
 *   it server-side to the in-container uvicorn.
 * - Server (RSC / route handlers): point straight at the backend so SSR
 *   doesn't loop back through the rewrite layer.
 *
 * Either can be overridden via env if you want to point the frontend at a
 * backend that lives somewhere else.
 */
const SERVER_API_BASE = (
  process.env.INTERNAL_API_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const CLIENT_API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(
  /\/$/,
  "",
);

function baseUrl(): string {
  return typeof window === "undefined" ? SERVER_API_BASE : CLIENT_API_BASE;
}

/** Exposed for the "backend unreachable" error panel. */
export const PUBLIC_API_BASE_URL = CLIENT_API_BASE || "(same origin)";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore — keep default detail
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export async function listModels(opts?: {
  signal?: AbortSignal;
  noStore?: boolean;
}): Promise<ModelSchema[]> {
  const res = await fetch(`${baseUrl()}/api/models`, {
    cache: opts?.noStore ? "no-store" : "default",
    signal: opts?.signal,
  });
  return handle<ModelSchema[]>(res);
}

export async function uploadModel(file: File): Promise<ModelSchema> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${baseUrl()}/api/models`, {
    method: "POST",
    body: form,
  });
  return handle<ModelSchema>(res);
}

export async function deleteModel(modelId: string): Promise<void> {
  const res = await fetch(
    `${baseUrl()}/api/models/${encodeURIComponent(modelId)}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new ApiError(detail, res.status);
  }
}

export async function predict(
  modelId: string,
  inputs: Record<string, string | number>,
): Promise<PredictionResult> {
  const res = await fetch(
    `${baseUrl()}/api/models/${encodeURIComponent(modelId)}/predict`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inputs }),
    },
  );
  return handle<PredictionResult>(res);
}

// ---- datasets / sample / batch ---------------------------------------------

export interface DatasetSummary {
  dataset_id: string;
  filename: string;
  n_rows: number;
  columns: string[];
  target_column: string | null;
  compatible_model_ids: string[];
}

export interface SampleRowResult {
  dataset_id: string;
  row_index: number;
  inputs: Record<string, string | number>;
  true_class: string | null;
}

export interface BatchRow {
  row_index: number;
  inputs: Record<string, string | number>;
  predicted_class: string;
  probabilities: Record<string, number>;
  true_class: string | null;
  correct: boolean | null;
}

export interface BatchSummary {
  total_rows_in_source: number;
  rows_processed: number;
  rows_skipped: number;
  skipped_reasons: string[];
  predicted_class_counts: Record<string, number>;
  average_probabilities: Record<string, number>;
  accuracy: number | null;
  confusion_matrix: Record<string, Record<string, number>> | null;
}

export interface BatchPredictionResult {
  model_id: string;
  source: "bundled" | "upload";
  dataset_id: string | null;
  summary: BatchSummary;
  rows: BatchRow[];
  rows_truncated: boolean;
}

export async function listDatasets(opts?: {
  signal?: AbortSignal;
  noStore?: boolean;
}): Promise<DatasetSummary[]> {
  const res = await fetch(`${baseUrl()}/api/datasets`, {
    cache: opts?.noStore ? "no-store" : "default",
    signal: opts?.signal,
  });
  return handle<DatasetSummary[]>(res);
}

export async function sampleRow(
  modelId: string,
  body: { dataset_id?: string; seed?: number } = {},
): Promise<SampleRowResult> {
  const res = await fetch(
    `${baseUrl()}/api/models/${encodeURIComponent(modelId)}/sample`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  return handle<SampleRowResult>(res);
}

export async function batchPredictBundled(
  modelId: string,
  body: { dataset_id: string; limit?: number; seed?: number },
): Promise<BatchPredictionResult> {
  const res = await fetch(
    `${baseUrl()}/api/models/${encodeURIComponent(modelId)}/predict/batch`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  return handle<BatchPredictionResult>(res);
}

export async function batchPredictUpload(
  modelId: string,
  file: File,
  opts: { limit?: number } = {},
): Promise<BatchPredictionResult> {
  const form = new FormData();
  form.append("file", file);
  if (opts.limit !== undefined) form.append("limit", String(opts.limit));
  const res = await fetch(
    `${baseUrl()}/api/models/${encodeURIComponent(modelId)}/predict/batch-upload`,
    { method: "POST", body: form },
  );
  return handle<BatchPredictionResult>(res);
}

export function bundledBatchCsvUrl(modelId: string, datasetId: string): string {
  const params = new URLSearchParams({ dataset_id: datasetId });
  return `${baseUrl()}/api/models/${encodeURIComponent(
    modelId,
  )}/predict/batch.csv?${params.toString()}`;
}

export async function uploadBatchCsv(modelId: string, file: File): Promise<Blob> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(
    `${baseUrl()}/api/models/${encodeURIComponent(modelId)}/predict/batch-upload.csv`,
    { method: "POST", body: form },
  );
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // keep default
    }
    throw new ApiError(detail, res.status);
  }
  return res.blob();
}
