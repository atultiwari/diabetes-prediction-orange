"use client";

import { useState } from "react";
import { ApiError, ModelSchema, sampleRow } from "@/app/api-client";
import { FormValues } from "./DynamicForm";

interface Props {
  schema: ModelSchema;
  onFilled: (values: FormValues, info: { dataset_id: string; row_index: number; true_class: string | null }) => void;
  disabled?: boolean;
}

export function SampleRowButton({ schema, onFilled, disabled }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setBusy(true);
    setError(null);
    try {
      const result = await sampleRow(schema.model_id);
      const filled: FormValues = {};
      for (const inp of schema.inputs) {
        const v = result.inputs[inp.name];
        filled[inp.name] = v === undefined || v === null ? "" : String(v);
      }
      onFilled(filled, {
        dataset_id: result.dataset_id,
        row_index: result.row_index,
        true_class: result.true_class,
      });
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else if (e instanceof Error) setError(e.message);
      else setError("Could not load a sample row.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={handleClick}
        disabled={busy || disabled}
        className="rounded-lg bg-canvas-soft px-3 py-1.5 text-xs font-medium text-ink shadow-ring transition hover:bg-canvas disabled:opacity-50"
        title="Pull a random row from the bundled dataset and fill the form"
      >
        {busy ? "Loading sample…" : "Fill from sample row"}
      </button>
      {error && (
        <span role="alert" className="text-xs text-warn-ink">
          {error}
        </span>
      )}
    </div>
  );
}
