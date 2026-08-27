import { request, json } from "./client";
import type {
  Health,
  IngestResponse,
  ItemDetail,
  ItemStatus,
  ListItemsResponse,
  QueryRequest,
  QueryResponse,
} from "../types";

// ─── Items ──────────────────────────────────────────────────────────────────

export function listItems(
  params: { status?: ItemStatus; limit?: number; offset?: number } = {},
  signal?: AbortSignal,
): Promise<ListItemsResponse> {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.limit != null) qs.set("limit", String(params.limit));
  if (params.offset != null) qs.set("offset", String(params.offset));
  const suffix = qs.toString() ? `?${qs}` : "";
  return request<ListItemsResponse>(`/items${suffix}`, { signal });
}

export function getItem(itemId: string, signal?: AbortSignal): Promise<ItemDetail> {
  return request<ItemDetail>(`/items/${itemId}`, { signal });
}

export function deleteItem(itemId: string): Promise<void> {
  return request<void>(`/items/${itemId}`, { method: "DELETE" });
}

/**
 * Pasted text, dropped files and URLs all go up in one multipart request —
 * 'text' once, 'files' repeated per file, 'urls' repeated per URL. Any may be
 * omitted, but not all three.
 *
 * URL syntax is validated synchronously; the fetch itself happens in the
 * background, so a slow page never holds this request open.
 */
export function ingest(
  input: { text?: string; title?: string; files?: File[]; urls?: string[] },
  signal?: AbortSignal,
): Promise<IngestResponse> {
  const form = new FormData();
  if (input.text?.trim()) form.append("text", input.text.trim());
  if (input.title?.trim()) form.append("title", input.title.trim());
  for (const file of input.files ?? []) form.append("files", file);
  for (const url of input.urls ?? []) {
    const trimmed = url.trim();
    if (trimmed) form.append("urls", trimmed);
  }

  return request<IngestResponse>("/ingest", { method: "POST", body: form, signal });
}

// ─── Query ──────────────────────────────────────────────────────────────────

export function askQuestion(body: QueryRequest, signal?: AbortSignal): Promise<QueryResponse> {
  return request<QueryResponse>("/query", { ...json(body), signal });
}

export function getHealth(signal?: AbortSignal): Promise<Health> {
  return request<Health>("/health", { signal });
}
