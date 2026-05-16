"use client";

import { FormEvent } from "react";
import { ModelSchema } from "@/app/api-client";

export type FormValues = Record<string, string>;

interface Props {
  schema: ModelSchema;
  values: FormValues;
  onChange: (next: FormValues) => void;
  onSubmit: () => void;
  submitting: boolean;
}

function prettyLabel(name: string): string {
  if (!name) return name;
  const spaced = name.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function isComplete(schema: ModelSchema, values: FormValues): boolean {
  return schema.inputs.every((inp) => {
    const v = values[inp.name];
    return v !== undefined && v !== null && String(v).trim() !== "";
  });
}

export function DynamicForm({ schema, values, onChange, onSubmit, submitting }: Props) {
  function update(name: string, value: string) {
    onChange({ ...values, [name]: value });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit();
  }

  const complete = isComplete(schema, values);

  return (
    <form onSubmit={handleSubmit} className="surface p-6">
      <div className="mb-4">
        <h2 className="text-lg font-semibold tracking-tight label-pretty">Inputs</h2>
        <p className="text-xs text-ink-subtle">
          {schema.inputs.length} fields · target{" "}
          <span className="font-mono">{schema.target.name}</span>
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {schema.inputs.map((inp) => {
          const id = `f-${inp.name}`;
          const isCat = inp.type === "categorical";
          return (
            <div key={inp.name} className="flex flex-col gap-1.5">
              <label htmlFor={id} className="text-sm font-medium text-ink label-pretty">
                {prettyLabel(inp.name)}
              </label>
              {isCat ? (
                <select
                  id={id}
                  required
                  value={values[inp.name] ?? ""}
                  onChange={(e) => update(inp.name, e.target.value)}
                  className="rounded-lg bg-canvas px-3 py-2 text-ink shadow-ring outline-none transition focus:shadow-[inset_0_0_0_2px_theme(colors.accent.DEFAULT)]"
                >
                  <option value="" disabled>
                    Select…
                  </option>
                  {(inp.values ?? []).map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={id}
                  type="number"
                  step="any"
                  inputMode="decimal"
                  required
                  value={values[inp.name] ?? ""}
                  onChange={(e) => update(inp.name, e.target.value)}
                  className="rounded-lg bg-canvas px-3 py-2 text-ink shadow-ring outline-none transition focus:shadow-[inset_0_0_0_2px_theme(colors.accent.DEFAULT)]"
                />
              )}
              <code className="text-[0.7rem] font-mono text-ink-subtle">{inp.name}</code>
            </div>
          );
        })}
      </div>

      <div className="mt-6 flex items-center justify-end">
        <button
          type="submit"
          disabled={!complete || submitting}
          className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-accent-fg shadow-card transition hover:brightness-105 disabled:opacity-50"
        >
          {submitting ? "Predicting…" : "Predict"}
        </button>
      </div>
    </form>
  );
}
