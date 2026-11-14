"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, KeyRound, LockKeyhole, ShieldCheck, UserRound, Activity, Monitor, LogOut } from "lucide-react";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  getModelInfo, getActiveLoginSessions, updateInvestigatorProfile,
  updateInvestigatorPassword, revokeOtherLoginSessions, revokeEveryLoginSession,
  type ModelInfo, type ActiveLoginSession,
} from "@/services/api";

function Detail({label, value}: {label: string; value: string}) {
  return <div className="rounded-xl border border-white/10 bg-black/20 p-4"><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-2 break-words text-sm font-semibold">{value}</dd></div>;
}
const panel = "rounded-3xl border border-white/10 bg-white/5 p-6 sm:p-8";
const inputClass = "mt-2 w-full rounded-xl border border-white/15 bg-[#0a1020] px-4 py-3 text-white outline-none focus:border-cyan-400";

export default function SettingsPage() {
  const {user, token, updateUser, clearAfterSecurityChange, logout} = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [sessions, setSessions] = useState<ActiveLoginSession[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  useEffect(() => { setName(user?.name ?? ""); }, [user?.name]);
  const reload = useCallback(async () => {
    if (!token) return;
    try {
      const [modelData, loginData] = await Promise.all([getModelInfo(token), getActiveLoginSessions(token)]);
      setModel(modelData); setSessions(loginData); setError("");
    } catch(err) { setError(err instanceof Error ? err.message : "Unable to load account settings."); }
  }, [token]);
  useEffect(() => { void reload(); }, [reload]);
  function start(key: string) { setBusy(key); setError(""); setNotice(""); }
  function fail(err: unknown) { setError(err instanceof Error ? err.message : "This action failed."); setBusy(null); }
  async function saveProfile(event: FormEvent) {
    event.preventDefault(); if (!token || !user) return;
    if (name.trim().length < 2) {setError("Enter a name of at least two characters.");return;}
    start("profile");
    try { const updated = await updateInvestigatorProfile(token, name.trim()); updateUser(updated); setNotice("Profile updated successfully."); }
    catch(err) {fail(err);} finally {setBusy(null);}
  }
  async function savePassword(event: FormEvent) {
    event.preventDefault(); if (!token) return;
    if (newPassword.length < 8) {setError("Use at least 8 characters for your new password.");return;}
    if (newPassword !== confirmPassword) {setError("Your new passwords do not match.");return;}
    if (!window.confirm("Changing your password will sign out every active session, including this one. Continue?")) return;
    start("password");
    try { await updateInvestigatorPassword(token, currentPassword, newPassword); clearAfterSecurityChange(); router.replace("/login?passwordChanged=1"); }
    catch(err) {fail(err);} finally { setBusy(null); setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); }
  }
  async function revokeOthers() {
    if (!token || !window.confirm("Sign out all other devices and tabs?")) return;
    start("others");
    try { const revoked = await revokeOtherLoginSessions(token); setNotice(`${revoked} other session(s) revoked.`); await reload(); }
    catch(err) {fail(err);} finally {setBusy(null);}
  }
  async function revokeAll() {
    if (!token || !window.confirm("Sign out from every device, including this one?")) return;
    start("all");
    try { await revokeEveryLoginSession(token); clearAfterSecurityChange(); router.replace("/login"); }
    catch(err) {fail(err);} finally {setBusy(null);}
  }
  return <main className="min-h-screen px-5 pb-20 pt-8 text-white sm:px-8">
    <h1 className="text-4xl font-bold md:text-5xl">Settings & Account</h1>
    <p className="mt-3 max-w-3xl text-slate-400">Manage your investigator profile, sessions, privacy information and active NeuralEdge AI system.</p>
    {notice && <p role="status" className="mt-6 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-emerald-300">{notice}</p>}
    {error && <p role="alert" className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-300">{error}</p>}
    <div className="mt-8 max-w-6xl space-y-7">
      <section id="profile" className={panel}><div className="flex items-center gap-3"><UserRound className="text-cyan-400"/><h2 className="text-2xl font-bold">Account profile</h2></div>
        <div className="mt-5 grid gap-3 sm:grid-cols-2"><Detail label="Email (verified change process not available)" value={user?.email ?? "N/A"}/><Detail label="Account role" value={user?.role ?? "Investigator"}/></div>
        <form onSubmit={(e) => void saveProfile(e)} className="mt-5 max-w-lg"><label htmlFor="account-name" className="text-sm font-medium">Display name</label><input id="account-name" maxLength={100} minLength={2} required autoComplete="name" value={name} onChange={e => setName(e.target.value)} className={inputClass}/><button type="submit" disabled={busy !== null || name.trim() === user?.name} className="mt-4 rounded-xl bg-cyan-600 px-5 py-3 font-semibold disabled:opacity-40">{busy === "profile" ? "Saving..." : "Save profile"}</button></form>
        <p className="mt-4 break-all text-xs text-slate-500">Investigator ID: {user?.id ?? "N/A"}</p>
      </section>
      <section id="security" className={panel}><div className="flex items-center gap-3"><ShieldCheck className="text-cyan-400"/><h2 className="text-2xl font-bold">Security & sessions</h2></div>
        <p className="mt-3 text-sm leading-6 text-slate-300">NeuralEdge AI uses short-lived access tokens and a protected remembered-session cookie (up to seven days, subject to expiry). Logging out revokes that session immediately.</p>
        <h3 className="mt-6 font-semibold">Signed-in sessions</h3>
        <div className="mt-3 space-y-3">{sessions.length ? sessions.map(s => <div key={s.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/20 p-4"><div className="flex items-center gap-3"><Monitor size={19} className="text-cyan-400"/><div><p className="font-medium">{s.is_current ? "This session" : "Another signed-in session"}</p><p className="text-xs text-slate-400">Started {new Date(s.created_at).toLocaleString()} · Expires {new Date(s.expires_at).toLocaleString()}</p></div></div><span className="text-xs text-slate-400">{s.is_current ? "Current" : "Active"}</span></div>) : <p className="text-sm text-slate-400">No session information is available.</p>}</div>
        <div className="mt-5 flex flex-wrap gap-3"><button type="button" disabled={busy !== null} onClick={() => void revokeOthers()} className="rounded-xl border border-cyan-400/40 px-4 py-3 text-sm font-semibold text-cyan-300 disabled:opacity-40">Sign out other sessions</button><button type="button" disabled={busy !== null} onClick={() => void revokeAll()} className="rounded-xl border border-red-400/40 px-4 py-3 text-sm font-semibold text-red-300 disabled:opacity-40">Sign out everywhere</button></div>
        <h3 className="mt-8 flex items-center gap-2 text-lg font-semibold"><KeyRound size={19} className="text-cyan-400"/> Change password</h3>
        <form onSubmit={(e) => void savePassword(e)} className="mt-4 grid max-w-xl gap-4"><label className="text-sm">Current password<input type="password" autoComplete="current-password" minLength={1} maxLength={128} required value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} className={inputClass}/></label><label className="text-sm">New password (8+ characters)<input type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={newPassword} onChange={e => setNewPassword(e.target.value)} className={inputClass}/></label><label className="text-sm">Confirm new password<input type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} className={inputClass}/></label><button type="submit" disabled={busy !== null} className="w-fit rounded-xl bg-cyan-600 px-5 py-3 font-semibold disabled:opacity-40">{busy === "password" ? "Updating..." : "Change password"}</button></form>
        <p className="mt-3 text-xs text-amber-200">Password changes sign out every device. You must log in with the new password afterward.</p>
      </section>
      <section id="privacy" className={panel}><div className="flex items-center gap-3"><LockKeyhole className="text-cyan-400"/><h2 className="text-2xl font-bold">Privacy & evidence handling</h2></div>
        <div className="mt-5 space-y-4 text-sm leading-6 text-slate-300"><p>Original uploaded images are stored separately from analysis results and explanation assets. Access to evidence, reports and cases is restricted to their investigator account.</p><p>Deleting an analysis removes its saved result and explanation assets, but the uploaded original evidence is retained. Deleting a case can permanently delete its analyses; associated original uploads and audit records may remain.</p><p>Reports include file hashes, timestamps, model findings and any saved image explanations. NeuralEdge AI is a screening aid, not an authenticity certificate.</p><p>Before public deployment, configure HTTPS, a secure session cookie, private persistent storage, backup retention and guest rate limits.</p></div>
        <p className="mt-5 flex items-start gap-2 text-xs text-amber-200"><AlertTriangle size={17} className="shrink-0"/> Do not upload sensitive evidence to a publicly hosted demonstration without an approved privacy policy and storage controls.</p>
      </section>
      <section id="model" className={panel}><div className="flex items-center gap-3"><Activity className="text-cyan-400"/><h2 className="text-2xl font-bold">Active model & system</h2></div>
        {model ? <><div className="mt-5 grid gap-3 sm:grid-cols-2"><Detail label="Model status" value={model.ready ? "Inference ready" : `Unavailable: ${model.reason ?? "unknown"}`}/><Detail label="Prediction mode" value={model.mode === "stacking" ? "Four-model stacking with test-time augmentation" : model.mode}/><Detail label="Decision threshold" value={model.threshold == null ? "N/A" : model.threshold.toFixed(2)}/><Detail label="Explanations" value={model.explainability.join(", ")}/></div><h3 className="mt-6 font-semibold">Loaded CNNs</h3><div className="mt-3 flex flex-wrap gap-2">{model.members.map(m => <span key={m} className="rounded-lg border border-cyan-400/20 bg-cyan-400/5 px-3 py-2 text-sm text-cyan-200">{m}</span>)}</div><p className="mt-4 break-all text-xs text-slate-400">Model version: {model.model_version ?? "Unknown"}</p></> : <p role="status" className="mt-5 text-slate-400">Loading backend status...</p>}
        <p className="mt-5 text-xs text-slate-500">System configuration is controlled by the backend and cannot be changed from this account page.</p>
      </section>
      <button type="button" onClick={() => void logout().then(() => router.replace("/login")).catch(fail)} className="inline-flex items-center gap-2 rounded-xl border border-red-400/40 bg-red-500/10 px-5 py-3 text-red-300"><LogOut size={18}/> Log out of this session</button>
    </div>
  </main>;
}
