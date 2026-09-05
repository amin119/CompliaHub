const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Citation = {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  clause_number: string | null;
  path: string;
};

export type GraphNode = {
  id: string;
  name: string;
  entity_type: string;
};

export type GraphEdge = {
  source: string;
  target: string;
  relation_type: string;
  chunk_id: string | null;
};

export type GraphEvidence = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type QueryResponse = {
  answer: string;
  citations: Citation[];
  conversation_id: string | null;
  graph_evidence: GraphEvidence;
};

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    // FastAPI's own request-validation errors (422) shape `detail` as a
    // list of {loc, msg, type} objects, not a string — e.g. Phase 7's
    // review form needs the actual "notes must be a substantive
    // justification" message, not a generic "Request failed (422)".
    if (Array.isArray(body?.detail) && typeof body.detail[0]?.msg === "string") {
      return body.detail[0].msg;
    }
  } catch {
    // response body wasn't JSON — fall through to the generic message
  }
  return `Request failed (${response.status})`;
}

export async function askQuestion(
  question: string,
  conversationId: string | null,
): Promise<QueryResponse> {
  const response = await fetch(`${API_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, conversation_id: conversationId }),
  });
  if (!response.ok) throw new Error(await parseErrorDetail(response));
  return response.json();
}

export type StreamEvent =
  | { type: "status"; stage: string }
  | { type: "token"; text: string }
  | {
      type: "done";
      conversation_id: string;
      citations: Citation[];
      graph_evidence: GraphEvidence;
    }
  | { type: "error"; message: string };

/**
 * Phase 6 Part 2: consumes `POST /query/stream`'s Server-Sent Events. A
 * plain `fetch()` + `ReadableStream`, not the browser's `EventSource` —
 * `EventSource` only supports GET, and the question has to go in the body.
 *
 * SSE frames are separated by a blank line and may arrive split across
 * multiple stream chunks (or several frames in one chunk), so this buffers
 * decoded text and only emits once a full `\n\n`-terminated frame is seen.
 */
export async function streamQuestion(
  question: string,
  conversationId: string | null,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_URL}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, conversation_id: conversationId }),
    signal,
  });
  if (!response.ok || !response.body) {
    onEvent({ type: "error", message: await parseErrorDetail(response) });
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const dataLine = frame.split("\n").find((line) => line.startsWith("data: "));
      if (dataLine) {
        onEvent(JSON.parse(dataLine.slice("data: ".length)) as StreamEvent);
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export type DocumentStatus = {
  id: string;
  filename: string;
  status: string;
  error_message: string | null;
  graph_status: string;
  graph_error_message: string | null;
  created_at: string;
  updated_at: string;
};

export async function uploadDocument(file: File): Promise<DocumentStatus> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_URL}/documents`, { method: "POST", body: formData });
  if (!response.ok) throw new Error(await parseErrorDetail(response));
  return response.json();
}

export async function getDocument(id: string): Promise<DocumentStatus> {
  const response = await fetch(`${API_URL}/documents/${id}`);
  if (!response.ok) throw new Error(await parseErrorDetail(response));
  return response.json();
}

export type DocumentChunk = {
  id: string;
  clause_number: string | null;
  title: string | null;
  text: string;
  path: string;
  order_in_parent: number;
};

export async function getDocumentChunks(documentId: string): Promise<DocumentChunk[]> {
  const response = await fetch(`${API_URL}/documents/${documentId}/chunks`);
  if (!response.ok) throw new Error(await parseErrorDetail(response));
  return response.json();
}

export type ScanStatus = {
  id: string;
  repository_name: string | null;
  source_type: string;
  original_filename: string;
  status: string;
  error_message: string | null;
  file_count: number | null;
  total_size_bytes: number | null;
  detected_languages: string[];
  detected_frameworks: string[];
  findings_status: string;
  findings_error_message: string | null;
  privacy_status: string;
  privacy_error_message: string | null;
  ai_status: string;
  ai_error_message: string | null;
  iso27001_status: string;
  iso27001_error_message: string | null;
  created_at: string;
  updated_at: string;
};

export async function uploadScan(file: File): Promise<ScanStatus> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_URL}/scans`, { method: "POST", body: formData });
  if (!response.ok) throw new Error(await parseErrorDetail(response));
  return response.json();
}

export async function getScan(id: string): Promise<ScanStatus> {
  const response = await fetch(`${API_URL}/scans/${id}`);
  if (!response.ok) throw new Error(await parseErrorDetail(response));
  return response.json();
}

export async function listScans(): Promise<ScanStatus[]> {
  const response = await fetch(`${API_URL}/scans`);
  if (!response.ok) throw new Error(await parseErrorDetail(response));
  return response.json();
}

export type RepositoryFile = {
  id: string;
  relative_path: string;
  language: string | null;
  component_type: string;
  size_bytes: number;
  content_stored: boolean;
};

export async function getScanFiles(
  scanId: string,
  componentType?: string,
): Promise<RepositoryFile[]> {
  const query = componentType ? `?component_type=${encodeURIComponent(componentType)}` : "";
  const response = await fetch(`${API_URL}/scans/${scanId}/files${query}`);
  if (!response.ok) throw new Error(await parseErrorDetail(response));
  return response.json();
}

export type Finding = {
  id: string;
  framework: string | null;
  category: string;
  rule_id: string;
  title: string;
  status: string;
  severity: string;
  confidence: string;
  summary: string;
  recommendation: string | null;
  automated: boolean;
  human_review_required: boolean;
  created_at: string;
};

export type EvidenceItem = {
  id: string;
  source_type: string | null;
  rule_id: string | null;
  file_path: string | null;
  line_start: number | null;
  line_end: number | null;
  snippet: string | null;
  description: string;
  confidence: string | null;
  evidence_metadata: Record<string, unknown> | null;
};

export type FindingReview = {
  id: string;
  finding_id: string;
  reviewer_name: string | null;
  decision: string;
  notes: string;
  previous_status: string | null;
  created_at: string;
};

export type FindingDetail = Finding & {
  reasoning: string;
  evidence: EvidenceItem[];
  reviews: FindingReview[];
};

export async function getScanFindings(
  scanId: string,
  filters?: { severity?: string; status?: string; category?: string; framework?: string },
): Promise<Finding[]> {
  const params = new URLSearchParams();
  if (filters?.severity) params.set("severity", filters.severity);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.category) params.set("category", filters.category);
  if (filters?.framework) params.set("framework", filters.framework);
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_URL}/scans/${scanId}/findings${query}`);
  if (!response.ok) throw new Error(await parseErrorDetail(response));
  return response.json();
}

export async function getScanFinding(scanId: string, findingId: string): Promise<FindingDetail> {
  const response = await fetch(`${API_URL}/scans/${scanId}/findings/${findingId}`);
  if (!response.ok) throw new Error(await parseErrorDetail(response));
  return response.json();
}

export class ValidateFindingError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function validateFinding(
  scanId: string,
  findingId: string,
): Promise<EvidenceItem> {
  const response = await fetch(`${API_URL}/scans/${scanId}/findings/${findingId}/validate`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new ValidateFindingError(await parseErrorDetail(response), response.status);
  }
  return response.json();
}

export class ReviewFindingError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function submitFindingReview(
  scanId: string,
  findingId: string,
  payload: { reviewer_name?: string | null; decision: string; notes: string },
): Promise<FindingReview> {
  const response = await fetch(`${API_URL}/scans/${scanId}/findings/${findingId}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new ReviewFindingError(await parseErrorDetail(response), response.status);
  }
  return response.json();
}

export type SeverityCount = { severity: string; count: number };
export type FindingStatusCount = { status: string; count: number };
export type FrameworkCount = { framework: string | null; count: number };
export type ReviewCoverage = {
  total_findings: number;
  reviewed_findings: number;
  unreviewed_findings: number;
  requires_human_review_count: number;
  requires_human_review_unreviewed_count: number;
  total_reviews: number;
};

export type ScanSummary = {
  scan_id: string;
  original_filename: string;
  repository_name: string | null;
  detected_languages: string[];
  detected_frameworks: string[];
  file_count: number | null;
  total_size_bytes: number | null;
  status: string;
  findings_status: string;
  privacy_status: string;
  ai_status: string;
  iso27001_status: string;
  generated_at: string;
  total_findings: number;
  severity_counts: SeverityCount[];
  status_counts: FindingStatusCount[];
  framework_counts: FrameworkCount[];
  review_coverage: ReviewCoverage;
};

export async function getScanSummary(scanId: string): Promise<ScanSummary> {
  const response = await fetch(`${API_URL}/scans/${scanId}/summary`);
  if (!response.ok) throw new Error(await parseErrorDetail(response));
  return response.json();
}
