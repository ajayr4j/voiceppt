export interface Slide {
  id: number;
  title: string;
  bullets: string[];
}

export interface SessionResponse {
  client_secret: string;
  instructions: string;
  tools: unknown[];
}

export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "error";

export type AgentState = "idle" | "listening" | "speaking";
