
"use client";

import { useEffect, useState } from "react";

import Sidebar from "@/components/Sidebar";
import AdditionalExplainability from "@/components/AdditionalExplainability";
import AnalysisActions from "@/components/AnalysisActions";
import ImageUploader from "@/components/ImageUploader";
import ImagePreview from "@/components/ImagePreview";

import { useAuth } from "@/components/auth/AuthProvider";

import {
  uploadEvidence,
  analyzeEvidence,
  getAnalysisImage,
  type AnalysisResponse,
} from "@/services/api";

export default function Analyze() {
  const { token } = useAuth();

  const [image, setImage] = useState<string | null>(null);

  const [result, setResult] =
    useState<AnalysisResponse | null>(null);

  const [heatmap, setHeatmap] = useState<string | null>(null);
  const [overlay, setOverlay] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  // Release temporary browser image URLs when no longer needed.
  useEffect(() => {
    return () => {
      if (image) URL.revokeObjectURL(image);
    };
  }, [image]);

  useEffect(() => {
    return () => {
      if (heatmap) URL.revokeObjectURL(heatmap);
    };
  }, [heatmap]);

  useEffect(() => {
    return () => {
      if (overlay) URL.revokeObjectURL(overlay);
    };
  }, [overlay]);

  async function handleUpload(file: File) {
    if (loading) return;

    setError("");
    setStatus("");
    setResult(null);
    setHeatmap(null);
    setOverlay(null);

    // This backend currently analyzes JPEG and PNG only.
    if (!["image/jpeg", "image/png"].includes(file.type)) {
      setError("Please select a JPG or PNG image.");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError("Maximum image size is 10 MB.");
      return;
    }

    if (!token) {
      setError("Please log in before analyzing an image.");
      return;
    }

    const previewUrl = URL.createObjectURL(file);
    setImage(previewUrl);
    setLoading(true);

    try {
      setStatus("Uploading image to the backend...");

      // STEP 1: Save the image as forensic evidence.
      const evidence = await uploadEvidence(file, token);

      setStatus("Running deepfake detection model...");

      // STEP 2: Run real TensorFlow inference.
      const analysis = await analyzeEvidence(
        evidence.id,
        token
      );

      setResult(analysis);

      setStatus("Downloading Grad-CAM explanations...");

      // STEP 3: Download heatmap and overlay.
      const [heatmapUrl, overlayUrl] = await Promise.all([
        getAnalysisImage(
          analysis.assets.heatmap.url,
          token
        ),
        getAnalysisImage(
          analysis.assets.overlay.url,
          token
        ),
      ]);

      setHeatmap(heatmapUrl);
      setOverlay(overlayUrl);

      setStatus("Analysis completed successfully.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Analysis failed. Please try again."
      );

      setStatus("");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen pt-32 lg:ml-[340px] px-8 pb-20 text-white">
      <Sidebar />

      <h1 className="text-5xl font-bold">
        Analyze Evidence
      </h1>

      <p className="mt-4 text-lg text-slate-400">
        Upload suspicious images for real AI forensic analysis.
      </p>

      <div className="mt-10 max-w-5xl space-y-10">

        <ImageUploader onUpload={handleUpload} />

        <ImagePreview image={image} />

        {loading && (
          <div
            role="status"
            className="rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-6"
          >
            <p className="animate-pulse text-cyan-300">
              {status}
            </p>
          </div>
        )}

        {error && (
          <div
            role="alert"
            className="rounded-2xl border border-red-400/30 bg-red-400/10 p-6 text-red-300"
          >
            {error}
          </div>
        )}

        {result && (
          <div className="space-y-8">

            <div className="rounded-3xl border border-white/10 bg-white/5 p-8">

              <h2 className="text-3xl font-bold">
                Detection Result
              </h2>

              <div className="mt-8 text-center">
                <p className="text-slate-400">
                  AI Classification
                </p>

                <h3
                  className={`mt-3 text-5xl font-bold ${
                    result.prediction === "Fake"
                      ? "text-red-400"
                      : "text-emerald-400"
                  }`}
                >
                  {result.prediction.toUpperCase()}
                </h3>
              </div>

              <div className="mt-8 grid gap-4 md:grid-cols-3">

                <Metric
                  label="Confidence"
                  value={`${(result.confidence * 100).toFixed(2)}%`}
                />

                <Metric
                  label="Prediction system"
                  value={result.model === "FourModelStacking" ? "Four-model stacking" : result.model}
                />

                <Metric
                  label="Threshold"
                  value={result.threshold.toFixed(3)}
                />

              </div>

              {result.members && (
                <div className="mt-6 grid gap-3 sm:grid-cols-2">
                  {Object.entries(result.members).map(([name, member]) => (
                    <div key={name} className="rounded-xl bg-black/20 p-4 text-sm">
                      <p className="font-semibold">{name}</p>
                      <p className="mt-1 text-slate-300">{member.prediction} · {(member.fake_probability * 100).toFixed(1)}% Fake score</p>
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-8 space-y-3">
                <p>
                  Fake probability:{" "}
                  {(result.fake_probability * 100).toFixed(2)}%
                </p>

                <p>
                  Real probability:{" "}
                  {(result.real_probability * 100).toFixed(2)}%
                </p>

                <p className="text-sm text-slate-400">
                  Inference mode: {result.mode}
                </p>

                <p className="break-all text-xs text-slate-500">
                  Analysis ID: {result.analysis_id}
                </p>
              </div>

              <p className="mt-6 text-sm text-amber-200">
                This prediction supports forensic triage.
                It is not proof that an image was manipulated.
              </p>
            </div>

            <div className="rounded-3xl border border-white/10 bg-white/5 p-8">

              <h2 className="text-2xl font-bold">
                Explainable AI — Grad-CAM
              </h2>

              <p className="mt-3 text-slate-400">
                Visualization of image regions that influenced
                the model prediction.
              </p>

              <div className="mt-8 grid gap-8 md:grid-cols-2">

                {heatmap && (
                  <div>
                    <h3 className="mb-4 font-semibold">
                      Grad-CAM Heatmap
                    </h3>

                    {/* Blob URL returned by authenticated fetch */}
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={heatmap}
                      alt="Grad-CAM activation heatmap"
                      className="w-full rounded-2xl"
                    />
                  </div>
                )}

                {overlay && (
                  <div>
                    <h3 className="mb-4 font-semibold">
                      Grad-CAM Overlay
                    </h3>

                    {/* Blob URL returned by authenticated fetch */}
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={overlay}
                      alt="Original image with Grad-CAM overlay"
                      className="w-full rounded-2xl"
                    />
                  </div>
                )}

              </div>

              <p className="mt-6 text-xs text-slate-400">
                {result.explanation.note}
              </p>
            </div>

            {token && result.model === "FourModelStacking" && (
              <AdditionalExplainability
                key={result.analysis_id}
                analysisId={result.analysis_id}
                token={token}
              />
            )}

            {token && <AnalysisActions key={result.analysis_id} token={token} analysisId={result.analysis_id} />}

          </div>
        )}

        {!loading && status && (
          <p className="text-sm text-emerald-400">
            {status}
          </p>
        )}

      </div>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl bg-black/30 p-5 text-center">
      <p className="text-sm text-slate-400">
        {label}
      </p>

      <p className="mt-2 break-words text-xl font-bold">
        {value}
      </p>
    </div>
  );
}
