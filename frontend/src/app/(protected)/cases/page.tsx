
"use client";

import CaseManager from "@/components/CaseManager";
import { useCallback, useEffect, useState } from "react";

import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/components/auth/AuthProvider";

import {
  getAnalysisHistory,
  type AnalysisResponse,
} from "@/services/api";

export default function CasesPage() {
  const { token } = useAuth();

  const [analyses, setAnalyses] = useState<AnalysisResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    if (!token) {
      setAnalyses([]);
      setLoading(false);
      setError("Please log in to view your investigations.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data = await getAnalysisHistory(token);
      setAnalyses(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load investigation history."
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

 useEffect(() => {
  if (!token) return;

  // Store the verified token in a local constant.
  const authToken: string = token;

  let cancelled = false;

  async function fetchHistory() {
    try {
      const data = await getAnalysisHistory(authToken);

      if (!cancelled) {
        setAnalyses(data);
        setError("");
      }
    } catch (err) {
      if (!cancelled) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load investigation history."
        );
      }
    } finally {
      if (!cancelled) {
        setLoading(false);
      }
    }
  }

  void fetchHistory();

  return () => {
    cancelled = true;
  };
}, [token]);

  return (
    <div className="min-h-screen pt-32 lg:ml-[340px] px-8 pb-20 text-white">
      <Sidebar />

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-4xl font-bold">
            Investigation History
          </h1>

          <p className="mt-3 text-slate-400">
            View previous deepfake detection analyses.
          </p>
        </div>

        <button
          onClick={() => void loadHistory()}
          disabled={loading}
          className="rounded-xl bg-cyan-600 px-5 py-3 font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>
 <div className="mt-10">
      <CaseManager />
    </div>
      {loading && (
        <p role="status" className="mt-10 text-cyan-400">
          Loading investigation history...
        </p>
      )}

      {error && (
        <div
          role="alert"
          className="mt-10 rounded-xl border border-red-500/30 bg-red-500/10 p-5 text-red-300"
        >
          {error}
        </div>
      )}

      {!loading && !error && analyses.length === 0 && (
        <div className="mt-10 rounded-3xl border border-white/10 bg-white/5 p-10">
          <h2 className="text-2xl font-bold">
            No Analyses Yet
          </h2>

          <p className="mt-3 text-slate-400">
            Upload and analyze an image to create
            your first investigation record.
          </p>
        </div>
      )}

      {!loading && analyses.length > 0 && (
        <div className="mt-10 space-y-6">

          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard
              label="Loaded Analyses"
              value={analyses.length}
            />

            <StatCard
              label="Classified Fake"
              value={
                analyses.filter(
                  (a) => a.prediction === "Fake"
                ).length
              }
            />

            <StatCard
              label="Classified Real"
              value={
                analyses.filter(
                  (a) => a.prediction === "Real"
                ).length
              }
            />
          </div>

          <div className="overflow-x-auto rounded-3xl border border-white/10 bg-white/5 p-6">

            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-white/10 text-sm text-slate-400">
                  <th className="p-4">Analysis ID</th>
                  <th className="p-4">Prediction</th>
                  <th className="p-4">Confidence</th>
                  <th className="p-4">Model</th>
                  <th className="p-4">Date</th>
                  <th className="p-4">Action</th>
                </tr>
              </thead>

              <tbody>
                {analyses.map((analysis) => (
                  <tr
                    key={analysis.analysis_id}
                    className="border-b border-white/5"
                  >
                    <td className="p-4 font-mono text-xs">
                      {analysis.analysis_id.slice(0, 8)}...
                    </td>

                    <td
                      className={`p-4 font-semibold ${
                        analysis.prediction === "Fake"
                          ? "text-red-400"
                          : "text-emerald-400"
                      }`}
                    >
                      {analysis.prediction}
                    </td>

                    <td className="p-4">
                      {(analysis.confidence * 100).toFixed(2)}%
                    </td>

                    <td className="p-4">
                      {analysis.model}
                    </td>

                    <td className="p-4 text-sm text-slate-400">
                      {new Date(
                        analysis.created_at
                      ).toLocaleString()}
                    </td>

                    <td className="p-4">
                      <button
                        onClick={() =>
                          setSelected(
                            selected === analysis.analysis_id
                              ? null
                              : analysis.analysis_id
                          )
                        }
                        aria-expanded={
                          selected === analysis.analysis_id
                        }
                        className="rounded-lg bg-cyan-600/20 px-4 py-2 text-sm text-cyan-300 hover:bg-cyan-600/30"
                      >
                        {selected === analysis.analysis_id
                          ? "Hide"
                          : "View"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {analyses
            .filter((a) => a.analysis_id === selected)
            .map((analysis) => (
              <div
                key={analysis.analysis_id}
                className="rounded-3xl border border-white/10 bg-white/5 p-8"
              >
                <h2 className="text-2xl font-bold">
                  Analysis Details
                </h2>

                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  <Detail
                    label="Prediction"
                    value={analysis.prediction}
                  />

                  <Detail
                    label="Confidence"
                    value={`${(
                      analysis.confidence * 100
                    ).toFixed(2)}%`}
                  />

                  <Detail
                    label="Fake Probability"
                    value={`${(
                      analysis.fake_probability * 100
                    ).toFixed(2)}%`}
                  />

                  <Detail
                    label="Real Probability"
                    value={`${(
                      analysis.real_probability * 100
                    ).toFixed(2)}%`}
                  />

                  <Detail
                    label="Model"
                    value={analysis.model}
                  />

                  <Detail
                    label="Threshold"
                    value={analysis.threshold.toFixed(3)}
                  />

                  <Detail
                    label="Inference Mode"
                    value={analysis.mode}
                  />

                  <Detail
                    label="Explainability"
                    value={analysis.explanation.method}
                  />
                </div>

                <div className="mt-6 space-y-3 text-xs text-slate-400">
                  <p className="break-all">
                    Analysis ID: {analysis.analysis_id}
                  </p>

                  <p className="break-all">
                    Evidence ID: {analysis.evidence_id}
                  </p>

                  <p className="break-all">
                    Image SHA-256: {analysis.image_sha256}
                  </p>
                </div>

                <p className="mt-6 text-sm text-amber-200">
                  AI predictions support forensic
                  investigation but do not constitute
                  proof of image manipulation.
                </p>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
      <p className="text-sm text-slate-400">
        {label}
      </p>

      <p className="mt-3 text-3xl font-bold">
        {value}
      </p>
    </div>
  );
}

function Detail({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-black/20 p-4">
      <p className="text-sm text-slate-400">
        {label}
      </p>

      <p className="mt-2 break-words font-semibold">
        {value}
      </p>
    </div>
  );
}
