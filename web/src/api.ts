export type UserProfile = {
  id: string;
  username: string;
  role: "admin" | "employee";
  department: string | null;
};

export type KnowledgeDocument = {
  id: string;
  title: string;
  department: string | null;
  allowed_roles: string[];
  active_version_id: string | null;
  created_at: string;
};

export type DocumentVersion = {
  id: string;
  version_number: number;
  filename: string;
  source_format: string;
  effective_date: string | null;
  status: string;
  created_at: string;
  activated_at: string | null;
  job_id: string | null;
  job_status: string | null;
  job_error: string | null;
};

export type SearchHit = {
  chunk_id: string;
  document_id: string;
  version_id: string;
  text: string;
  headings: string[];
  page_number: number | null;
  score: number;
};

export type ChatResult = {
  status: "answered" | "search_only" | "insufficient_evidence" | "invalid_citation" | "model_unavailable" | "quota_exceeded";
  answer: string | null;
  citations: SearchHit[];
  request_id: string;
  retrieval_ms: number;
  generation_ms: number;
  total_ms: number;
  model?: string;
  input_tokens?: number;
  output_tokens?: number;
};

export type AuditEvent = {
  id: string;
  actor_id: string | null;
  action: string;
  object_id: string;
  result: string;
  created_at: string;
};

export type UsageSummary = {
  day: string;
  limit: number;
  consumed_tokens: number;
  reserved_tokens: number;
  remaining_tokens: number | null;
  requests: {
    id: string;
    actor_id: string;
    status: string;
    model: string | null;
    retrieval_ms: number | null;
    generation_ms: number | null;
    total_ms: number | null;
    input_tokens: number | null;
    output_tokens: number | null;
    charged_tokens: number;
    created_at: string;
  }[];
};

export type EvaluationDashboard = {
  retrieval: {
    generated_at: string | null;
    document_count: number | null;
    chunk_count: number | null;
    question_count: number | null;
    embedding_model: string | null;
    modes: {
      id: string;
      label: string;
      recall_at_5?: number;
      mrr?: number;
      unauthorized_exposures?: number;
      latency_p50_ms?: number;
      latency_p95_ms?: number;
    }[];
  } | null;
  generation: {
    generated_at: string | null;
    model: string | null;
    selected_case_count: number | null;
    completed_count: number | null;
    pending_count: number | null;
    positive_answered: number | null;
    positive_evaluated: number | null;
    no_answer_refused: number | null;
    no_answer_evaluated: number | null;
    unauthorized_exposures: number | null;
    latency_p50_ms: number | null;
    latency_p95_ms: number | null;
    input_tokens: number | null;
    output_tokens: number | null;
    manual_answer_correctness: number | null;
    manual_citation_support: number | null;
    issues: {
      case_id: string | null;
      category: string;
      question: string;
      status: string;
      issue_type: string;
      expected_docs: string[];
    }[];
  } | null;
};

export type UploadReceipt = { document_id: string; version_id: string; job_id: string };

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function api<T>(path: string, token?: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !(init.body instanceof URLSearchParams)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`/api/v1${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof body.detail === "string" ? body.detail : `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const client = {
  async login(username: string, password: string) {
    const body = new URLSearchParams({ username, password });
    return api<{ access_token: string }>("/auth/login", undefined, { method: "POST", body });
  },
  me: (token: string) => api<UserProfile>("/auth/me", token),
  documents: (token: string) => api<KnowledgeDocument[]>("/documents", token),
  versions: (token: string, id: string) => api<DocumentVersion[]>(`/documents/${id}/versions`, token),
  audit: (token: string) => api<AuditEvent[]>("/audit", token),
  usage: (token: string) => api<UsageSummary>("/usage", token),
  evaluations: (token: string) => api<EvaluationDashboard>("/evaluations", token),
  search: (token: string, query: string) => api<SearchHit[]>("/search", token, {
    method: "POST", body: JSON.stringify({ query, limit: 6 }),
  }),
  chat: (token: string, query: string) => api<ChatResult>("/chat", token, {
    method: "POST", body: JSON.stringify({ query, limit: 6 }),
  }),
  upload: (token: string, form: FormData, documentId?: string) =>
    api<UploadReceipt>(documentId ? `/documents/${documentId}/versions` : "/documents", token, {
      method: "POST", body: form,
    }),
  activate: (token: string, id: string, versionId: string) =>
    api<{ status: string }>(`/documents/${id}/versions/${versionId}/activate`, token, { method: "POST" }),
  remove: (token: string, id: string) =>
    api<{ status: string }>(`/documents/${id}`, token, { method: "DELETE" }),
  retry: (token: string, jobId: string) =>
    api<{ status: string }>(`/jobs/${jobId}/retry`, token, { method: "POST" }),
  async source(token: string, id: string, versionId?: string): Promise<Blob> {
    const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : "";
    const response = await fetch(`/api/v1/documents/${id}/source${query}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new ApiError(response.status,
      response.status === 404 && versionId ? "该引用对应的版本已失效，请重新检索。" : "无法打开原文");
    return response.blob();
  },
};
