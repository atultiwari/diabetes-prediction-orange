"use client";

import { ModelSchema } from "@/app/api-client";

interface Props {
  models: ModelSchema[];
  selectedId: string | null;
  onSelect: (modelId: string) => void;
  disabled?: boolean;
}

export function ModelPicker({ models, selectedId, onSelect, disabled }: Props) {
  const selected = models.find((m) => m.model_id === selectedId) ?? null;

  return (
    <div className="surface p-5">
      <label className="block text-sm font-medium text-ink-muted mb-2">Model</label>
      <select
        value={selectedId ?? ""}
        onChange={(e) => onSelect(e.target.value)}
        disabled={disabled || models.length === 0}
        className="w-full rounded-lg bg-canvas px-3 py-2.5 text-ink shadow-ring outline-none transition focus:shadow-[inset_0_0_0_2px_theme(colors.accent.DEFAULT)] disabled:opacity-60"
        aria-label="Select a model"
      >
        {models.length === 0 && <option value="">No models available</option>}
        {models.map((m) => (
          <option key={m.model_id} value={m.model_id}>
            {m.model_id}
          </option>
        ))}
      </select>
      {selected && (
        <p className="mt-2 text-xs text-ink-subtle">
          <span className="font-mono">{selected.algorithm}</span>
          <span className="mx-2 text-ink-subtle/60">·</span>
          <span>{selected.inputs.length} inputs</span>
          <span className="mx-2 text-ink-subtle/60">·</span>
          <span>{selected.source}</span>
        </p>
      )}
    </div>
  );
}
