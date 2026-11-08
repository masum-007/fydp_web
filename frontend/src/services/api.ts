
const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);

  return fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });
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
  };
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

export async function downloadForensicReport(
  analysisId: string,
  token: string
): Promise<void> {
  const response = await authenticatedFetch(
    `/api/report/${encodeURIComponent(analysisId)}`,
    token
  );

  await checkResponse(response);

  const blob = await response.blob();

  if (!blob.type.includes("application/pdf")) {
    throw new Error("Server did not return a PDF report.");
  }

  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = `NeuralEdge_${analysisId}.pdf`;

  document.body.appendChild(link);
  link.click();
  link.remove();

  window.setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 1000);
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
