"use client";

import { useEffect, useRef, useState } from "react";
import {
  generateSavedExplanation,
  getAnalysisDetails,
  getAnalysisImage,
  type AnalysisResponse,
  type ExplanationMethod,
} from "@/services/api";

const methods: { key: ExplanationMethod; label: string; note: string }[] = [
  {
    key: "gradcam",
    label: "Explain Grad-CAM regions",
    note: "Identifies prominent facial regions in the four-CNN Grad-CAM average.",
  },
  {
    key: "lime",
    label: "Generate LIME",
    note: "May take substantial time; explains the four-model stacking Fake score.",
  },
  {
    key: "shap",
    label: "Generate SHAP",
    note: "May be slower than LIME; uses the same stacking model and a blur reference.",
  },
];

export default function AdditionalExplainability({
  analysisId,
  token,
}: {
  analysisId: string;
  token: string;
}) {
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [urls, setUrls] = useState<Record<string, string>>({});
  const urlRegistry = useRef<Record<string, string>>({});
  const [busy, setBusy] = useState<ExplanationMethod | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const current = await getAnalysisDetails(analysisId, token);
        if (!cancelled) setAnalysis(current);
      } catch {
        if (!cancelled) setError("Cannot load previous explanations.");
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [analysisId, token]);

  useEffect(() => {
    // Release all URLs only when the panel unmounts (not after each update).
    const registry = urlRegistry.current;
    return () => {
      for (const url of Object.values(registry)) URL.revokeObjectURL(url);
    };
  }, []);

  function rememberUrl(method: string, url: string) {
    const previous = urlRegistry.current[method];
    if (previous) URL.revokeObjectURL(previous);
    urlRegistry.current[method] = url;
    setUrls({ ...urlRegistry.current });
  }

  async function generate(method: ExplanationMethod) {
    if (busy) return;
    setBusy(method);
    setError("");
    try {
      await generateSavedExplanation(analysisId, method, token);
      const updated = await getAnalysisDetails(analysisId, token);
      const asset = updated.assets[method];
      if (asset) {
        const url = await getAnalysisImage(asset.url, token);
        rememberUrl(method, url);
      }
      setAnalysis(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Explanation generation failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-8">
      <h2 className="text-2xl font-bold">Additional AI Explanations</h2>
      <p className="mt-3 text-sm text-slate-400">
        Explanations are generated for this specific evidence, on demand.
        A highlighted facial feature is not proof that it was manipulated.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        {methods.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => void generate(key)}
            disabled={busy !== null || !!analysis?.xai?.[key]}
            className="rounded-xl bg-cyan-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy === key ? `Generating ${key.toUpperCase()}...` : analysis?.xai?.[key] ? `${key.toUpperCase()} ready` : label}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="mt-4 text-sm text-red-400">{error}</p>}
      <div className="mt-6 space-y-6">
        {methods.map(({ key, label, note }) => {
          const meta = analysis?.xai?.[key];
          if (!meta) return null;
          return (
            <article key={key} className="rounded-2xl border border-white/10 bg-black/20 p-5">
              <h3 className="font-semibold">{label.replace("Generate ", "")}</h3>
              <p className="mt-2 text-sm text-slate-400">{note}</p>
              {urls[key] && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={urls[key]}
                  alt={`${key.toUpperCase()} red positive Fake-score contribution; blue negative Fake-score contribution`}
                  className="mt-4 max-h-80 max-w-full rounded-xl"
                />
              )}
              <p className="mt-3 text-sm text-cyan-200">
                {meta.interpretation.narrative}
              </p>
              <p className="mt-3 text-xs text-slate-400">{meta.note}</p>
              {analysis?.assets?.[key] && !urls[key] && (
                <button
                  type="button"
                  onClick={() => {
                    const asset = analysis.assets[key];
                    if (!asset) return;
                    void getAnalysisImage(asset.url, token)
                      .then((url) => rememberUrl(key, url))
                      .catch(() => setError(`Unable to load ${key.toUpperCase()} image.`));
                  }}
                  className="mt-3 text-sm text-cyan-400 underline"
                >
                  Load saved explanation image
                </button>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
