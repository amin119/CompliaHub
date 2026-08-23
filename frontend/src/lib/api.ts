const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Citation = {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  clause_number: string | null;
  path: string;
};

export type QueryResponse = {
  answer: string;
  citations: Citation[];
  conversation_id: string | null;
};

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
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
