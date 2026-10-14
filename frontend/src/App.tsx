import { useCallback, useEffect, useState } from "react";
import "./App.css";
import { fetchSlides } from "./api";
import { SlideView } from "./components/SlideView";
import { VoiceControls } from "./components/VoiceControls";
import { useRealtimeSession } from "./hooks/useRealtimeSession";
import type { Slide } from "./types";

export default function App() {
  const [slides, setSlides] = useState<Slide[]>([]);
  const [currentSlideId, setCurrentSlideId] = useState(1);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    fetchSlides()
      .then(setSlides)
      .catch((err) => setLoadError(err instanceof Error ? err.message : String(err)));
  }, []);

  const onShowSlide = useCallback((slideNumber: number) => {
    setCurrentSlideId(slideNumber);
  }, []);

  const { status, agentState, error, connect, disconnect } = useRealtimeSession({ onShowSlide });

  const currentSlide = slides.find((s) => s.id === currentSlideId);

  return (
    <div className="app">
      <header>
        <h2>voiceppt</h2>
        <VoiceControls
          status={status}
          agentState={agentState}
          error={error}
          onConnect={connect}
          onDisconnect={disconnect}
        />
      </header>

      {loadError && <p className="error">Could not load slides: {loadError}</p>}

      {currentSlide && <SlideView slide={currentSlide} total={slides.length} />}

      <nav className="slide-nav">
        {slides.map((slide) => (
          <button
            key={slide.id}
            className={slide.id === currentSlideId ? "active" : ""}
            onClick={() => setCurrentSlideId(slide.id)}
          >
            {slide.id}
          </button>
        ))}
      </nav>
    </div>
  );
}
