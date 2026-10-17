"use client";

import React, { useEffect, useState } from "react";

export function CustomCursor() {
  const [position, setPosition] = useState({ x: -100, y: -100 });
  const [trailingPos, setTrailingPos] = useState({ x: -100, y: -100 });
  const [isPointer, setIsPointer] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setPosition({ x: e.clientX, y: e.clientY });
      if (!isVisible) setIsVisible(true);

      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "BUTTON" ||
          target.tagName === "A" ||
          target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.closest("button") ||
          target.closest("a") ||
          target.getAttribute("role") === "button")
      ) {
        setIsPointer(true);
      } else {
        setIsPointer(false);
      }
    };

    const handleMouseLeave = () => setIsVisible(false);

    window.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [isVisible]);

  // Smooth trailing effect using requestAnimationFrame
  useEffect(() => {
    let animId: number;
    const animate = () => {
      setTrailingPos((prev) => ({
        x: prev.x + (position.x - prev.x) * 0.18,
        y: prev.y + (position.y - prev.y) * 0.18,
      }));
      animId = requestAnimationFrame(animate);
    };
    animId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animId);
  }, [position]);

  if (!isVisible) return null;

  return (
    <div className="pointer-events-none fixed inset-0 z-50 overflow-hidden transition-opacity duration-300">
      {/* Outer soft trailing halo */}
      <div
        className="fixed rounded-full border transition-transform duration-100 ease-out pointer-events-none"
        style={{
          left: `${trailingPos.x}px`,
          top: `${trailingPos.y}px`,
          width: isPointer ? "42px" : "28px",
          height: isPointer ? "42px" : "28px",
          transform: "translate(-50%, -50%)",
          borderColor: isPointer ? "rgba(56, 189, 248, 0.75)" : "rgba(38, 140, 245, 0.45)",
          backgroundColor: isPointer ? "rgba(56, 189, 248, 0.08)" : "transparent",
          boxShadow: isPointer ? "0 0 20px rgba(56, 189, 248, 0.4)" : "none",
        }}
      />

      {/* Center glowing precision dot */}
      <div
        className="fixed rounded-full pointer-events-none transition-transform duration-75"
        style={{
          left: `${position.x}px`,
          top: `${position.y}px`,
          width: isPointer ? "6px" : "4px",
          height: isPointer ? "6px" : "4px",
          transform: "translate(-50%, -50%)",
          backgroundColor: isPointer ? "#38bdf8" : "#82c4ff",
          boxShadow: "0 0 10px #38bdf8, 0 0 20px rgba(22, 120, 239, 0.8)",
        }}
      />
    </div>
  );
}
