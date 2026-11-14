
"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { UploadCloud, ShieldCheck, Image as ImageIcon, X, FileCheck2 } from "lucide-react";

const API_URL = ""; // Same-origin Next.js /api rewrite.

type QuickResult = {
  prediction: "Real" | "Fake";
  confidence: number;
  fake_probability: number;
  real_probability: number;
  threshold: number;
  model: string;
  note: string;
};

export default function DetectPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<QuickResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const previewUrlRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    };
  }, []);

  function selectFile(selected: File) {
    setError("");
    setResult(null);
    setFile(null);
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = null;
    setPreview(null);

    if (!["image/jpeg", "image/png"].includes(selected.type)) {
      setError("Please select a JPG or PNG image.");
      return;
    }

    if (selected.size > 10 * 1024 * 1024) {
      setError("Maximum guest image size is 10 MB.");
      return;
    }

    setFile(selected);

    const url = URL.createObjectURL(selected);
    previewUrlRef.current = url;
    setPreview(url);
  }

  function clearFile() {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = null;
    if (inputRef.current) inputRef.current.value = "";
    setPreview(null); setFile(null); setResult(null); setError("");
  }

  async function analyzeImage() {
    if (!file || loading) return;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        `${API_URL}/api/quick-detect`,
        {
          method: "POST",
          body: formData,
          cache: "no-store",
        }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => null);

        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : `Detection failed (HTTP ${response.status}).`
        );
      }

      const data = (await response.json()) as QuickResult;
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to analyze the image."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-6 pb-20 pt-36 text-white">
      <div className="mx-auto max-w-4xl text-center">

        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-5 py-2 text-cyan-300">
          <ShieldCheck size={18} />
          Quick Deepfake Detection
        </div>

        <h1 className="mt-10 text-5xl font-bold">
          Check Image Authenticity
        </h1>

        <p className="mt-5 text-lg text-slate-400">
          Try our AI-based image screening without creating
          an investigator account.
        </p>

        <section aria-labelledby="guest-upload-title" className="mt-12 rounded-3xl border border-white/10 bg-white/5 p-5 text-left shadow-xl sm:p-10">
          <div className="text-center"><span className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-400/20 bg-cyan-400/10"><UploadCloud size={32} className="text-cyan-400" /></span><h2 id="guest-upload-title" className="mt-5 text-2xl font-bold">Upload an image</h2><p className="mt-2 text-sm text-slate-400">JPG or PNG · Up to 10 MB · Non-sensitive demonstration images only</p></div>
          <div onDragEnter={(e) => {e.preventDefault();if(!loading) setDragging(true);}} onDragOver={e => {e.preventDefault();}} onDragLeave={e => {e.preventDefault();setDragging(false);}} onDrop={e => {e.preventDefault();setDragging(false);if(!loading && e.dataTransfer.files[0]) selectFile(e.dataTransfer.files[0]);}}
            className={`mt-7 rounded-2xl border-2 border-dashed px-5 py-10 text-center transition ${dragging ? "border-cyan-300 bg-cyan-400/10" : "border-cyan-400/25 bg-[#0b1224]"}`}>
            <ImageIcon size={36} className="mx-auto text-cyan-300" aria-hidden="true"/>
            <p className="mt-4 text-base font-semibold">Drag and drop your image here</p><p className="mt-2 text-sm text-slate-400">or select a photo from your device</p>
            <input ref={inputRef} type="file" accept="image/jpeg,image/png" className="sr-only" aria-label="Select JPG or PNG image" onChange={e => {const selected=e.currentTarget.files?.[0];if(selected) selectFile(selected);}}/>
            <button type="button" disabled={loading} onClick={() => inputRef.current?.click()} className="mt-5 rounded-xl bg-cyan-600 px-6 py-3 font-semibold text-white shadow-lg shadow-cyan-900/25 transition hover:bg-cyan-500 disabled:opacity-50">Browse files</button>
            <p className="mt-4 text-xs text-slate-500">Accepted formats: JPEG, JPG, PNG. Maximum file size: 10 MB.</p>
          </div>
          {file && <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-4"><div className="flex min-w-0 items-center gap-3"><FileCheck2 size={24} className="shrink-0 text-cyan-300"/><div className="min-w-0"><p className="max-w-[360px] truncate text-sm font-semibold" title={file.name}>{file.name}</p><p className="mt-1 text-xs text-slate-400">{(file.size / 1024 / 1024).toFixed(2)} MB · Ready to analyze</p></div></div><button type="button" disabled={loading} onClick={clearFile} aria-label="Remove selected image" className="rounded-lg border border-white/15 p-2 text-slate-300 hover:bg-white/10 disabled:opacity-50"><X size={18}/></button></div>}
          {preview && <div className="mt-6 rounded-xl border border-white/10 bg-black/30 p-3 text-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="Preview of selected image" className="mx-auto max-h-[340px] max-w-full rounded-lg object-contain"/>
          </div>}
          {error && <p role="alert" className="mt-5 rounded-xl border border-red-400/25 bg-red-500/10 p-4 text-sm text-red-300">{error}</p>}
          {file && <button type="button" onClick={() => void analyzeImage()} disabled={loading} className="mt-6 w-full rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-7 py-4 font-bold text-white shadow-lg disabled:opacity-50">{loading ? "NeuralEdge AI is analyzing..." : "Analyze selected image"}</button>}
        </section>

        {result && (
          <div className="mt-10 rounded-3xl border border-white/10 bg-white/5 p-10">

            <h2 className="text-2xl font-bold">
              AI Detection Result
            </h2>

            <h3
              className={`mt-6 text-4xl font-bold ${
                result.prediction === "Fake"
                  ? "text-red-400"
                  : "text-emerald-400"
              }`}
            >
              {result.prediction.toUpperCase()}
            </h3>

            <div className="mt-8 grid gap-5 md:grid-cols-2">
              <ResultCard
                title="Model Confidence"
                value={`${(result.confidence * 100).toFixed(2)}%`}
              />

              <ResultCard
                title="Model"
                value={result.model}
              />

              <ResultCard
                title="Fake Probability"
                value={`${(result.fake_probability * 100).toFixed(2)}%`}
              />

              <ResultCard
                title="Real Probability"
                value={`${(result.real_probability * 100).toFixed(2)}%`}
              />
            </div>

            <p className="mt-7 text-sm text-amber-200">
              {result.note}
            </p>

            <div className="mt-8 rounded-xl bg-black/20 p-6">
              <h4 className="text-lg font-semibold">
                Need a complete forensic investigation?
              </h4>

              <p className="mt-3 text-slate-400">
                Investigator accounts provide Grad-CAM
                explanations, evidence history, case management,
                and PDF forensic reports.
              </p>

              <Link
                href="/register"
                className="mt-5 inline-block rounded-xl bg-cyan-600 px-6 py-3 font-semibold text-white"
              >
                Register as Investigator
              </Link>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

function ResultCard({
  title,
  value,
}: {
  title: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-black/20 p-5">
      <p className="text-sm text-slate-400">
        {title}
      </p>

      <h3 className="mt-2 text-2xl font-bold">
        {value}
      </h3>
    </div>
  );
}
