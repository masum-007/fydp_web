"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Download, RefreshCw } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  getAnalysisHistory, getAnalysisCaseLinks, downloadForensicReport,
  type AnalysisResponse, type AnalysisCaseLinks,
} from "@/services/api";

export default function ReportsPage() {
  const { token } = useAuth();
  const [analyses, setAnalyses] = useState<AnalysisResponse[]>([]);
  const [links, setLinks] = useState<AnalysisCaseLinks>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);
  useEffect(() => {
    if (!token) return;
    const authToken = token;
    let cancelled = false;
    async function load() {
      try {
        const [items, map] = await Promise.all([
          getAnalysisHistory(authToken, 100, 0), getAnalysisCaseLinks(authToken),
        ]);
        if (!cancelled) { setAnalyses(items); setLinks(map); setError(""); }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load reports.");
      } finally { if (!cancelled) setLoading(false); }
    }
    void load();
    return () => { cancelled = true; };
  }, [token, refresh]);
  async function download(id: string) {
    if (!token) return;
    setBusyId(id); setError("");
    try { await downloadForensicReport(id, token); }
    catch (err) { setError(err instanceof Error ? err.message : "PDF download failed."); }
    finally { setBusyId(null); }
  }
  return <div className="min-h-screen px-8 pb-20 pt-32 text-white lg:ml-[340px]">
    <Sidebar />
    <div className="flex flex-wrap items-center justify-between gap-5">
      <div><h1 className="text-4xl font-bold md:text-5xl">Forensic Reports</h1><p className="mt-4 text-slate-400">Generate reports from your saved analyses and cases.</p></div>
      <button type="button" disabled={loading} onClick={() => { setLoading(true); setRefresh(v => v + 1); }} className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-3 disabled:opacity-50"><RefreshCw size={18}/> Refresh</button>
    </div>
    <p className="mt-7 rounded-xl border border-white/10 bg-white/5 p-5 text-sm text-slate-300">Reports are generated on demand. SHAP and LIME appear in PDFs only when saved for that analysis. Case titles below reflect current assignments; PDF contents are unchanged in this release.</p>
    {loading && <p role="status" className="mt-7 text-cyan-300">Loading saved analyses...</p>}
    {error && <p role="alert" className="mt-7 text-red-300">{error}</p>}
    {!loading && analyses.length === 0 && !error && <p className="mt-8">No analyses saved yet. <Link className="text-cyan-300 underline" href="/analyze">Analyze an image</Link></p>}
    {!loading && analyses.length > 0 && <section className="mt-8 overflow-x-auto rounded-3xl border border-white/10 bg-white/5 p-6">
      <table className="w-full text-left text-sm"><thead><tr className="border-b border-white/10 text-slate-400"><th className="p-3">Analysis</th><th className="p-3">Prediction</th><th className="p-3">Model</th><th className="p-3">Case title</th><th className="p-3">Date</th><th className="p-3">Report</th></tr></thead>
        <tbody>{analyses.map((a) => <tr key={a.analysis_id} className="border-b border-white/5"><td className="p-3 font-mono text-xs">{a.analysis_id.slice(0, 8)}...</td><td className="p-3">{a.prediction}</td><td className="p-3">{a.model === "FourModelStacking" ? "Four-model stacking (4 CNNs)" : a.model}</td><td className="p-3">{links[a.analysis_id]?.length ? links[a.analysis_id].map(c => c.title).join(", ") : "Not assigned"}</td><td className="p-3">{new Date(a.created_at).toLocaleString()}</td><td className="p-3"><button type="button" disabled={busyId !== null} onClick={() => void download(a.analysis_id)} className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-3 py-2 disabled:opacity-50"><Download size={16}/>{busyId === a.analysis_id ? "Generating..." : "Download PDF"}</button></td></tr>)}</tbody>
      </table>
    </section>}
    <p className="mt-4 text-xs text-slate-500">Up to 100 recent analyses shown. AI results require independent verification.</p>
  </div>;
}
