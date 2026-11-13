"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { useAuth } from "@/components/auth/AuthProvider";
import { getModelInfo, type ModelInfo } from "@/services/api";

export default function SettingsPage() {
  const { user, token, logout } = useAuth();
  const router = useRouter();
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!token) return;
    const authToken = token;
    let cancelled = false;
    void getModelInfo(authToken).then((model) => { if (!cancelled) setInfo(model); })
      .catch((err: unknown) => { if (!cancelled) setError(err instanceof Error ? err.message : "Backend unavailable."); })
      .finally(() => { if (!cancelled) setChecking(false); });
    return () => { cancelled = true; };
  }, [token]);

  return <div className="min-h-screen px-8 pb-20 pt-32 text-white lg:ml-[340px]">
    <Sidebar />
    <h1 className="text-4xl font-bold md:text-5xl">Settings</h1>
    <p className="mt-4 text-slate-400">Investigator profile, actual model configuration, and security information.</p>
    <div className="mt-10 max-w-5xl space-y-7">
      <section className="rounded-3xl border border-white/10 bg-white/5 p-8">
        <h2 className="text-2xl font-bold">Account profile</h2>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <Detail label="Name" value={user?.name ?? "N/A"}/>
          <Detail label="Email" value={user?.email ?? "N/A"}/>
          <Detail label="Role" value={user?.role ?? "Investigator"}/>
          <Detail label="Account ID" value={user?.id ?? "N/A"}/>
        </div>
        <p className="mt-4 text-sm text-slate-400">Account editing and password change are not implemented yet; this is a read-only profile.</p>
      </section>
      <section className="rounded-3xl border border-white/10 bg-white/5 p-8">
        <h2 className="text-2xl font-bold">Active AI engine</h2>
        {checking && <p role="status" className="mt-4 text-cyan-300">Checking backend configuration...</p>}
        {error && <p role="alert" className="mt-4 text-red-300">{error}</p>}
        {info && <>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <Detail label="Classification" value={info.mode === "stacking" ? "Four-model stacking" : info.model}/>
            <Detail label="Model status" value={info.ready ? "Ready" : `Not ready (${info.reason ?? "unknown"})`}/>
            <Detail label="Decision threshold" value={info.threshold === null ? "N/A" : info.threshold.toFixed(3)}/>
            <Detail label="Explanation methods" value={info.explainability.join(", ")}/>
          </div>
          <h3 className="mt-6 font-semibold">Loaded models</h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">{info.members.map((m) => <div className="rounded-xl bg-black/20 p-4" key={m}>{m}</div>)}</div>
          <p className="mt-4 break-all text-xs text-slate-400">Model version: {info.model_version ?? "N/A"}</p>
        </>}
        <p className="mt-4 text-sm text-amber-200">The backend controls the model version. This page does not change trained models.</p>
      </section>
      <section className="rounded-3xl border border-white/10 bg-white/5 p-8">
        <h2 className="text-2xl font-bold">Security and privacy</h2>
        <Detail label="Authentication" value="JWT Bearer token (30-minute lifetime)"/>
        <Detail label="Session" value="In-memory; you may need to log in again after refreshing"/>
        <Detail label="Evidence" value="Original uploads are separate from analyses and explanation assets"/>
        <Detail label="Deletion" value="Deleting analyses retains original evidence uploads and backups"/>
        <p className="mt-4 text-sm text-slate-300">The AI supports investigation and does not independently establish authenticity or manipulation.</p>
        <button type="button" onClick={() => { logout(); router.replace("/login"); }} className="mt-6 rounded-xl border border-red-400/40 bg-red-500/10 px-6 py-3 font-semibold text-red-300">Sign out</button>
      </section>
      <section className="rounded-3xl border border-white/10 bg-white/5 p-8">
        <h2 className="text-2xl font-bold">About NeuralEdge AI</h2>
        <p className="mt-3 text-slate-300">An Explainable Deep Learning Framework for Deepfake Image Detection to Support Cybercrime Investigations.</p>
        <p className="mt-3 text-sm text-slate-400">MobileNetV2, ResNet50V2, Xception and EfficientNetB0 feed a stacking meta-learner. Visual explanations: Grad-CAM, SHAP, LIME and optional facial-region interpretation.</p>
      </section>
    </div>
  </div>;
}
function Detail({label, value}: {label: string; value: string}) {
  return <div className="border-b border-white/10 py-3"><p className="text-xs text-slate-400">{label}</p><p className="mt-2 break-all text-sm font-semibold">{value}</p></div>;
}
