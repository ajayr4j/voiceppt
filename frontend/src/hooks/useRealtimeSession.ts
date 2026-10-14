import { useCallback, useRef, useState } from "react";
import { createSession } from "../api";
import type { AgentState, ConnectionStatus } from "../types";

const REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls";

interface FunctionCallItem {
  type: "function_call";
  name: string;
  call_id: string;
  arguments: string;
}

interface UseRealtimeSessionOptions {
  onShowSlide: (slideNumber: number) => void;
}

/**
 * Opens a direct browser<->OpenAI Realtime WebRTC session.
 *
 * The backend only ever mints a short-lived ephemeral token; audio flows
 * peer-to-peer from here on, which is why interruption doesn't need any
 * custom cancel/truncate logic client-side - OpenAI's server manages the
 * output buffer automatically over WebRTC on barge-in. We just listen for
 * input_audio_buffer.speech_started / response.cancelled to reflect that
 * in the UI.
 */
export function useRealtimeSession({ onShowSlide }: UseRealtimeSessionOptions) {
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const [error, setError] = useState<string | null>(null);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dcRef = useRef<RTCDataChannel | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);

  const sendEvent = useCallback((event: Record<string, unknown>) => {
    dcRef.current?.send(JSON.stringify(event));
  }, []);

  const handleServerEvent = useCallback(
    (raw: string) => {
      let event: Record<string, unknown>;
      try {
        event = JSON.parse(raw);
      } catch {
        return;
      }

      switch (event.type) {
        case "input_audio_buffer.speech_started":
          setAgentState("listening");
          break;
        case "response.created":
          setAgentState("speaking");
          break;
        case "response.done":
        case "response.cancelled":
          setAgentState("idle");
          break;
        case "error":
          setError(JSON.stringify(event.error ?? event));
          break;
        default:
          break;
      }

      if (event.type === "response.done") {
        const output = (event.response as { output?: unknown[] } | undefined)?.output ?? [];
        for (const item of output) {
          const call = item as FunctionCallItem;
          if (call.type === "function_call" && call.name === "show_slide") {
            try {
              const args = JSON.parse(call.arguments) as { slide_number: number };
              onShowSlide(args.slide_number);
              sendEvent({
                type: "conversation.item.create",
                item: {
                  type: "function_call_output",
                  call_id: call.call_id,
                  output: JSON.stringify({ ok: true }),
                },
              });
              sendEvent({ type: "response.create" });
            } catch {
              // malformed function call arguments - ignore rather than crash the session
            }
          }
        }
      }
    },
    [onShowSlide, sendEvent],
  );

  const disconnect = useCallback(() => {
    dcRef.current?.close();
    pcRef.current?.close();
    localStreamRef.current?.getTracks().forEach((track) => track.stop());
    audioElRef.current?.remove();
    dcRef.current = null;
    pcRef.current = null;
    localStreamRef.current = null;
    audioElRef.current = null;
    setStatus("idle");
    setAgentState("idle");
  }, []);

  const connect = useCallback(async () => {
    setStatus("connecting");
    setError(null);
    try {
      const session = await createSession();

      const pc = new RTCPeerConnection();
      pcRef.current = pc;

      const audioEl = document.createElement("audio");
      audioEl.autoplay = true;
      document.body.appendChild(audioEl);
      audioElRef.current = audioEl;
      pc.ontrack = (e) => {
        audioEl.srcObject = e.streams[0];
      };

      const localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      localStreamRef.current = localStream;
      localStream.getTracks().forEach((track) => pc.addTrack(track, localStream));

      const dc = pc.createDataChannel("oai-events");
      dcRef.current = dc;
      dc.onopen = () => {
        sendEvent({
          type: "session.update",
          session: {
            type: "realtime",
            instructions: session.instructions,
            tools: session.tools,
            tool_choice: "auto",
          },
        });
        sendEvent({ type: "response.create" });
      };
      dc.onmessage = (e) => handleServerEvent(e.data);

      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "failed" || pc.connectionState === "disconnected") {
          setStatus("error");
          setError("Realtime connection dropped.");
        }
      };

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const sdpResponse = await fetch(REALTIME_CALLS_URL, {
        method: "POST",
        body: offer.sdp,
        headers: {
          Authorization: `Bearer ${session.client_secret}`,
          "Content-Type": "application/sdp",
        },
      });
      if (!sdpResponse.ok) {
        throw new Error(`OpenAI rejected the WebRTC offer (${sdpResponse.status})`);
      }
      const answerSdp = await sdpResponse.text();
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });

      setStatus("connected");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : String(err));
      disconnect();
    }
  }, [disconnect, handleServerEvent, sendEvent]);

  return { status, agentState, error, connect, disconnect };
}
