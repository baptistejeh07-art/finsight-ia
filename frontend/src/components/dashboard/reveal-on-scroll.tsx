"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Wrap children pour ne les monter qu'à l'entrée dans le viewport.
 * Permet aux animations natives Recharts (mount-driven) ou aux animations CSS
 * de jouer quand l'utilisateur scroll jusqu'à l'élément.
 */
export function RevealOnScroll({
  children,
  className = "",
  rootMargin = "-80px 0px",
}: {
  children: React.ReactNode;
  className?: string;
  rootMargin?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!ref.current) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { rootMargin, threshold: 0.05 }
    );
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, [rootMargin]);

  return (
    <div
      ref={ref}
      className={`transition-all duration-700 ease-out ${
        visible
          ? "opacity-100 translate-y-0"
          : "opacity-0 translate-y-4"
      } ${className}`}
    >
      {visible ? children : <div className="invisible">{children}</div>}
    </div>
  );
}
