
"use client";

import CaseManager from "@/components/CaseManager";
import EvidenceThumbnail from "@/components/EvidenceThumbnail";
import { Fragment, useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";

import {
  getAnalysisHistory,
  permanentlyDeleteAnalysis,
  getAnalysisDetails,
  downloadForensicReport,
  type AnalysisResponse,
} from "@/services/api";

export default function CasesPage() {
  const { token } = useAuth();

  const [analyses, setAnalyses] = useState<AnalysisResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [viewed, setViewed] = useState<AnalysisResponse | null>(null);
  const [detailBusy, setDetailBusy] = useState<string | null>(null);
  const [downloadBusy, setDownloadBusy] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function deleteSavedAnalysis(id: string) {
    if (!token || deletingId) return;
    if (!window.confirm("PERMANENTLY delete this analysis, its explanation images, and all case associations? Uploaded original evidence is retained.")) return;
    setDeletingId(id);
    setError("");
    try {
      await permanentlyDeleteAnalysis(token, id);
      setAnalyses((old) => old.filter((a) => a.analysis_id !== id));
      setSelected((previous) => previous === id ? null : previous);
      setViewed((old) => old?.analysis_id === id ? null : old);
      window.dispatchEvent(new Event("neuraledge-data-changed"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    } finally { setDeletingId(null); }
  }

  async function viewAnalysis(id: string) {
    if (!token) return;
    if (selected === id) {setSelected(null);setViewed(null);return;}
    setSelected(id);setViewed(null);setDetailBusy(id);setError("");
    try { const data = await getAnalysisDetails(id, token); setViewed(data); }
    catch(err) {setError(err instanceof Error ? err.message : "Unable to open analysis details.");}
    finally {setDetailBusy(null);}
  }
  async function downloadAnalysis(id: string) {
    if (!token) return;
    setDownloadBusy(true);setError("");
    try { await downloadForensicReport(id,token); }
    catch(err) {setError(err instanceof Error ? err.message : "PDF download failed.");}
    finally {setDownloadBusy(false);}
  }

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

  useEffect(() => {
    const refresh = () => { void loadHistory(); };
    window.addEventListener("neuraledge-data-changed", refresh);
    return () => window.removeEventListener("neuraledge-data-changed", refresh);
  }, [loadHistory]);

  return (
    <div className="min-h-screen pt-8  px-8 pb-20 text-white">


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
                  <Fragment key={analysis.analysis_id}>
                  <tr
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
                      {analysis.model === "FourModelStacking" ? "Four-model stacking" : analysis.model}
                    </td>

                    <td className="p-4 text-sm text-slate-400">
                      {new Date(
                        analysis.created_at
                      ).toLocaleString()}
                    </td>

                    <td className="p-4">
                      <button
                        type="button"
                        onClick={() => void viewAnalysis(analysis.analysis_id)}
                        aria-expanded={
                          selected === analysis.analysis_id
                        }
                        className="rounded-lg bg-cyan-600/20 px-4 py-2 text-sm text-cyan-300 hover:bg-cyan-600/30"
                      >
                        {selected === analysis.analysis_id
                          ? "Hide details"
                          : "View details"}
                      </button>
                      <button type="button" disabled={deletingId !== null}
                        onClick={() => void deleteSavedAnalysis(analysis.analysis_id)}
                        className="ml-2 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-300 disabled:opacity-50">
                        {deletingId === analysis.analysis_id ? "Deleting..." : "Delete"}
                      </button>
                    </td>
                  </tr>
                  {selected === analysis.analysis_id && <tr className="border-b border-cyan-400/20 bg-cyan-500/5"><td colSpan={6} className="p-5 sm:p-7">
                    {detailBusy === analysis.analysis_id ? <p role="status" className="text-cyan-300">Loading analysis details...</p> : viewed?.analysis_id === analysis.analysis_id ? <div className="space-y-5">
                      <div className="flex flex-wrap items-center gap-4"><EvidenceThumbnail evidenceId={viewed.evidence_id} token={token!}/><div><h3 className="text-lg font-semibold text-white">Saved analysis details</h3><p className="mt-1 text-sm text-slate-400">Analyzed {new Date(viewed.created_at).toLocaleString()}</p><p className="mt-1 break-all font-mono text-xs text-slate-500">{viewed.analysis_id}</p></div></div>
                      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Detail label="Classification" value={viewed.prediction}/><Detail label="Fake-category score" value={`${(viewed.fake_probability*100).toFixed(2)}%`}/><Detail label="Decision threshold" value={viewed.threshold.toFixed(2)}/><Detail label="Model" value={viewed.model === "FourModelStacking" ? "Four-model stacking" : viewed.model}/></div>
                      <div className="rounded-xl border border-white/10 bg-black/20 p-4"><h4 className="font-semibold">Saved explanations</h4><p className="mt-2 text-sm text-slate-300">Grad-CAM: {viewed.xai?.gradcam?.status === "completed" ? "Available" : "Original heatmap saved"} · LIME: {viewed.xai?.lime?.status === "completed" ? "Available" : "Not generated"} · SHAP: {viewed.xai?.shap?.status === "completed" ? "Available" : "Not generated"}</p><p className="mt-3 break-all text-xs text-slate-500">Evidence SHA-256: {viewed.image_sha256}</p></div>
                      <div className="flex flex-wrap gap-3"><button type="button" disabled={downloadBusy} onClick={() => void downloadAnalysis(viewed.analysis_id)} className="rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold disabled:opacity-50">{downloadBusy ? "Generating..." : "Download PDF"}</button><button type="button" onClick={() => {setSelected(null);setViewed(null);}} className="rounded-xl border border-white/20 px-4 py-2.5 text-sm">Close details</button></div>
                      <p className="text-xs text-amber-200">NeuralEdge AI provides screening support, not proof of authenticity or manipulation.</p>
                    </div> : <p role="alert" className="text-amber-200">Details are unavailable. Please retry View details.</p>}
                  </td></tr>}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>

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
