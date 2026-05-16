import { listModels, API_BASE_URL, ModelSchema } from "./api-client";
import { ModelDemo } from "@/components/ModelDemo";

export const dynamic = "force-dynamic";

interface InitialState {
  models: ModelSchema[];
  error: string | null;
}

async function loadInitial(): Promise<InitialState> {
  try {
    const models = await listModels({ noStore: true });
    return { models, error: null };
  } catch (e) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return { models: [], error: message };
  }
}

export default async function HomePage() {
  const { models, error } = await loadInitial();

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-1">
        <span className="text-xs uppercase tracking-[0.2em] text-ink-subtle">
          Orange Data Mining
        </span>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Model Demo
        </h1>
        <p className="text-sm text-ink-muted">
          Demo of Orange-trained models. Pick a model, fill the form, see the prediction.
        </p>
      </header>

      {error ? (
        <div className="surface border border-warn/40 p-6 bg-warn-soft">
          <h2 className="text-base font-semibold text-warn-ink">
            Cannot reach backend
          </h2>
          <p className="mt-2 text-sm text-ink-muted">
            Tried <code className="font-mono">{API_BASE_URL}</code>. Check that the
            backend is running and that{" "}
            <code className="font-mono">NEXT_PUBLIC_API_BASE_URL</code> and
            <code className="font-mono"> FRONTEND_ORIGIN</code> are set correctly.
          </p>
          <p className="mt-2 text-xs text-ink-subtle">Error: {error}</p>
        </div>
      ) : (
        <ModelDemo initialModels={models} />
      )}
    </div>
  );
}
