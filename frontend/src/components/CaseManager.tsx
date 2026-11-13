
"use client";

import {
  useEffect,
  useState,
  type FormEvent,
} from "react";

import {
  FolderPlus,
  FolderOpen,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";

import {
  createCase,
  getCases,
  getCaseDetails,
  getAnalysisHistory,
  attachAnalysisToCase,
  updateCaseStatus,
  editInvestigationCase,
  unlinkAnalysisFromCase,
  permanentlyDeleteAnalysis,
  permanentlyDeleteCase,
  type InvestigationCase,
  type CaseDetails,
  type AnalysisResponse,
} from "@/services/api";

export default function CaseManager() {
  const { token } = useAuth();

  const [cases, setCases] = useState<InvestigationCase[]>([]);
  const [analyses, setAnalyses] = useState<AnalysisResponse[]>([]);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const [selectedCase, setSelectedCase] =
    useState<CaseDetails | null>(null);

  const [selectedAnalysisId, setSelectedAnalysisId] =
    useState("");

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);

  function notifyHistoryChange() {
    window.dispatchEvent(new Event("neuraledge-data-changed"));
  }


  // Refresh when Analysis History deletes a record outside this component.
  useEffect(() => {
    const onChange = () => {
      setSelectedCase(null);
      setLoading(true);
      setRefreshKey((v) => v + 1);
    };
    window.addEventListener("neuraledge-data-changed", onChange);
    return () => window.removeEventListener("neuraledge-data-changed", onChange);
  }, []);

  // Load cases and available analyses when the page opens.
  useEffect(() => {
    if (!token) return;

    const authToken: string = token;
    let cancelled = false;

    async function loadInitialData() {
      try {
        const [caseData, analysisData] = await Promise.all([
          getCases(authToken),
          getAnalysisHistory(authToken, 100, 0),
        ]);

        if (!cancelled) {
          setCases(caseData);
          setAnalyses(analysisData);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load case information."
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadInitialData();

    return () => {
      cancelled = true;
    };
  }, [token, refreshKey]);

  // Refresh cases after a modification.
  async function refreshCases(authToken: string) {
    const data = await getCases(authToken);
    setCases(data);
  }

  // Create a new investigation case.
  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      setError("Please log in.");
      return;
    }

    if (title.trim().length < 3) {
      setError("The case title must have at least 3 characters.");
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const created = await createCase(
        token,
        title.trim(),
        description.trim()
      );

      await refreshCases(token);

      setTitle("");
      setDescription("");

      setMessage(`Case "${created.title}" created successfully.`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create case."
      );
    } finally {
      setBusy(false);
    }
  }

  // Expand or collapse a case and load its analyses.
  async function handleViewCase(caseId: string) {
    if (!token || busy) return;

    if (selectedCase?.id === caseId) {
      setSelectedCase(null);
      setSelectedAnalysisId("");
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const details = await getCaseDetails(token, caseId);

      setSelectedCase(details);
      setEditTitle(details.title);
      setEditDescription(details.description);
      setConfirmation("");
      setAcknowledged(false);
      setSelectedAnalysisId("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load case details."
      );
    } finally {
      setBusy(false);
    }
  }

  // Attach an existing AI analysis to the selected case.
  async function handleAttach() {
    if (!token || !selectedCase || !selectedAnalysisId) {
      setError("Please select an analysis first.");
      return;
    }

    setBusy(true);
    setError("");
    setMessage("");

    try {
      await attachAnalysisToCase(
        token,
        selectedCase.id,
        selectedAnalysisId
      );

      const updated = await getCaseDetails(
        token,
        selectedCase.id
      );

      setSelectedCase(updated);
      setSelectedAnalysisId("");

      await refreshCases(token);

      setMessage("Analysis attached to the case successfully.");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to attach analysis."
      );
    } finally {
      setBusy(false);
    }
  }

  // Open or close the selected investigation.
  async function handleStatusChange() {
    if (!token || !selectedCase) return;

    const newStatus =
      selectedCase.status === "open" ? "closed" : "open";

    setBusy(true);
    setError("");
    setMessage("");

    try {
      await updateCaseStatus(
        token,
        selectedCase.id,
        newStatus
      );

      const updated = await getCaseDetails(
        token,
        selectedCase.id
      );

      setSelectedCase(updated);

      await refreshCases(token);

      setMessage(
        newStatus === "closed"
          ? "Investigation case closed successfully."
          : "Investigation case reopened successfully."
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to update case status."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleEditCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !selectedCase || busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await editInvestigationCase(token, selectedCase.id, editTitle.trim(), editDescription.trim());
      const updated = await getCaseDetails(token, selectedCase.id);
      setSelectedCase(updated);
      await refreshCases(token);
      setMessage("Case details updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Case edit failed.");
    } finally { setBusy(false); }
  }

  async function handleUnlink(analysisId: string) {
    if (!token || !selectedCase || busy) return;
    if (!window.confirm("Remove this analysis from this case? The analysis itself will NOT be deleted.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await unlinkAnalysisFromCase(token, selectedCase.id, analysisId);
      setSelectedCase(await getCaseDetails(token, selectedCase.id));
      await refreshCases(token);
      setMessage("Analysis unlinked. It still exists in history and reports.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not unlink analysis.");
    } finally { setBusy(false); }
  }

  async function handleDeleteAnalysis(analysisId: string) {
    if (!token || !selectedCase || busy) return;
    if (!window.confirm("PERMANENTLY delete this analysis, its SHAP/LIME/Grad-CAM assets, and ALL its case links? Uploaded original evidence is retained.")) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await permanentlyDeleteAnalysis(token, analysisId);
      setSelectedCase(await getCaseDetails(token, selectedCase.id));
      setAnalyses((previous) => previous.filter((a) => a.analysis_id !== analysisId));
      await refreshCases(token);
      notifyHistoryChange();
      setMessage("Analysis permanently deleted from the app; original uploaded evidence retained.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cannot delete analysis.");
    } finally { setBusy(false); }
  }

  async function handleDeleteCase() {
    if (!token || !selectedCase || busy || !acknowledged || confirmation !== selectedCase.title) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await permanentlyDeleteCase(token, selectedCase.id, confirmation);
      setSelectedCase(null);
      setSelectedAnalysisId("");
      setConfirmation("");
      setAcknowledged(false);
      const [updatedCases, updatedAnalyses] = await Promise.all([
        getCases(token), getAnalysisHistory(token, 100, 0)
      ]);
      setCases(updatedCases);
      setAnalyses(updatedAnalyses);
      notifyHistoryChange();
      setMessage(`Case deleted together with ${result.deleted_analyses} saved analyses. Original evidence uploads were retained.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Case deletion failed.");
    } finally { setBusy(false); }
  }

  function handleRefresh() {
    if (busy) return;

    setLoading(true);
    setError("");
    setMessage("");
    setSelectedCase(null);
    setRefreshKey((value) => value + 1);
  }

  if (!token) {
    return (
      <p className="text-amber-300">
        Please log in to manage investigation cases.
      </p>
    );
  }

  return (
    <section className="space-y-8">

      {/* Create Investigation Case */}
      <div className="rounded-3xl border border-white/10 bg-white/5 p-8">

        <div className="flex items-center gap-3">
          <FolderPlus className="text-cyan-400" size={28} />

          <h2 className="text-2xl font-bold">
            Create Investigation Case
          </h2>
        </div>

        <p className="mt-3 text-slate-400">
          Organize related deepfake analyses into
          a single investigation case.
        </p>

        <form
          onSubmit={handleCreate}
          className="mt-8 space-y-5"
        >
          <div>
            <label
              htmlFor="case-title"
              className="mb-2 block text-sm text-slate-300"
            >
              Case Title
            </label>

            <input
              id="case-title"
              type="text"
              required
              minLength={3}
              maxLength={150}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Suspected Social Media Impersonation"
              className="w-full rounded-xl border border-white/10 bg-black/20 p-4 text-white"
            />
          </div>

          <div>
            <label
              htmlFor="case-description"
              className="mb-2 block text-sm text-slate-300"
            >
              Description
            </label>

            <textarea
              id="case-description"
              rows={4}
              maxLength={2000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the investigation..."
              className="w-full rounded-xl border border-white/10 bg-black/20 p-4 text-white"
            />
          </div>

          <button
            type="submit"
            disabled={busy}
            className="rounded-xl bg-cyan-600 px-6 py-3 font-semibold text-white disabled:opacity-50"
          >
            {busy ? "Processing..." : "Create Case"}
          </button>
        </form>
      </div>

      {/* Feedback Messages */}
      {error && (
        <p
          role="alert"
          className="rounded-xl border border-red-400/30 bg-red-400/10 p-4 text-red-300"
        >
          {error}
        </p>
      )}

      {message && (
        <p
          role="status"
          className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 p-4 text-emerald-300"
        >
          {message}
        </p>
      )}

      {/* Saved Investigation Cases */}
      <div className="rounded-3xl border border-white/10 bg-white/5 p-8">

        <div className="flex flex-wrap items-center justify-between gap-4">

          <h2 className="flex items-center gap-3 text-2xl font-bold">
            <FolderOpen size={26} className="text-cyan-400" />
            Saved Investigation Cases
          </h2>

          <button
            type="button"
            onClick={handleRefresh}
            disabled={loading || busy}
            className="flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2 disabled:opacity-50"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>

        {loading ? (
          <p role="status" className="mt-6 text-slate-400">
            Loading investigation cases...
          </p>
        ) : cases.length === 0 ? (
          <p className="mt-6 text-slate-400">
            No cases created yet.
          </p>
        ) : (
          <div className="mt-6 space-y-5">
            {cases.map((item) => (
              <div
                key={item.id}
                className="rounded-2xl border border-white/10 bg-black/20 p-6"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">

                  <div>
                    <h3 className="text-xl font-semibold">
                      {item.title}
                    </h3>

                    <p className="mt-2 text-sm text-slate-400">
                      {item.description || "No description provided."}
                    </p>

                    <p className="mt-3 text-xs text-slate-500">
                      Created:{" "}
                      {new Date(item.created_at).toLocaleString()}
                    </p>

                    <p className="mt-2 text-xs text-slate-500">
                      Attached analyses: {item.analysis_count}
                    </p>
                  </div>

                  <span
                    className={
                      item.status === "open"
                        ? "rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400"
                        : "rounded-lg bg-slate-500/20 px-3 py-2 text-sm text-slate-300"
                    }
                  >
                    {item.status.toUpperCase()}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => void handleViewCase(item.id)}
                  disabled={busy}
                  className="mt-5 flex items-center gap-2 rounded-xl bg-cyan-600/20 px-5 py-3 text-sm font-semibold text-cyan-300 disabled:opacity-50"
                >
                  {selectedCase?.id === item.id ? (
                    <>
                      <ChevronUp size={16} />
                      Hide Details
                    </>
                  ) : (
                    <>
                      <ChevronDown size={16} />
                      Manage Case
                    </>
                  )}
                </button>

                {/* Expanded Case Details */}
                {selectedCase?.id === item.id && (
                  <div className="mt-6 space-y-6 border-t border-white/10 pt-6">

                    <form onSubmit={(event) => void handleEditCase(event)} className="space-y-3 rounded-xl bg-white/5 p-5">
                      <h4 className="font-semibold">Edit case details</h4>
                      <label className="block text-sm">Case title
                        <input required minLength={3} maxLength={150} value={editTitle} onChange={(e) => setEditTitle(e.target.value)}
                          className="mt-2 w-full rounded-lg border border-white/10 bg-slate-900 p-3" />
                      </label>
                      <label className="block text-sm">Description
                        <textarea maxLength={2000} rows={2} value={editDescription} onChange={(e) => setEditDescription(e.target.value)}
                          className="mt-2 w-full rounded-lg border border-white/10 bg-slate-900 p-3" />
                      </label>
                      <button type="submit" disabled={busy} className="rounded-lg bg-cyan-600 px-4 py-2 disabled:opacity-50">Save changes</button>
                    </form>

                    <h4 className="text-lg font-bold">Attached AI Analyses</h4>

                    {selectedCase.analyses.length === 0 ? (
                      <p className="text-sm text-slate-400">
                        No analyses attached to this case yet.
                      </p>
                    ) : (
                      <div className="space-y-3">

                        {selectedCase.analyses.map((analysis) => (
                          <div
                            key={analysis.analysis_id}
                            className="rounded-xl border border-white/10 bg-white/5 p-4"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-3">

                              <div>
                                <p className="font-mono text-xs text-slate-400">
                                  {analysis.analysis_id}
                                </p>

                                <p className="mt-2 text-sm">
                                  Model: {analysis.model === "FourModelStacking" ? "Four-model stacking (MobileNetV2, ResNet50V2, Xception, EfficientNetB0)" : analysis.model}
                                </p>

                                <p className="mt-1 text-sm">
                                  Confidence:{" "}
                                  {(analysis.confidence * 100).toFixed(2)}%
                                </p>
                              </div>

                              <span
                                className={
                                  analysis.prediction === "Fake"
                                    ? "font-bold text-red-400"
                                    : "font-bold text-emerald-400"
                                }
                              >
                                {analysis.prediction}
                              </span>
                            </div>
                            <div className="mt-4 flex flex-wrap gap-3">
                              {selectedCase.status === "open" && (
                                <button type="button" disabled={busy} onClick={() => void handleUnlink(analysis.analysis_id)}
                                  className="rounded-lg border border-slate-400/30 px-3 py-2 text-sm text-slate-200 disabled:opacity-50">
                                  Remove from this case
                                </button>
                              )}
                              <button type="button" disabled={busy} onClick={() => void handleDeleteAnalysis(analysis.analysis_id)}
                                className="rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-sm text-red-300 disabled:opacity-50">
                                Permanently delete analysis
                              </button>
                            </div>
                          </div>
                        ))}

                      </div>
                    )}

                    {/* Attach Analysis */}
                    {selectedCase.status === "open" && (
                      <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-5">

                        <h4 className="font-semibold">
                          Attach Existing Analysis
                        </h4>

                        <p className="mt-2 text-sm text-slate-400">
                          Select an analysis previously completed
                          by your AI detection system.
                        </p>

                        <select
                          aria-label="Select analysis"
                          value={selectedAnalysisId}
                          onChange={(e) =>
                            setSelectedAnalysisId(e.target.value)
                          }
                          className="mt-4 w-full rounded-xl border border-white/10 bg-slate-900 p-3 text-white"
                        >
                          <option value="">
                            Select an analysis
                          </option>

                          {analyses
                            .filter(
                              (analysis) =>
                                !selectedCase.analyses.some(
                                  (attached) =>
                                    attached.analysis_id ===
                                    analysis.analysis_id
                                )
                            )
                            .map((analysis) => (
                              <option
                                key={analysis.analysis_id}
                                value={analysis.analysis_id}
                              >
                                {analysis.analysis_id.slice(0, 8)}
                                {" — "}
                                {analysis.prediction}
                                {" — "}
                                {analysis.model}
                              </option>
                            ))}
                        </select>

                        <button
                          type="button"
                          onClick={() => void handleAttach()}
                          disabled={busy || !selectedAnalysisId}
                          className="mt-4 rounded-xl bg-cyan-600 px-5 py-3 font-semibold text-white disabled:opacity-50"
                        >
                          {busy ? "Processing..." : "Attach Analysis"}
                        </button>
                      </div>
                    )}

                    {/* Change Case Status */}
                    <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl bg-white/5 p-5">

                      <div>
                        <h4 className="font-semibold">
                          Investigation Status
                        </h4>

                        <p className="mt-2 text-sm text-slate-400">
                          {selectedCase.status === "open"
                            ? "This case currently accepts new analyses."
                            : "This case is closed. Reopen it to attach more analyses."}
                        </p>
                      </div>

                      <button
                        type="button"
                        onClick={() => void handleStatusChange()}
                        disabled={busy}
                        className="rounded-xl border border-white/20 px-5 py-3 font-semibold text-white hover:bg-white/10 disabled:opacity-50"
                      >
                        {selectedCase.status === "open"
                          ? "Close Case"
                          : "Reopen Case"}
                      </button>
                    </div>

                    <section className="space-y-3 rounded-xl border border-red-400/30 bg-red-500/5 p-5">
                      <h4 className="font-semibold text-red-300">Danger zone — permanently delete case</h4>
                      <p className="text-sm text-slate-300">
                        This deletes the case and all {selectedCase.analyses.length} attached analyses and their explanation files.
                        Original uploaded evidence is retained. If any analysis belongs to another case, deletion is blocked.
                      </p>
                      <label className="block text-sm">Type the exact case title to confirm
                        <input aria-label="Confirm case deletion by title" value={confirmation} onChange={(e) => setConfirmation(e.target.value)}
                          className="mt-2 w-full rounded-lg border border-red-400/30 bg-slate-900 p-3" />
                      </label>
                      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)}/>
                        I understand this cannot be undone from the application.</label>
                      <button type="button" disabled={busy || !acknowledged || confirmation !== selectedCase.title}
                        onClick={() => void handleDeleteCase()}
                        className="rounded-lg bg-red-700 px-4 py-3 text-white disabled:opacity-40">
                        Permanently delete case and its analyses
                      </button>
                    </section>

                  </div>
                )}

              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
