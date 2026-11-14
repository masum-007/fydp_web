"use client";

import {useEffect, useState} from "react";
import Link from "next/link";
import {Download, RefreshCw, Search} from "lucide-react";
import EvidenceThumbnail from "@/components/EvidenceThumbnail";
import {useAuth} from "@/components/auth/AuthProvider";
import {getAnalysisHistory, getAnalysisCaseLinks, downloadForensicReport, type AnalysisResponse, type AnalysisCaseLinks} from "@/services/api";

export default function ReportsPage() {
  const {token} = useAuth();
  const [analyses, setAnalyses] = useState<AnalysisResponse[]>([]);
  const [links, setLinks] = useState<AnalysisCaseLinks>({});
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all"|"Fake"|"Real">("all");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;
  useEffect(() => {
    if (!token) return;
    let alive = true;
    void Promise.all([getAnalysisHistory(token, 100, 0), getAnalysisCaseLinks(token)]).then(([items, map]) => {
      if (alive) {setAnalyses(items);setLinks(map);setError("");}
    }).catch(err => {if(alive) setError(err instanceof Error ? err.message : "Unable to load reports.");})
      .finally(() => {if(alive) setLoading(false);});
    return () => {alive = false;};
  }, [token, refresh]);
  const shown = analyses.filter(a => {
    const query = search.trim().toLowerCase();
    return (filter === "all" || a.prediction === filter) && (!query ||
      [a.analysis_id, a.evidence_id, ...(links[a.analysis_id] ?? []).map(l=>l.title)].some(v => v.toLowerCase().includes(query)));
  });
  const totalPages = Math.max(1, Math.ceil(shown.length / PAGE_SIZE));
  const visiblePage = Math.min(page, totalPages - 1);
  const visibleRows = shown.slice(visiblePage * PAGE_SIZE, (visiblePage + 1) * PAGE_SIZE);
  async function download(id: string) {
    if (!token) return;
    setBusy(id);setError("");
    try {await downloadForensicReport(id,token);} catch(err) {setError(err instanceof Error?err.message:"Report download failed.");} finally {setBusy(null);}
  }
  return <main className="min-h-screen px-5 pb-20 pt-8 text-white sm:px-8">
    <div className="flex flex-wrap items-center justify-between gap-5"><div><h1 className="text-4xl font-bold md:text-5xl">Forensic Reports</h1><p className="mt-3 text-slate-400">Find past analyses using their preview image, case assignment or ID.</p></div><button type="button" disabled={loading} onClick={() => {setLoading(true);setRefresh(n=>n+1);}} className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-3 font-semibold disabled:opacity-50"><RefreshCw size={18}/> Refresh</button></div>
    <p className="mt-7 rounded-xl border border-white/10 bg-white/5 p-5 text-sm text-slate-300">Reports use your approved NeuralEdge AI forensic layout. Grad-CAM appears with each analysis; LIME and SHAP are included only when previously generated.</p>
    <div className="mt-6 flex flex-wrap gap-3"><label className="flex min-w-[240px] flex-1 items-center gap-2 rounded-xl border border-white/15 bg-[#0b1020] px-4"><Search size={18} className="text-cyan-400"/><input value={search} onChange={e=>{setSearch(e.target.value);setPage(0);}} aria-label="Search reports" placeholder="Search analysis ID, evidence ID or case" className="w-full bg-transparent py-3 text-sm outline-none placeholder:text-slate-500"/></label><select value={filter} onChange={e=>{setFilter(e.target.value as "all"|"Fake"|"Real");setPage(0);}} aria-label="Filter reports by classification" className="rounded-xl border border-white/15 bg-[#111a2b] px-4 py-3 text-sm"><option value="all">All results</option><option value="Fake">Fake</option><option value="Real">Real</option></select></div>
    {loading && <p role="status" className="mt-7 text-cyan-300">Loading reports...</p>}
    {error && <p role="alert" className="mt-7 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</p>}
    {!loading && !error && analyses.length === 0 && <p className="mt-8">No analyses yet. <Link href="/analyze" className="text-cyan-300 underline">Analyze an image</Link></p>}
    {!loading && analyses.length>0 && shown.length===0 && <p className="mt-7 text-slate-400">No reports match your search.</p>}
    {!loading && shown.length>0 && <section className="mt-7 overflow-x-auto rounded-3xl border border-white/10 bg-white/5 p-4 sm:p-6"><table className="w-full min-w-[760px] text-left text-sm"><thead><tr className="border-b border-white/10 text-slate-400">{["Evidence", "Analysis", "Result", "Model", "Case title", "Date", "Report"].map(col=><th key={col} className="px-3 py-3">{col}</th>)}</tr></thead><tbody>{visibleRows.map(a => <tr key={a.analysis_id} className="border-b border-white/5 align-middle"><td className="px-3 py-3">{token && <EvidenceThumbnail evidenceId={a.evidence_id} token={token} size="compact"/>}</td><td className="px-3 py-3 font-mono text-xs" title={a.analysis_id}>{a.analysis_id.slice(0,8)}...</td><td className={`px-3 py-3 font-semibold ${a.prediction === "Fake" ? "text-rose-300":"text-emerald-300"}`}>{a.prediction}</td><td className="px-3 py-3 text-slate-300">{a.model === "FourModelStacking"?"Four-model stacking":a.model}</td><td className="px-3 py-3">{links[a.analysis_id]?.length ? links[a.analysis_id].map(x=>x.title).join(", ") : "Not assigned"}</td><td className="px-3 py-3 text-slate-400">{new Date(a.created_at).toLocaleString()}</td><td className="px-3 py-3"><button type="button" onClick={() => void download(a.analysis_id)} disabled={busy !== null} className="inline-flex items-center gap-2 whitespace-nowrap rounded-lg bg-cyan-600 px-3 py-2 font-semibold disabled:opacity-40"><Download size={16}/>{busy===a.analysis_id?"Generating...":"Download PDF"}</button></td></tr>)}</tbody></table></section>}
    {!loading && shown.length > PAGE_SIZE && <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-400">Page {visiblePage+1} of {totalPages} · {shown.length} matching reports</p><div className="flex gap-3"><button type="button" disabled={visiblePage===0} onClick={() => setPage(p=>Math.max(0,p-1))} className="rounded-lg border border-white/15 px-4 py-2 text-sm disabled:opacity-40">Previous</button><button type="button" disabled={visiblePage>=totalPages-1} onClick={() => setPage(p=>Math.min(totalPages-1,p+1))} className="rounded-lg border border-white/15 px-4 py-2 text-sm disabled:opacity-40">Next</button></div></div>}
    <p className="mt-4 text-xs text-slate-500">Showing {visibleRows.length} of {shown.length} matching analyses (latest 100 loaded). Reports are model-based screening evidence, not proof of authenticity.</p>
  </main>;
}
