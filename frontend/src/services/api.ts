// All authenticated calls use the same-origin Next.js /api rewrite.
// Never persist access JWTs in localStorage or sessionStorage.
const API_URL = "";
let activeAccessToken: string | null = null;
let sessionEpoch = 0;
let pendingRefresh: Promise<LoginResponse> | null = null;

export function setAccessToken(value: string | null): void {
  activeAccessToken = value;
  sessionEpoch += 1;
}

function notifySessionExpired(): void {
  activeAccessToken = null;
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("neuraledge-session-expired"));
  }
}

export async function restoreSession(): Promise<LoginResponse> {
  if (!pendingRefresh) {
    pendingRefresh = (async () => {
      const startedAtEpoch = sessionEpoch;
      const response = await fetch("/api/auth/refresh", {
        method: "POST", credentials: "same-origin", cache: "no-store",
      });
      if (!response.ok) {
        if (response.status === 401) {
          if (sessionEpoch === startedAtEpoch) notifySessionExpired();
          throw new Error("Your saved session has expired. Please log in again.");
        }
        throw new Error(`Unable to restore your session (HTTP ${response.status}).`);
      }
      const session = (await response.json()) as LoginResponse;
      if (sessionEpoch !== startedAtEpoch) {
        throw new Error("A newer login or logout superseded this session request.");
      }
      setAccessToken(session.access_token);
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("neuraledge-token-renewed", { detail: session }));
      }
      return session;
    })().finally(() => { pendingRefresh = null; });
  }
  return pendingRefresh;
}

export async function endServerSession(): Promise<void> {
  const response = await fetch("/api/auth/logout", {
    method: "POST", credentials: "same-origin", cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Could not log out securely. Please retry while the server is reachable.");
  }
  setAccessToken(null);
}

export type Investigator = {
  id: string;
  name: string;
  email: string;
  role: "investigator";
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: Investigator;
};

export async function loginUser(
  email: string,
  password: string
): Promise<LoginResponse> {
  const response = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
    credentials: "same-origin",
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Incorrect email or password.");
    }

    throw new Error(`Login failed (HTTP ${response.status}).`);
  }

  return (await response.json()) as LoginResponse;
}

export async function authenticatedFetch(
  path: string,
  token: string,
  options: RequestInit = {}
): Promise<Response> {
  if (!path.startsWith("/api/") || path.startsWith("//")) {
    throw new Error("Invalid authenticated API path.");
  }
  const send = (accessToken: string) => {
    const headers = new Headers(options.headers);
    headers.set("Authorization", `Bearer ${accessToken}`);
    return fetch(`${API_URL}${path}`, {
      ...options, headers, cache: "no-store", credentials: "same-origin",
    });
  };
  let response = await send(activeAccessToken ?? token);
  if (response.status !== 401) return response;

  // A 30-minute access JWT may expire during an otherwise valid 7-day
  // remembered session. Renew once, then retry the original request.
  let session: LoginResponse;
  try {
    session = await restoreSession();
  } catch {
    // No session means no retry. The auth context handles the redirect.
    return response;
  }
  response = await send(session.access_token);
  if (response.status === 401) notifySessionExpired();
  return response;
}

export type EvidenceResponse = {
  id: string;
  filename: string;
  sha256: string;
  size_bytes: number;
  width: number;
  height: number;
  media_type: string;
  created_at: string;
  status: string;
};

export type AnalysisResponse = {
  analysis_id: string;
  evidence_id: string;
  prediction: "Real" | "Fake";
  fake_probability: number;
  real_probability: number;
  confidence: number;
  threshold: number;
  model: string;
  mode: string;
  model_version: string;
  image_sha256: string;
  created_at: string;
  status: string;
  explanation: {
    method: string;
    model: string;
    layer: string;
    note: string;
  };
  assets: {
    heatmap: {
      url: string;
      sha256: string;
    };
    overlay: {
      url: string;
      sha256: string;
    };
    gradcam?: { url: string; sha256: string };
    lime?: { url: string; sha256: string };
    shap?: { url: string; sha256: string };
  };
  xai?: Partial<Record<ExplanationMethod, SavedExplanation>>;
  members?: Record<string, { prediction: "Real" | "Fake"; fake_probability: number; confidence: number }>;
  tta_applied?: boolean;
  face_detected?: boolean;
};

// Converts API error responses into readable messages.
async function checkResponse(response: Response) {
  if (response.ok) return;

  if (response.status === 401) {
    throw new Error(
      "Your session has expired. Please log in again."
    );
  }

  let message = `Request failed (HTTP ${response.status}).`;

  try {
    const data = await response.json();
    const detail = data.detail;

    if (typeof detail === "string") {
      message = detail;
    } else if (
      detail &&
      typeof detail === "object" &&
      typeof detail.message === "string"
    ) {
      message = detail.message;
    }
  } catch {
    // The server may return a non-JSON error.
  }

  throw new Error(message);
}

// Uploads the original image and returns an evidence ID.
export async function uploadEvidence(
  file: File,
  token: string
): Promise<EvidenceResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await authenticatedFetch(
    "/api/evidence",
    token,
    {
      method: "POST",
      body: formData,
    }
  );

  await checkResponse(response);

  return (await response.json()) as EvidenceResponse;
}

// Runs the trained model using a previously uploaded image.
export async function analyzeEvidence(
  evidenceId: string,
  token: string
): Promise<AnalysisResponse> {
  const response = await authenticatedFetch(
    "/api/analyze",
    token,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        evidence_id: evidenceId,
      }),
    }
  );

  await checkResponse(response);

  return (await response.json()) as AnalysisResponse;
}

// Downloads a protected Grad-CAM image.
export async function getAnalysisImage(
  path: string,
  token: string
): Promise<string> {
  if (!path.startsWith("/api/analyses/")) {
    throw new Error("Invalid analysis image path.");
  }

  const response = await authenticatedFetch(path, token);

  await checkResponse(response);

  const blob = await response.blob();

  if (!blob.type.startsWith("image/")) {
    throw new Error("Server did not return an image.");
  }

  return URL.createObjectURL(blob);
}


export async function getAnalysisHistory(
  token: string,
  limit = 50,
  offset = 0
): Promise<AnalysisResponse[]> {
  const response = await authenticatedFetch(
    `/api/analyses?limit=${limit}&offset=${offset}`,
    token
  );

  await checkResponse(response);

  return (await response.json()) as AnalysisResponse[];
}

async function saveAuthenticatedDownload(
  path: string,
  token: string,
  filename: string,
  expectedMime: "application/pdf" | "application/zip"
): Promise<void> {
  const response = await authenticatedFetch(path, token);
  await checkResponse(response);
  const blob = await response.blob();
  if (!blob.type.includes(expectedMime) &&
      !(expectedMime === "application/zip" && blob.type.includes("octet-stream"))) {
    throw new Error(`Server did not return a valid ${expectedMime === "application/pdf" ? "PDF" : "ZIP"} file.`);
  }
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  }
}

export async function downloadForensicReport(
  analysisId: string,
  token: string,
  caseId?: string
): Promise<void> {
  const query = caseId ? `?case_id=${encodeURIComponent(caseId)}` : "";
  return saveAuthenticatedDownload(
    `/api/report/${encodeURIComponent(analysisId)}${query}`,
    token,
    `NeuralEdge_${analysisId}.pdf`,
    "application/pdf"
  );
}

export async function downloadCaseReportBundle(
  caseId: string,
  token: string
): Promise<void> {
  return saveAuthenticatedDownload(
    `/api/cases/${encodeURIComponent(caseId)}/reports.zip`,
    token,
    `NeuralEdge_Case_${caseId.slice(0, 8)}.zip`,
    "application/zip"
  );
}

export async function getEvidenceThumbnail(
  evidenceId: string,
  token: string
): Promise<string> {
  const response = await authenticatedFetch(
    `/api/evidence/${encodeURIComponent(evidenceId)}/thumbnail`, token
  );
  await checkResponse(response);
  const blob = await response.blob();
  if (!blob.type.startsWith("image/")) {
    throw new Error("Evidence thumbnail is unavailable.");
  }
  return URL.createObjectURL(blob);
}

export type InvestigationCase = {
  id: string;
  title: string;
  description: string;
  status: "open" | "closed";
  created_at: string;
  analysis_count: number;
};

export async function getCases(
  token: string
): Promise<InvestigationCase[]> {
  const response = await authenticatedFetch(
    "/api/cases",
    token
  );

  await checkResponse(response);

  return (await response.json()) as InvestigationCase[];
}

export async function createCase(
  token: string,
  title: string,
  description: string
): Promise<InvestigationCase> {
  const response = await authenticatedFetch(
    "/api/cases",
    token,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title,
        description,
      }),
    }
  );

  await checkResponse(response);

  return (await response.json()) as InvestigationCase;
}

export type CaseDetails = {
  id: string;
  title: string;
  description: string;
  status: "open" | "closed";
  created_at: string;
  analyses: AnalysisResponse[];
};

// Fetch one case and all analyses attached to it.
export async function getCaseDetails(
  token: string,
  caseId: string
): Promise<CaseDetails> {
  const response = await authenticatedFetch(
    `/api/cases/${encodeURIComponent(caseId)}`,
    token
  );

  await checkResponse(response);

  return (await response.json()) as CaseDetails;
}

// Attach an existing analysis to an open case.
export async function attachAnalysisToCase(
  token: string,
  caseId: string,
  analysisId: string
): Promise<void> {
  const response = await authenticatedFetch(
    `/api/cases/${encodeURIComponent(caseId)}/analyses`,
    token,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        analysis_id: analysisId,
      }),
    }
  );

  await checkResponse(response);
}

// Open or close a case.
export async function updateCaseStatus(
  token: string,
  caseId: string,
  status: "open" | "closed"
): Promise<void> {
  const response = await authenticatedFetch(
    `/api/cases/${encodeURIComponent(caseId)}/status`,
    token,
    {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status }),
    }
  );

  await checkResponse(response);
}

export type RegisterResponse = {
  id: string;
  name: string;
  email: string;
  role: "investigator";
};

export async function registerInvestigator(
  name: string,
  email: string,
  password: string
): Promise<RegisterResponse> {
  const response = await fetch(
    `${API_URL}/api/auth/register`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name,
        email,
        password,
      }),
      cache: "no-store",
    }
  );

  if (!response.ok) {
    if (response.status === 409) {
      throw new Error(
        "This email address is already registered."
      );
    }

    const data = await response.json().catch(() => null);

    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : "Registration failed. Check your information."
    );
  }

  return (await response.json()) as RegisterResponse;
}

export type ExplanationMethod = "gradcam" | "lime" | "shap";

export type SavedExplanation = {
  method: string;
  status: string;
  created_at: string;
  target_label: string;
  model_version: string;
  note: string;
  interpretation: {
    status: string;
    narrative: string;
    regions: unknown;
  };
};

export async function getAnalysisDetails(
  analysisId: string,
  token: string
): Promise<AnalysisResponse> {
  const response = await authenticatedFetch(
    `/api/analyses/${encodeURIComponent(analysisId)}`,
    token
  );
  await checkResponse(response);
  return (await response.json()) as AnalysisResponse;
}

export type ExplanationJobStatus = "not_started" | "queued" | "running" | "completed" | "failed" | "cancelled";
export type ExplanationJob = {
  id: string | null;
  analysis_id: string;
  method: ExplanationMethod;
  status: ExplanationJobStatus;
  progress: number;
  message: string;
  created_at: string | null;
  updated_at: string | null;
  started_at: string | null;
  finished_at: string | null;
};

/** Start an asynchronous explanation; POST returns promptly with a job record. */
export async function generateSavedExplanation(
  analysisId: string,
  method: ExplanationMethod,
  token: string
): Promise<ExplanationJob> {
  const response = await authenticatedFetch(
    `/api/analyses/${encodeURIComponent(analysisId)}/explain/${method}`,
    token,
    { method: "POST" }
  );
  await checkResponse(response);
  return (await response.json()) as ExplanationJob;
}

export async function getExplanationJobStatus(
  analysisId: string,
  method: ExplanationMethod,
  token: string
): Promise<ExplanationJob> {
  const response = await authenticatedFetch(
    `/api/analyses/${encodeURIComponent(analysisId)}/explain/${method}/status`,
    token
  );
  await checkResponse(response);
  return (await response.json()) as ExplanationJob;
}

export async function cancelQueuedExplanation(
  analysisId: string,
  method: ExplanationMethod,
  token: string
): Promise<ExplanationJob> {
  const response = await authenticatedFetch(
    `/api/analyses/${encodeURIComponent(analysisId)}/explain/${method}/job`,
    token, { method: "DELETE" }
  );
  await checkResponse(response);
  return (await response.json()) as ExplanationJob;
}

// v3 management: typed models and explicitly confirmed deletion.
export type ModelInfo = {
  ready: boolean;
  reason: string | null;
  model: string;
  mode: string;
  members: string[];
  threshold: number | null;
  model_version: string | null;
  explainability: string[];
};

export type LinkedCase = { id: string; title: string };
export type AnalysisCaseLinks = Record<string, LinkedCase[]>;

export async function getModelInfo(token: string): Promise<ModelInfo> {
  const response = await authenticatedFetch("/api/model-info", token);
  await checkResponse(response);
  return (await response.json()) as ModelInfo;
}

export async function getAnalysisCaseLinks(token: string): Promise<AnalysisCaseLinks> {
  const response = await authenticatedFetch("/api/analysis-case-links", token);
  await checkResponse(response);
  return (await response.json()) as AnalysisCaseLinks;
}

export async function editInvestigationCase(
  token: string, caseId: string, title: string, description: string
): Promise<void> {
  const response = await authenticatedFetch(`/api/cases/${encodeURIComponent(caseId)}`, token, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description }),
  });
  await checkResponse(response);
}

export async function unlinkAnalysisFromCase(
  token: string, caseId: string, analysisId: string
): Promise<void> {
  const response = await authenticatedFetch(
    `/api/cases/${encodeURIComponent(caseId)}/analyses/${encodeURIComponent(analysisId)}`,
    token, { method: "DELETE" }
  );
  await checkResponse(response);
}

export async function permanentlyDeleteAnalysis(
  token: string, analysisId: string
): Promise<void> {
  const response = await authenticatedFetch(
    `/api/analyses/${encodeURIComponent(analysisId)}?confirm=true`, token,
    { method: "DELETE" }
  );
  await checkResponse(response);
}

export async function permanentlyDeleteCase(
  token: string, caseId: string, exactTitle: string
): Promise<{ deleted_case: string; deleted_analyses: number }> {
  const response = await authenticatedFetch(`/api/cases/${encodeURIComponent(caseId)}`, token, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirm_title: exactTitle, delete_analyses: true }),
  });
  await checkResponse(response);
  return (await response.json()) as { deleted_case: string; deleted_analyses: number };
}


// Investigator account settings. Endpoints enforce authenticated ownership.
export type ActiveLoginSession = {
  id: string; created_at: string; expires_at: string; is_current: boolean;
};
export type ResearchMetric = {
  model: string; n: number; threshold: number; accuracy: number;
  balanced_accuracy: number; fake_precision: number; fake_recall: number;
  fake_F1: number; ROC_AUC: number; PR_AUC: number;
  TN: number; FP: number; FN: number; TP: number;
};
export type ResearchSummary = {
  available: boolean; reason?: string; model_order?: string[];
  metrics?: ResearchMetric[]; test_count?: number | null;
  threshold?: number | null; split_counts?: {test?: {Real: number; Fake: number}};
  research_caveats?: unknown; note?: string;
};

export async function getModelResearch(token: string): Promise<ResearchSummary> {
  const response = await authenticatedFetch("/api/model-research", token);
  await checkResponse(response);
  return (await response.json()) as ResearchSummary;
}
export async function updateInvestigatorProfile(token: string, name: string): Promise<Investigator> {
  const response = await authenticatedFetch("/api/auth/profile", token, {
    method: "PATCH", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({name}),
  });
  await checkResponse(response);
  return (await response.json()) as Investigator;
}
export async function getActiveLoginSessions(token: string): Promise<ActiveLoginSession[]> {
  const response = await authenticatedFetch("/api/auth/sessions", token);
  await checkResponse(response);
  return (await response.json()) as ActiveLoginSession[];
}
export async function revokeOtherLoginSessions(token: string): Promise<number> {
  const response = await authenticatedFetch("/api/auth/sessions/revoke-others", token, {method: "POST"});
  await checkResponse(response);
  const data = (await response.json()) as {revoked: number};
  return data.revoked;
}
export async function revokeEveryLoginSession(token: string): Promise<void> {
  const response = await authenticatedFetch("/api/auth/sessions/revoke-all", token, {method: "POST"});
  await checkResponse(response);
  setAccessToken(null);
}
export async function updateInvestigatorPassword(token: string, currentPassword: string, newPassword: string): Promise<void> {
  const response = await authenticatedFetch("/api/auth/password", token, {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({current_password: currentPassword, new_password: newPassword}),
  });
  await checkResponse(response);
  setAccessToken(null);
}
