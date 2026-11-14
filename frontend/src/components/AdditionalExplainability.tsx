"use client";

import { useEffect, useRef, useState } from "react";
import { Download, Flame, Puzzle, Scale } from "lucide-react";
import { methodInPlainLanguage, methodReadingNote, resultInPlainLanguage } from "@/utils/xaiReaderCopy";
import {
  generateSavedExplanation,
  downloadForensicReport,
  getAnalysisDetails,
  getAnalysisImage,
  type AnalysisResponse,
  type ExplanationMethod,
} from "@/services/api";

const methods: { key: ExplanationMethod; label: string }[] = [
  {
    key: "gradcam",
    label: "Explain Grad-CAM regions",
  },
  {
    key: "lime",
    label: "Generate LIME",
  },
  {
    key: "shap",
    label: "Generate SHAP",
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
  const [downloading, setDownloading] = useState(false);

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

  const basicReady = Boolean(analysis?.assets?.overlay && analysis?.assets?.heatmap);
  const predictedClass = analysis?.prediction === "Real" ? "Real" : "Fake";
  const limeReady = analysis?.xai?.lime?.status === "completed" && Boolean(analysis?.assets?.lime);
  const shapReady = analysis?.xai?.shap?.status === "completed" && Boolean(analysis?.assets?.shap);
  const completeReady = basicReady && limeReady && shapReady;

  async function download() {
    if (!basicReady || busy || downloading) return;
    setDownloading(true);
    setError("");
    try {
      await downloadForensicReport(analysisId, token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF download failed.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-8">
      <h2 className="text-2xl font-bold">NeuralEdge AI Image Explanations</h2>
      <p className="mt-3 text-sm text-slate-400">
        See how the NeuralEdge AI model classified this picture and which image areas contributed to its assessment.
        You can request more detailed explanation pictures below.
      </p>
      {analysis && (
        <div className="mt-5 rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4">
          <p className="text-sm font-semibold text-cyan-200">Why NeuralEdge AI reached this result</p>
          <p className="mt-2 text-sm leading-6 text-slate-100">{resultInPlainLanguage(analysis)}</p>
        </div>
      )}
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
      <div className="mt-6 rounded-xl border border-white/10 bg-black/20 p-5 space-y-2">
        <h3 className="font-semibold">Report readiness</h3>
        <p className="text-sm text-slate-300">
          Grad-CAM: {basicReady ? "Ready" : "Loading"} · LIME: {limeReady ? "Ready" : "Not generated"} · SHAP: {shapReady ? "Ready" : "Not generated"}
        </p>
        <p className="text-sm text-slate-400">
          {completeReady
            ? "Complete explainability report: all three methods will be included."
            : "Basic forensic report: Grad-CAM is included. Generate LIME and/or SHAP above to add them to the PDF."}
        </p>
        {basicReady && !analysis?.xai?.gradcam && (
          <p className="text-xs text-amber-200">This older analysis has Grad-CAM images but no saved facial-region interpretation. Choose Explain Grad-CAM regions above to add one before downloading.</p>
        )}
        <button type="button" onClick={() => void download()}
          disabled={!basicReady || busy !== null || downloading}
          className="mt-3 inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-5 py-3 font-semibold text-white disabled:opacity-50">
          <Download size={18}/>{downloading ? "Preparing PDF..." : `Download ${completeReady ? "Complete" : "Basic"} PDF`}
        </button>
      </div>
      {error && <p role="alert" className="mt-4 text-sm text-red-400">{error}</p>}
      <div className="mt-6 space-y-6">
        {methods.map(({ key, label }) => {
          const meta = analysis?.xai?.[key];
          if (!meta) return null;
          const target = meta.target_label === "Real" || meta.target_label === "Fake"
            ? meta.target_label : "not recorded";
          const legacy = target !== predictedClass;
          const MethodIcon = key === "gradcam" ? Flame : key === "lime" ? Puzzle : Scale;
          const explanationNote = key === "gradcam"
            ? "Blue means lower relative CNN activation; cyan/green is moderate; yellow/red is stronger. The heatmap does not explain the stacking output directly."
            : `Red regions support ${target}; blue regions oppose ${target}. Color intensity represents relative contribution, not edited pixels.`;
          return (
            <article key={key} className="rounded-2xl border border-white/10 bg-black/20 p-5">
              <h3 className="flex items-center gap-2 font-semibold"><MethodIcon size={18} /> {label.replace("Generate ", "")}</h3>
              <p className="mt-2 text-sm text-slate-300">
                {key === "gradcam" ? "Where the image models were most responsive" : key === "lime" ? "Which sections helped or opposed the result" : "Which details supported or opposed the result"}
              </p>
              {legacy && (
                <p className="mt-2 text-sm text-amber-200">
                  This is a saved {target}-target explanation, not a {predictedClass}-target map.
                  Reanalyze the original image for a matching predicted-class explanation.
                </p>
              )}
              {urls[key] && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={urls[key]}
                  alt={key === "gradcam"
                    ? "Grad-CAM heatmap: blue lower activation and red higher relative activation"
                    : `${key.toUpperCase()} red contributions support ${target}; blue contributions oppose ${target}`}
                  className="mt-4 max-h-80 max-w-full rounded-xl"
                />
              )}
              <p className="mt-3 text-sm leading-6 text-cyan-100">
                {methodInPlainLanguage(key, meta, predictedClass)}
              </p>
              <details className="mt-4 rounded-lg border border-white/10 p-3 text-xs text-slate-400">
                <summary className="cursor-pointer font-semibold text-slate-300">Color guide and technical notes</summary>
                <p className="mt-2">{explanationNote}</p>
                <p className="mt-2">{methodReadingNote(key)}</p>
                {meta.interpretation?.narrative && (
                  <p className="mt-2">Saved research description: {meta.interpretation.narrative}</p>
                )}
                {meta.note && <p className="mt-2">{meta.note}</p>}
              </details>
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
