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

const RAW_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const API_BASE_URL = RAW_BASE.replace(/\/$/, "");

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

export async function listModels(opts?: { signal?: AbortSignal; noStore?: boolean }): Promise<ModelSchema[]> {
  const res = await fetch(`${API_BASE_URL}/api/models`, {
    cache: opts?.noStore ? "no-store" : "default",
    signal: opts?.signal,
  });
  return handle<ModelSchema[]>(res);
}

export async function uploadModel(file: File): Promise<ModelSchema> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE_URL}/api/models`, { method: "POST", body: form });
  return handle<ModelSchema>(res);
}

export async function deleteModel(modelId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/models/${encodeURIComponent(modelId)}`, {
    method: "DELETE",
  });
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
  const res = await fetch(`${API_BASE_URL}/api/models/${encodeURIComponent(modelId)}/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs }),
  });
  return handle<PredictionResult>(res);
}
