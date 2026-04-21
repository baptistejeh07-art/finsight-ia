"use client";

import { useEffect, useState, useRef } from "react";
import { QUOTES } from "@/data/quotes";

const ROTATION_MS = 3 * 60 * 1000;       // 3 minutes
const FADE_MS = 600;                      // transition fondu

/**
 * Citation tournante : rotation aléatoire toutes les 3 minutes avec fondu.
 * Évite de re-tirer la même citation 2 fois de suite.
 */
export function CitationBlock() {
  const [idx, setIdx] = useState(0);
  const [fading, setFading] = useState(false);
  const lastIdxRef = useRef<number>(-1);

  function pickNew() {
    if (QUOTES.length <= 1) return 0;
    let next = Math.floor(Math.random() * QUOTES.length);
    // Évite de retomber sur la même citation
    while (next === lastIdxRef.current) {
      next = Math.floor(Math.random() * QUOTES.length);
    }
    lastIdxRef.current = next;
    return next;
  }

  useEffect(() => {
    // Premier tirage au mount
    setIdx(pickNew());

    const interval = setInterval(() => {
      setFading(true);
      setTimeout(() => {
        setIdx(pickNew());
        setFading(false);
      }, FADE_MS);
    }, ROTATION_MS);

    return () => clearInterval(interval);
  }, []);

  const q = QUOTES[idx];

  return (
    <div
      className="text-center transition-opacity"
      style={{
        opacity: fading ? 0 : 1,
        transitionDuration: `${FADE_MS}ms`,
      }}
    >
      <div
        style={{
          fontSize: "13px",
          fontWeight: 300,
          fontStyle: "italic",
          lineHeight: "1.7",
          color: "#777",
          marginBottom: "8px",
        }}
      >
        « {q.text} »
      </div>
      <div
        style={{
          fontSize: "10px",
          fontWeight: 500,
          color: "#999",
          letterSpacing: "1px",
          textTransform: "uppercase",
        }}
      >
        {q.author}
      </div>
    </div>
  );
}
