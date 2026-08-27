// Mirrors the RAG API contract. Field names stay snake_case where they come
// straight off the wire, so a payload can be eyeballed against the spec
// without a translation step. Only locally-derived state gets camelCase.

export type ItemStatus = "pending" | "indexing" | "indexed" | "failed";
export type ItemSourceType = "text" | "file" | "url";

export const TERMINAL_STATUSES: ItemStatus[] = ["indexed", "failed"];

export interface ItemOut {
  id: string;
  title: string;
  source_type: ItemSourceType;
  /** Set for 'file' items only. */
  filename: string | null;
  /** Set for 'file' items, and for 'url' items once the fetch completes. */
  mime_type: string | null;
  /** Set for 'url' items only. This is the URL *after* redirects. */
  source_url: string | null;
  status: ItemStatus;
  error: string | null;
  char_count: number;
  chunk_count: number;
  created_at: string;
}

export interface ItemDetail extends ItemOut {
  raw_text: string;
}

export interface ListItemsResponse {
  items: ItemOut[];
  total: number;
  indexed_chunks: number;
}

export interface IngestResponse {
  items: ItemOut[];
  /** Per-source rejection reasons, "<name>: <reason>". Warnings, not errors. */
  skipped: string[];
}

export interface Source {
  rank: number;
  chunk_id: number;
  item_id: string;
  item_title: string;
  filename: string | null;
  section_path: string;
  snippet: string;
  char_start: number;
  char_end: number;
  /** Raw cosine similarity, 0–1. Comparable across queries — safe to display. */
  similarity: number;
  /** Fusion artifact used only for ordering. Never render this. */
  score: number;
}

export interface QueryResponse {
  question: string;
  answer: string;
  sources: Source[];
  conversation_id: string | null;
  model: string;
  rag_hit: boolean;
  total_tokens: number;
  latency_ms: number;
}

export interface QueryRequest {
  question: string;
  session_id?: string;
  end_user_id?: string;
  top_k?: number;
  item_ids?: string[];
}

export interface Health {
  status: string;
  indexed_chunks: number;
  embedding_model: string | null;
  inference_provider: string;
  embedding_provider: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  ragHit?: boolean;
  model?: string;
  totalTokens?: number;
  latencyMs?: number;
}
