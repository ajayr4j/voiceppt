import type { SessionResponse, Slide } from "./types";

// Strip any trailing slash so `${API_BASE_URL}/api/...` can't become a
// double slash (e.g. "https://host.onrender.com/" + "/api/slides" would
// 404 on FastAPI, which routes "/api/slides" but not "//api/slides").
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/+$/, "");

export async function fetchSlides(): Promise<Slide[]> {
  const response = await fetch(`${API_BASE_URL}/api/slides`);
  if (!response.ok) throw new Error(`Failed to load slides (${response.status})`);
  return response.json();
}

export async function createSession(): Promise<SessionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/session`, { method: "POST" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? `Failed to create session (${response.status})`);
  }
  return response.json();
}
