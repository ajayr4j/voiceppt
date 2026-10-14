import type { Slide } from "../types";

interface SlideViewProps {
  slide: Slide;
  total: number;
}

export function SlideView({ slide, total }: SlideViewProps) {
  return (
    <div className="slide">
      <div className="slide-counter">
        {slide.id} / {total}
      </div>
      <h1>{slide.title}</h1>
      <ul>
        {slide.bullets.map((bullet) => (
          <li key={bullet}>{bullet}</li>
        ))}
      </ul>
    </div>
  );
}
