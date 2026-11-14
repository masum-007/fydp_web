"use client";

import {useEffect, useState} from "react";
import {Activity, AlertTriangle, BarChart3, BrainCircuit, ShieldCheck} from "lucide-react";
import {useAuth} from "@/components/auth/AuthProvider";
import {getAnalysisHistory, getModelInfo, getModelResearch, type ModelInfo, type ResearchMetric, type ResearchSummary} from "@/services/api";

const pct = (v: number) => `${(100 * v).toFixed(2)}%`;
const panel = "rounded-3xl border border-white/10 bg-white/5 p-6 sm:p-8";
function MetricTile({label, value, note}: {label: string; value: string; note?: string}) {
  return <div className="rounded-2xl border border-cyan-400/15 bg-[#0b1527] p-5"><p className="text-xs text-slate-400">{label}</p><p className="mt-3 text-2xl font-bold text-white">{value}</p>{note && <p className="mt-2 text-xs text-slate-500">{note}</p>}</div>;
}
export default function ModelAnalytics() {
  const {token} = useAuth();
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [research, setResearch] = useState<ResearchSummary | null>(null);
  const [recent, setRecent] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!token) return;
    let alive = true;
    setLoading(true);
    void Promise.all([getModelInfo(token), getModelResearch(token), getAnalysisHistory(token, 50, 0)])
      .then(([a, b, c]) => {if (alive) {setInfo(a);setResearch(b);setRecent(c.filter(x => x.model === "FourModelStacking").length);setError("");}})
      .catch(err => {if (alive) setError(err instanceof Error ? err.message : "Unable to load model analytics.");})
      .finally(() => {if (alive) setLoading(false);});
    return () => {alive = false;};
  }, [token]);
  const deployed = research?.metrics?.find(x => x.model === "Stacking_TTA");
  const rows = research?.metrics?.filter(x => x.model !== "Stacking_TTA") ?? [];
  const testSplit = research?.split_counts?.test;
  const rawCaveats = research?.research_caveats;
  const caveats = Array.isArray(rawCaveats) ? rawCaveats.filter((c): c is string => typeof c === "string") : [];
  return <main className="min-h-screen px-5 pb-20 pt-8 text-white sm:px-8">
    <div className="flex items-center gap-3"><BrainCircuit className="text-cyan-400" size={29}/><h1 className="text-4xl font-bold md:text-5xl">Model Analytics</h1></div>
    <p className="mt-4 max-w-4xl text-slate-400">Final v3 deployment configuration, verified research results and explainability methods. Research metrics are not performance guarantees for new uploads.</p>
    {loading && <p role="status" className="mt-7 text-cyan-300">Loading active model and matching research records...</p>}
    {error && <p role="alert" className="mt-7 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</p>}
    {info && <section className={`${panel} mt-8`}><div className="flex flex-wrap items-center justify-between gap-4"><h2 className="flex items-center gap-3 text-2xl font-bold"><Activity className="text-cyan-400"/> Active prediction system</h2><span className={info.ready ? "rounded-full border border-emerald-400/20 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300" : "text-amber-300"}>{info.ready ? "Inference ready" : `Unavailable — ${info.reason ?? "unknown"}`}</span></div>
      <p className="mt-5 text-sm leading-6 text-slate-300">Four independently trained CNN classifiers produce Fake-category scores. Original-image and horizontal-flip predictions are combined with a trained logistic-regression stacking learner to produce NeuralEdge AI's final screening classification.</p>
      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{info.members.map((name, i) => <div key={name} className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-4"><p className="mb-2 text-xs text-cyan-300">CNN {i + 1}</p><p className="break-words font-semibold">{name}</p></div>)}</div>
      <div className="mt-5 grid gap-3 sm:grid-cols-3"><MetricTile label="Decision cutoff" value={info.threshold == null ? "Unavailable" : info.threshold.toFixed(2)}/><MetricTile label="Inference mode" value={info.mode === "stacking" ? "Stacking + TTA" : info.mode}/><MetricTile label="Recent stacking analyses" value={recent == null ? "Unavailable" : String(recent)} note="From your latest 50 saved analyses"/></div>
      <p className="mt-6 break-all text-xs text-slate-500">Loaded model version: {info.model_version ?? "Unavailable"}</p>
    </section>}
    <section className={`${panel} mt-7`}><div className="flex items-center gap-3"><BarChart3 className="text-cyan-400"/><h2 className="text-2xl font-bold">Final v3 held-out evaluation</h2></div>
      <p className="mt-3 text-sm text-slate-400">Read directly from the active deployment bundle; these results concern the notebook's internal test split, not live website users or independently verified forensic accuracy.</p>
      {research?.available && deployed ? <>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><MetricTile label="Test accuracy" value={pct(deployed.accuracy)}/><MetricTile label="Fake F1-score" value={pct(deployed.fake_F1)}/><MetricTile label="ROC-AUC" value={deployed.ROC_AUC.toFixed(4)}/><MetricTile label="Held-out images" value={String(deployed.n)} note={testSplit ? `${testSplit.Real} Real / ${testSplit.Fake} Fake` : "Based on active deployment manifest"}/></div>
        <h3 className="mt-8 font-bold">Deployed stacking confusion matrix</h3><div className="mt-3 grid max-w-xl grid-cols-2 gap-3">{[
          ["Correct Real (TN)", deployed.TN], ["Real flagged Fake (FP)", deployed.FP],
          ["Fake missed (FN)", deployed.FN], ["Correct Fake (TP)", deployed.TP]
        ].map(([label, v]) => <div key={label} className="rounded-xl bg-black/20 p-4"><p className="text-xs text-slate-400">{label}</p><p className="mt-2 text-2xl font-bold">{v}</p></div>)}</div>
        <h3 className="mt-8 font-semibold">Research model comparison</h3>
        <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[640px] text-left text-sm"><thead className="border-b border-white/10 text-slate-400"><tr>{["Model", "Accuracy", "Fake precision", "Fake recall", "Fake F1", "ROC-AUC"].map(t => <th key={t} className="px-3 py-3">{t}</th>)}</tr></thead><tbody>{[...rows, deployed].map((m:ResearchMetric) => <tr key={m.model} className="border-b border-white/5"><th className="px-3 py-3 font-semibold">{m.model === "Stacking_TTA" ? "Deployed stacking + TTA" : m.model}</th><td className="px-3 py-3">{pct(m.accuracy)}</td><td className="px-3 py-3">{pct(m.fake_precision)}</td><td className="px-3 py-3">{pct(m.fake_recall)}</td><td className="px-3 py-3">{pct(m.fake_F1)}</td><td className="px-3 py-3">{m.ROC_AUC.toFixed(4)}</td></tr>)}</tbody></table></div>
        <p className="mt-5 text-xs text-slate-400">Operating threshold: {research.threshold?.toFixed(2) ?? "N/A"}. The model score is not a calibrated probability of manipulation.</p>
      </> : <p role="status" className="mt-6 rounded-xl border border-amber-400/20 bg-amber-500/5 p-4 text-amber-200">{research?.reason ?? "Verified final-v3 metrics are not available from this server. No historical results will be substituted."}</p>}
    </section>
    <section className={`${panel} mt-7`}><h2 className="flex items-center gap-3 text-2xl font-bold"><ShieldCheck className="text-cyan-400"/> Explainability methods</h2>
      <div className="mt-5 grid gap-4 md:grid-cols-3">{[
        {name:"Grad-CAM",text:"Highlights which image regions each CNN responded to for the selected Real or Fake output. The combined map is not a direct explanation of the stacking score."},
        {name:"LIME",text:"Tests small image sections and identifies which sections locally supported or opposed the final stacking result."},
        {name:"SHAP",text:"Compares the image with a softened reference to estimate which areas contributed toward or against the selected class."},
      ].map(m => <div key={m.name} className="rounded-xl border border-white/10 bg-black/20 p-5"><h3 className="font-semibold text-cyan-200">{m.name}</h3><p className="mt-3 text-sm leading-6 text-slate-300">{m.text}</p></div>)}</div>
      <p className="mt-5 text-sm text-slate-400">Facial-region names are approximate image locations, not confirmed editing defects.</p>
    </section>
    <section className={`${panel} mt-7`}><h2 className="flex items-center gap-3 text-2xl font-bold"><AlertTriangle className="text-amber-300"/> Robustness and research limitations</h2>
      <p className="mt-4 text-sm leading-6 text-slate-300">Robustness under compression, blur, downscaling, source changes and novel generators must be evaluated separately. The active deployment bundle does not supply verified robustness rows, so this page does not display mismatched experiment results.</p>
      {caveats.length > 0 && <ul className="mt-5 list-inside list-disc space-y-2 text-sm text-slate-300">{caveats.map(c => <li key={c}>{c}</li>)}</ul>}
    </section>
  </main>;
}
