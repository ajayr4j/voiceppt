import type { AgentState, ConnectionStatus } from "../types";

interface VoiceControlsProps {
  status: ConnectionStatus;
  agentState: AgentState;
  error: string | null;
  onConnect: () => void;
  onDisconnect: () => void;
}

const AGENT_STATE_LABEL: Record<AgentState, string> = {
  idle: "Idle",
  listening: "Listening…",
  speaking: "Speaking (say anything to interrupt)",
};

export function VoiceControls({ status, agentState, error, onConnect, onDisconnect }: VoiceControlsProps) {
  return (
    <div className="voice-controls">
      {status === "connected" ? (
        <>
          <span className={`agent-badge agent-badge-${agentState}`}>
            {AGENT_STATE_LABEL[agentState]}
          </span>
          <button onClick={onDisconnect}>End session</button>
        </>
      ) : (
        <button onClick={onConnect} disabled={status === "connecting"}>
          {status === "connecting" ? "Connecting…" : "Start voice session"}
        </button>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
