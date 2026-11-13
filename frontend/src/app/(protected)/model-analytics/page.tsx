"use client";

import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/components/auth/AuthProvider";
import { getAnalysisHistory, getModelInfo, type ModelInfo } from "@/services/api";

// Historical results from new-deepfake-2.ipynb, NOT live model accuracy.
const research = [
  { name: "MobileNetV2", accuracy: 92.0, auc: 0.9792 },
  { name: "ResNet50V2", accuracy: 90.67, auc: 0.9790 },
  { name: "Xception", accuracy: 91.33, auc: 0.9589 },
  { name: "EfficientNetB0", accuracy: 86.67, auc: 0.9652 },
  { name: "Four-model soft voting", accuracy: 94.0, auc: 0.9868 },
  { name: "Stacking, threshold 0.50", accuracy: 94.0, auc: 0.9886 },
  { name: "Stacking, threshold 0.65", accuracy: 92.0, auc: 0.9886 },
];

export default function ModelAnalytics() {
  const { token } = useAuth();
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [recentCount, setRecentCount] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!token) return;
    const authToken = token;
    let cancelled = false;
    async function load() {
      try {
        const [data, recent] = await Promise.all([
          getModelInfo(authToken), getAnalysisHistory(authToken, 50, 0),
        ]);
        if (!cancelled) {
          setInfo(data);
          setRecentCount(recent.filter((a) => a.model === "FourModelStacking").length);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Model information unavailable.");
      } finally { if (!cancelled) setLoading(false); }
    }
    void load();
    return () => { cancelled = true; };
  }, [token]);
  return <div className="min-h-screen px-8 pb-20 pt-32 text-white lg:ml-[340px]">
    <Sidebar />
    <h1 className="text-4xl font-bold md:text-5xl">Model Analytics</h1>
    <p className="mt-4 text-slate-400">The new four-network stacking classifier and explainability system.</p>
    {loading && <p role="status" className="mt-8 text-cyan-300">Loading active model information...</p>}
    {error && <p role="alert" className="mt-8 text-red-300">{error}</p>}
    {info && <section className="mt-10 rounded-3xl border border-white/10 bg-white/5 p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-2xl font-bold">Four-model stacking ensemble</h2>
        <span className={info.ready ? "text-emerald-300" : "text-amber-300"}>{info.ready ? "Inference ready" : "Inference unavailable"}</span>
      </div>
      <p className="mt-4 text-sm text-slate-300">MobileNetV2, ResNet50V2, Xception and EfficientNetB0 each produce a score. A trained logistic-regression stacking learner combines their scores into the final classification.</p>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {info.members.map((name) => <div key={name} className="rounded-xl border border-cyan-400/20 bg-cyan-500/5 p-4"><p className="font-semibold">{name}</p><p className="mt-1 text-xs text-slate-400">Active neural network</p></div>)}
      </div>
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        <Tile label="Decision threshold" value={info.threshold === null ? "Unavailable" : info.threshold.toFixed(3)}/>
        <Tile label="Recent stacking analyses" value={String(recentCount ?? "Unavailable")}/>
        <Tile label="Explainability" value={info.explainability.join(" · ")}/>
      </div>
      <p className="mt-5 break-all text-xs text-slate-500">Active model version: {info.model_version ?? "Unavailable"}</p>
    </section>}
    <section className="mt-8 rounded-3xl border border-white/10 bg-white/5 p-8">
      <h2 className="text-2xl font-bold">Held-out research results</h2>
      <p className="mt-3 text-sm text-slate-400">Results recorded in your new Kaggle notebook for 150 test images (75 Real, 75 Fake). These are historical experimental metrics, not accuracy measured on website visitors or unseen generators.</p>
      <div className="mt-6 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b border-white/10 text-slate-400"><th className="p-3">Model / rule</th><th className="p-3">Test accuracy</th><th className="p-3">ROC-AUC</th></tr></thead>
        <tbody>{research.map((row) => <tr key={row.name} className="border-b border-white/5"><td className="p-3">{row.name}</td><td className="p-3">{row.accuracy.toFixed(2)}%</td><td className="p-3">{row.auc.toFixed(4)}</td></tr>)}</tbody>
      </table></div>
      <p className="mt-4 text-xs text-amber-200">Threshold choice trades off false alarms against missed detections. A model score is not independent proof of manipulation.</p>
    </section>
    <section className="mt-8 rounded-3xl border border-white/10 bg-white/5 p-8">
      <h2 className="text-2xl font-bold">Explainability</h2>
      <p className="mt-4 text-sm text-slate-300">Grad-CAM displays averaged CNN activation, while on-demand SHAP and LIME explain the stacking classifier. Facial landmark interpretation can describe influenced regions but does not establish physical tampering.</p>
      <p className="mt-3 text-xs text-slate-400">Recent analysis count is limited to the latest 50 records.</p>
    </section>
  </div>;
}

function Tile({label, value}: {label: string; value: string}) {
  return <div className="rounded-xl bg-black/20 p-4"><p className="text-xs text-slate-400">{label}</p><p className="mt-2 break-words font-semibold">{value}</p></div>;
}
