"use client";

import { useRef, useState } from "react";
import { ApiError, ModelSchema, uploadModel } from "@/app/api-client";

interface Props {
  onUploaded: (model: ModelSchema) => void;
}

export function UploadTile({ onUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const schema = await uploadModel(file);
      onUploaded(schema);
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else if (e instanceof Error) setError(e.message);
      else setError("Upload failed.");
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="surface p-5">
      <p className="text-sm font-medium text-ink">
        Have your own <span className="font-mono text-ink-muted">.pkcls</span>? Upload it.
      </p>
      <p className="mt-1 text-xs text-ink-subtle">Max 50&nbsp;MB. Orange3 classifiers only.</p>
      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-canvas transition hover:bg-ink/90 disabled:opacity-60"
        >
          {busy ? "Uploading…" : "Choose .pkcls"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".pkcls"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleFile(f);
          }}
        />
        {error && (
          <span role="alert" className="text-xs text-warn-ink">
            {error}
          </span>
        )}
      </div>
    </div>
  );
}
