// Pure localStorage helpers — no React. The hooks decide *when* these run;
// this file only decides *how* values are stored and read.
//
// Two things are persisted, and they must move together:
//
//   session_id   sent on every POST /query, gives the server conversational memory
//   transcript   the rendered messages
//
// The API has no endpoint to read message history back. If we persisted the
// session id alone, a reload would leave the server remembering a conversation
// the user can no longer see — the model would resolve "the second one" against
// a turn that vanished from the screen. Keeping both, or clearing both, is the
// only honest pair of states.

import type { ChatMessage } from "./types";

const SESSION_KEY = "rag_sid";
const TRANSCRIPT_PREFIX = "rag_transcript_";

export function getOrCreateSessionId(): string {
  const existing = localStorage.getItem(SESSION_KEY);
  if (existing) return existing;

  const sid = crypto.randomUUID();
  localStorage.setItem(SESSION_KEY, sid);
  return sid;
}

/** Force a fresh session id, discarding the old transcript with it. */
export function rotateSessionId(previous: string | null): string {
  if (previous) localStorage.removeItem(`${TRANSCRIPT_PREFIX}${previous}`);
  const sid = crypto.randomUUID();
  localStorage.setItem(SESSION_KEY, sid);
  return sid;
}

export function readTranscript(sessionId: string): ChatMessage[] {
  const raw = localStorage.getItem(`${TRANSCRIPT_PREFIX}${sessionId}`);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as ChatMessage[]) : [];
  } catch {
    localStorage.removeItem(`${TRANSCRIPT_PREFIX}${sessionId}`);
    return [];
  }
}

export function storeTranscript(sessionId: string, messages: ChatMessage[]): void {
  try {
    localStorage.setItem(`${TRANSCRIPT_PREFIX}${sessionId}`, JSON.stringify(messages));
  } catch {
    // Quota exceeded on a long transcript. Losing persistence is survivable;
    // the in-memory transcript is unaffected.
  }
}
