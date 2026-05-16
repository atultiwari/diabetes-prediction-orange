"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  ModelSchema,
  PredictionResult,
  listModels,
  predict,
} from "@/app/api-client";
import { ModelPicker } from "./ModelPicker";
import { UploadTile } from "./UploadTile";
import { DynamicForm, FormValues } from "./DynamicForm";
import { ResultsPanel } from "./ResultsPanel";
import { SampleRowButton } from "./SampleRowButton";
import { BatchPredictPanel } from "./BatchPredictPanel";

interface Props {
  initialModels: ModelSchema[];
}

interface SampleHint {
  dataset_id: string;
  row_index: number;
  true_class: string | null;
}

function defaultFormValues(schema: ModelSchema): FormValues {
  const values: FormValues = {};
  for (const inp of schema.inputs) {
    values[inp.name] = "";
  }
  return values;
}

export function ModelDemo({ initialModels }: Props) {
  const [models, setModels] = useState<ModelSchema[]>(initialModels);
  const [selectedId, setSelectedId] = useState<string | null>(
    initialModels[0]?.model_id ?? null,
  );
  const [values, setValues] = useState<FormValues>(
    initialModels[0] ? defaultFormValues(initialModels[0]) : {},
  );
  const [submitting, setSubmitting] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [sampleHint, setSampleHint] = useState<SampleHint | null>(null);

  const selected = useMemo(
    () => models.find((m) => m.model_id === selectedId) ?? null,
    [models, selectedId],
  );

  useEffect(() => {
    if (!selected) return;
    setSwitching(true);
    setResult(null);
    setSubmitError(null);
    setSampleHint(null);
    setValues(defaultFormValues(selected));
    const t = setTimeout(() => setSwitching(false), 80);
    return () => clearTimeout(t);
    // selectedId is what really changes; selected derives from it
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  async function refreshModels(newSelectedId?: string) {
    try {
      const fresh = await listModels({ noStore: true });
      setModels(fresh);
      if (newSelectedId) {
        setSelectedId(newSelectedId);
      }
    } catch {
      // Soft-fail; user already saw the error elsewhere
    }
  }

  async function handleSubmit() {
    if (!selected) return;
    setSubmitting(true);
    setSubmitError(null);
    setResult(null);
    try {
      const payload: Record<string, string | number> = {};
      for (const inp of selected.inputs) {
        const raw = values[inp.name];
        if (inp.type === "continuous") {
          payload[inp.name] = Number(raw);
        } else {
          payload[inp.name] = raw;
        }
      }
      const r = await predict(selected.model_id, payload);
      setResult(r);
    } catch (e) {
      if (e instanceof ApiError) setSubmitError(e.message);
      else if (e instanceof Error) setSubmitError(e.message);
      else setSubmitError("Prediction failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (models.length === 0) {
    return (
      <div className="surface p-8 text-center">
        <h2 className="text-lg font-semibold">No models yet</h2>
        <p className="mt-2 text-sm text-ink-muted">
          Drop a <code className="font-mono">.pkcls</code> file into{" "}
          <code className="font-mono">backend/models/</code> and restart, or upload one now.
        </p>
        <div className="mx-auto mt-5 max-w-sm">
          <UploadTile
            onUploaded={(m) => {
              setModels([m]);
              setSelectedId(m.model_id);
            }}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr,1.25fr]">
        <div className="flex flex-col gap-4">
          <ModelPicker
            models={models}
            selectedId={selectedId}
            onSelect={setSelectedId}
            disabled={submitting}
          />
          <UploadTile
            onUploaded={(m) => {
              void refreshModels(m.model_id);
            }}
          />
        </div>

        <div className="flex flex-col gap-6">
          {selected && (switching ? (
            <div className="surface flex items-center gap-3 p-6 text-sm text-ink-muted">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
              Loading model…
            </div>
          ) : (
            <DynamicForm
              schema={selected}
              values={values}
              onChange={setValues}
              onSubmit={handleSubmit}
              submitting={submitting}
              toolbar={
                <SampleRowButton
                  schema={selected}
                  disabled={submitting}
                  onFilled={(filled, info) => {
                    setValues(filled);
                    setSampleHint(info);
                    setResult(null);
                    setSubmitError(null);
                  }}
                />
              }
              helperHint={
                sampleHint && (
                  <span>
                    Filled from{" "}
                    <span className="font-mono">{sampleHint.dataset_id}</span>{" "}
                    row {sampleHint.row_index}
                    {sampleHint.true_class && (
                      <>
                        {" "}
                        · true{" "}
                        <span className="font-mono">{sampleHint.true_class}</span>
                      </>
                    )}
                  </span>
                )
              }
            />
          ))}

          {submitError && (
            <div role="alert" className="surface border border-warn/40 bg-warn-soft p-4 text-sm text-warn-ink">
              {submitError}
            </div>
          )}

          {selected && result && <ResultsPanel schema={selected} result={result} />}
        </div>
      </div>

      {selected && !switching && <BatchPredictPanel schema={selected} />}
    </div>
  );
}
