// Server-only helpers for talking to the FastAPI backend. The API key is read
// from a non-public env var and never reaches the browser.
export function backend() {
  return { base: process.env.ADAM_API_URL || "", key: process.env.ADAM_API_KEY || "" };
}

export async function apiGet<T>(path: string): Promise<T | null> {
  const { base, key } = backend();
  if (!base || !key) return null;
  try {
    const res = await fetch(`${base}${path}`, { headers: { "X-API-Key": key }, cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
