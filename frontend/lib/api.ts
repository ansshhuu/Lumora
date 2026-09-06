/**
 * lib/api.ts — Lumora backend API client.
 * Single-user, single-instance; no auth layer, just an API key via env var.
 *
 * All fetches go through the Next.js /api/* proxy (see next.config.ts),
 * so the browser never makes a cross-origin request — no CORS headers required.
 */

import { QueryEvent } from "@/lib/types";

const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

export interface IndexSuccess {
  collection: string;
  itemsCount: number;
}

export interface IndexError {
  error: string;
}

export type IndexResult = IndexSuccess | IndexError;

// ── Query types ─────────────────────────────────────────────────────────────

export interface QuerySuccess {
  answer: string;
}

export interface QueryError {
  error: string;
}

export type QueryResult = QuerySuccess | QueryError;

export function isQueryError(r: QueryResult): r is QueryError {
  return "error" in r;
}

export function isIndexError(r: IndexResult): r is IndexError {
  return "error" in r;
}

/**
 * POST /index — Index a GitHub repository.
 * Returns the collection name and item count on success,
 * or an { error } object with the message from the API body on failure.
 */
export async function indexRepo(
  repoUrl: string,
  apiKey: string = API_KEY
): Promise<IndexResult> {
  try {
    const res = await fetch("/api/index", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
      },
      body: JSON.stringify({ repo_url: repoUrl }),
    });

    if (!res.ok) {
      // Extract the real error message from the response body.
      let message = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        message = body.detail ?? body.message ?? body.error ?? JSON.stringify(body);
      } catch {
        try {
          message = await res.text();
        } catch {
          /* leave message as the HTTP status */
        }
      }
      return { error: message };
    }

    const data = await res.json();
    return {
      collection: data.collection ?? data.collection_name ?? "",
      itemsCount: data.items_count ?? data.itemsCount ?? 0,
    };
  } catch (err: unknown) {
    // Network-level failure — surface the real cause, not a generic message.
    const message =
      err instanceof Error ? err.message : "network error — could not reach backend";
    return { error: message };
  }
}

/**
 * Splits a raw SSE byte stream into decoded event payloads.
 *
 * Frames are delimited by a blank line and can straddle chunk boundaries, so
 * bytes are buffered until a full blank-line terminator arrives rather than
 * assuming one network chunk equals one event.
 */
async function* readSseEvents(
  body: ReadableStream<Uint8Array>
): AsyncGenerator<QueryEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // Normalise CRLF: the SSE spec allows \r\n line endings, which would
      // otherwise slip past the \n\n frame boundary and the "data:" prefix test.
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");

        // A frame may carry comment or `event:` lines too; only `data:` matters.
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trim())
          .join("\n");

        if (!data) continue;
        try {
          yield JSON.parse(data) as QueryEvent;
        } catch (err) {
          // A malformed frame shouldn't kill an otherwise healthy stream, but
          // it must never fail silently either: a shape mismatch between this
          // client and the backend shows up here first, and swallowing it is
          // what makes that class of bug invisible.
          console.error("[queryRepo] discarded unparseable SSE frame:", data, err);
        }
      }
    }
  } finally {
    // Releasing the lock lets an early `break` by the caller cancel the body
    // instead of leaving the connection dangling.
    reader.releaseLock();
  }
}

/**
 * POST /query — Ask a question about an indexed repository.
 *
 * The backend answers with a Server-Sent Events stream, so `onEvent` fires for
 * each reasoning step as it happens (tool_call / tool_result) and finally for
 * the answer. Resolves once the stream closes; transport-level failures come
 * back as an { error } object, matching indexRepo().
 *
 * A `retry` event means the backend threw away the attempt it was streaming
 * and started again, so any steps delivered before it should be discarded.
 *
 * EventSource isn't usable here: it only issues GET requests and cannot send
 * the X-API-Key header, so this reads the response body stream directly.
 */
export async function queryRepo(
  question: string,
  collection: string,
  onEvent: (event: QueryEvent) => void,
  apiKey: string = API_KEY,
  signal?: AbortSignal
): Promise<QueryResult> {
  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(apiKey ? { "X-API-Key": apiKey } : {}),
      },
      body: JSON.stringify({ question, collection }),
      signal,
    });

    if (!res.ok) {
      // Pre-stream failures (401, 404, 422, 429) still arrive as JSON.
      let message = `HTTP ${res.status}`;
      try {
        const body = await res.json();
        message = body.detail ?? body.message ?? body.error ?? JSON.stringify(body);
      } catch {
        try {
          message = await res.text();
        } catch {
          /* leave message as the HTTP status */
        }
      }
      return { error: message };
    }

    if (!res.body) {
      return { error: "streaming is not supported in this browser" };
    }

    // A 200 that isn't an event stream means this client and the server
    // disagree about the contract — most often a stale backend still serving
    // the old flat {"answer": "..."} JSON. Parsing it as SSE would yield zero
    // frames and render nothing, so fail loudly with the body in hand.
    const contentType = res.headers.get("content-type") ?? "";
    if (!contentType.includes("text/event-stream")) {
      const raw = await res.text();
      console.error(
        `[queryRepo] expected text/event-stream, got "${contentType}". ` +
          "Is the backend running the current build?",
        raw
      );
      try {
        const legacy = JSON.parse(raw);
        if (typeof legacy?.answer === "string") {
          return {
            error:
              "backend returned a non-streaming response — it is running an " +
              "older build of /query. Rebuild and restart the API container.",
          };
        }
      } catch {
        /* not JSON either; fall through to the generic message */
      }
      return { error: `unexpected response type "${contentType}" from /query` };
    }

    let answer = "";
    let sawFinalAnswer = false;
    for await (const event of readSseEvents(res.body)) {
      // Errors raised after the 200 status line arrive as a terminal event.
      if (event.type === "error") {
        console.error("[queryRepo] backend error event:", event.message);
        return { error: event.message };
      }
      if (event.type === "final_answer") {
        answer = event.text;
        sawFinalAnswer = true;
      }
      onEvent(event);
    }

    // A stream that closes without a terminal answer would otherwise leave the
    // panel stuck on its empty state with no explanation.
    if (!sawFinalAnswer) {
      console.error("[queryRepo] stream closed with no final_answer event");
      return { error: "the answer stream ended before an answer arrived" };
    }

    return { answer };
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      return { error: "cancelled" };
    }
    console.error("[queryRepo] request failed:", err);
    const message =
      err instanceof Error ? err.message : "network error — could not reach backend";
    return { error: message };
  }
}
