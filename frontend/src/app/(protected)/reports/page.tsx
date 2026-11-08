
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Download, FileText, RefreshCw } from "lucide-react";

import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/components/auth/AuthProvider";

import {
  getAnalysisHistory,
  downloadForensicReport,
  type AnalysisResponse,
} from "@/services/api";

export default function ReportsPage() {
  const { token } = useAuth();

  const [analyses, setAnalyses] =
    useState<AnalysisResponse[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshCount, setRefreshCount] = useState(0);
  const [generatingId, setGeneratingId] =
    useState<string | null>(null);

  useEffect(() => {
    if (!token) return;

    const authToken: string = token;
    let cancelled = false;

    async function loadReports() {
      try {
        const data = await getAnalysisHistory(
          authToken,
          50,
          0
        );

        if (!cancelled) {
          setAnalyses(data);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load analyses."
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadReports();

    return () => {
      cancelled = true;
    };
  }, [token, refreshCount]);

  async function handleDownload(analysisId: string) {
    if (!token) {
      setError("Please log in again.");
      return;
    }

    setGeneratingId(analysisId);
    setError("");

    try {
      await downloadForensicReport(analysisId, token);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Report download failed."
      );
    } finally {
      setGeneratingId(null);
    }
  }

  return (
    <div className="min-h-screen pt-32 lg:ml-[340px] px-8 pb-20 text-white">
      <Sidebar />

      <div className="flex flex-wrap items-start justify-between gap-6">

        <div>
          <h1 className="text-4xl font-bold md:text-5xl">
            Forensic Reports
          </h1>

          <p className="mt-4 text-lg text-slate-400">
            Generate AI-assisted forensic triage reports
            from your saved analyses.
          </p>
        </div>

        <button
          onClick={() => {
            setLoading(true);
            setRefreshCount((count) => count + 1);
          }}
          disabled={loading || !token}
          className="flex items-center gap-2 rounded-xl bg-cyan-600 px-5 py-3 font-semibold disabled:opacity-50"
        >
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

      <div className="mt-8 rounded-2xl border border-cyan-400/20 bg-cyan-400/10 p-5">
        <p className="text-sm text-cyan-200">
          Reports are generated on demand using existing
          verified evidence and analysis records.
          They are not yet stored as permanent report records.
        </p>
      </div>

      {loading && (
        <p role="status" className="mt-8 text-cyan-300">
          Loading available analyses...
        </p>
      )}

      {error && (
        <div
          role="alert"
          className="mt-8 rounded-xl border border-red-400/30 bg-red-400/10 p-5 text-red-300"
        >
          {error}
        </div>
      )}

      {!loading && !error && analyses.length === 0 && token && (
        <div className="mt-10 rounded-3xl border border-white/10 bg-white/5 p-10">
          <FileText size={32} className="text-cyan-400" />

          <h2 className="mt-5 text-2xl font-bold">
            No Analyses Available
          </h2>

          <p className="mt-3 text-slate-400">
            Complete an image analysis before generating
            your first forensic report.
          </p>

          <Link
            href="/analyze"
            className="mt-5 inline-block text-cyan-400 hover:underline"
          >
            Analyze an image
          </Link>
        </div>
      )}

      {!loading && analyses.length > 0 && (
        <div className="mt-10 overflow-x-auto rounded-3xl border border-white/10 bg-white/5 p-6">

          <h2 className="mb-6 text-2xl font-bold">
            Available Analyses
          </h2>

          <table className="w-full text-left">

            <thead>
              <tr className="border-b border-white/10 text-sm text-slate-400">
                <th className="p-4">Analysis ID</th>
                <th className="p-4">Prediction</th>
                <th className="p-4">Confidence</th>
                <th className="p-4">Model</th>
                <th className="p-4">Date</th>
                <th className="p-4">Report</th>
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
                        void handleDownload(analysis.analysis_id)
                      }
                      disabled={generatingId !== null}
                      className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2 text-sm font-semibold disabled:opacity-50"
                    >
                      <Download size={16} />

                      {generatingId === analysis.analysis_id
                        ? "Generating..."
                        : "Download PDF"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

        </div>
      )}

      <p className="mt-6 text-xs text-slate-500">
        Showing up to 50 recent analyses.
        Model predictions support human investigation
        and do not independently prove manipulation.
      </p>
    </div>
  );
}
