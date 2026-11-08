
"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { UploadCloud, ShieldCheck } from "lucide-react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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

        <div className="mt-12 rounded-3xl border border-white/10 bg-white/5 p-10">
          <UploadCloud
            size={50}
            className="mx-auto text-cyan-400"
          />

          <h2 className="mt-6 text-2xl font-bold">
            Upload Image
          </h2>

          <p className="mt-3 text-sm text-slate-400">
            JPG or PNG, maximum 10 MB.
            Use only non-sensitive demonstration images.
          </p>

          <input
            type="file"
            accept="image/jpeg,image/png"
            aria-label="Select an image for detection"
            className="mx-auto mt-6 block max-w-full text-slate-300"
            onChange={(e) => {
              const selected = e.target.files?.[0];
              if (selected) selectFile(selected);
            }}
          />

          {preview && (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={preview}
              alt="Image selected for quick detection"
              className="mx-auto mt-8 max-h-[350px] max-w-full rounded-2xl"
            />
          )}

          {file && (
            <button
              onClick={() => void analyzeImage()}
              disabled={loading}
              className="mt-8 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-10 py-4 font-semibold disabled:opacity-50"
            >
              {loading ? "Analyzing image..." : "Analyze Image"}
            </button>
          )}

          {error && (
            <p role="alert" className="mt-6 text-red-400">
              {error}
            </p>
          )}
        </div>

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
