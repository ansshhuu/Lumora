/**
 * lib/api.ts — Lumora backend API client.
 * Single-user, single-instance; no auth layer, just an API key via env var.
 *
 * All fetches go through the Next.js /api/* proxy (see next.config.ts),
 * so the browser never makes a cross-origin request — no CORS headers required.
 */

const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

export interface IndexSuccess {
  collection: string;
  itemsCount: number;
}

export interface IndexError {
  error: string;
}

export type IndexResult = IndexSuccess | IndexError;

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

