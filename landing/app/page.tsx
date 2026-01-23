"use client";

import { useState, useEffect, useRef } from "react";
import Image from "next/image";
import dynamic from "next/dynamic";

const AudioWaveGL = dynamic(() => import("./components/AudioWaveGL"), {
  ssr: false,
});

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Custom cursor component
function CustomCursor() {
  const cursorRef = useRef<HTMLDivElement>(null);
  const position = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      position.current = { x: e.clientX, y: e.clientY };
      if (cursorRef.current) {
        cursorRef.current.style.transform = `translate(${e.clientX - 6}px, ${e.clientY - 6}px)`;
      }
    };

    window.addEventListener("mousemove", handleMouseMove);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
    };
  }, []);

  return (
    <div
      ref={cursorRef}
      className="fixed top-0 left-0 w-3 h-3 rounded-full bg-[#f95400] pointer-events-none z-[9999] hidden lg:block mix-blend-difference"
      style={{ willChange: 'transform' }}
    />
  );
}

export default function LandingPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [focused, setFocused] = useState(false);
  const [buttonHover, setButtonHover] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/miniapp/waitlist/submit/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "Something went wrong");
        setLoading(false);
        return;
      }

      if (data.telegram_url) {
        window.location.href = data.telegram_url;
      }
    } catch (err) {
      setError("Network error. Please try again.");
      setLoading(false);
    }
  };

  return (
    <>
      {/* Custom cursor */}
      <CustomCursor />

      <main className="h-screen h-[100dvh] w-full bg-[#0a0a0a] relative overflow-hidden cursor-none lg:cursor-none">
        {/* WebGL Background - Full screen behind everything */}
      <div className="fixed inset-0 pointer-events-none">
        <AudioWaveGL />
      </div>

      {/* Gradient overlay for depth */}
      <div className="fixed inset-0 pointer-events-none bg-gradient-to-t from-[#0a0a0a] via-transparent to-[#0a0a0a]/80" />

      {/* Grain texture overlay - subtle soft grain */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.12] mix-blend-soft-light"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.5' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'repeat',
          backgroundSize: '256px 256px',
        }}
      />
      {/* Second grain layer for subtle depth */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.08] mix-blend-overlay"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise2'%3E%3CfeTurbulence type='turbulence' baseFrequency='0.6' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise2)'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'repeat',
          backgroundSize: '200px 200px',
        }}
      />

      {/* Vignette effect */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 0%, transparent 40%, rgba(0,0,0,0.4) 100%)',
        }}
      />

      {/* Content wrapper */}
      <div className="relative z-10 h-screen h-[100dvh] flex flex-col overflow-hidden">
        {/* Header */}
        <header
          className={`
            flex items-center justify-between flex-shrink-0
            transition-all duration-1000 ease-out
            ${mounted ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-4"}
          `}
          style={{
            paddingLeft: 'clamp(1.25rem, 5vw, 7rem)',
            paddingRight: 'clamp(1.25rem, 5vw, 7rem)',
            paddingTop: 'clamp(1rem, 3vh, 3rem)',
            paddingBottom: 'clamp(0.5rem, 1.5vh, 1.5rem)'
          }}
        >
          <div className="flex items-center gap-2 group cursor-pointer relative">
            <div className="relative" style={{ width: 'clamp(32px, 5vw, 44px)', height: 'clamp(32px, 5vw, 44px)' }}>
              <Image
                src="/loudrr-icon.png"
                alt="Loudrr"
                fill
                priority
                className="transition-opacity duration-500 object-contain"
              />
              <div className="absolute inset-0 bg-[#f95400] rounded-full blur-xl opacity-30 group-hover:opacity-50 transition-opacity duration-500" />
            </div>
            <span className="font-syne font-bold text-[#f95400] tracking-tight" style={{ fontSize: 'clamp(1.25rem, 3vw, 1.5rem)' }}>
              Loudrr
            </span>

          </div>

          {/* Social buttons */}
          <div className="flex items-center gap-2">
            {/* X/Twitter button */}
            <a
              href="https://x.com/loudrrHQ"
              target="_blank"
              rel="noopener noreferrer"
              className="
                text-white/70 hover:text-white
                rounded-xl
                transition-all duration-300
                border border-white/10 hover:border-white/20
                bg-white/[0.02] hover:bg-white/[0.05]
                active:scale-[0.98]
                focus:outline-none focus:ring-0
                flex items-center justify-center
              "
              style={{
                width: 'clamp(36px, 5vw, 44px)',
                height: 'clamp(36px, 5vw, 44px)',
              }}
            >
              <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
              </svg>
            </a>

            {/* Contact button */}
            <a
              href="https://t.me/loudrrteam"
              target="_blank"
              rel="noopener noreferrer"
              className="
                text-white/70 hover:text-white font-syne font-medium
                rounded-xl
                transition-all duration-300
                border border-white/10 hover:border-white/20
                bg-white/[0.02] hover:bg-white/[0.05]
                active:scale-[0.98]
                whitespace-nowrap
                focus:outline-none focus:ring-0
                flex items-center justify-center gap-2
              "
              style={{
                fontSize: 'clamp(11px, 1.8vw, 14px)',
                height: 'clamp(36px, 5vw, 44px)',
                paddingLeft: 'clamp(10px, 1.5vw, 12px)',
                paddingRight: 'clamp(14px, 2vw, 18px)',
              }}
            >
              <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 24 24" fill="currentColor">
                <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
              </svg>
              <span>Contact</span>
            </a>
          </div>
        </header>

        {/* Main content */}
        <div
          className="flex-1 flex flex-col justify-center min-h-0"
          style={{
            paddingLeft: 'clamp(1.25rem, 5vw, 7rem)',
            paddingRight: 'clamp(1.25rem, 5vw, 7rem)',
            paddingTop: 'clamp(1rem, 3vh, 3rem)',
            paddingBottom: 'clamp(1rem, 3vh, 3rem)'
          }}
        >
          {/* Hero text */}
          <div className="max-w-4xl">
            <h1
              className={`
                font-syne font-bold text-white
                leading-[0.95] tracking-[-0.02em]
                transition-all duration-1000 ease-out delay-200
                ${mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"}
              `}
              style={{ fontSize: 'clamp(2rem, 8vw, 6rem)' }}
            >
              Stand out{" "}
              <span className="text-[#f95400] inline-block hover:scale-105 transition-transform duration-300 cursor-default">
                Go Loudrr
              </span>
            </h1>
            <p
              className={`
                text-white/40 font-medium
                transition-all duration-1000 ease-out delay-300
                ${mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"}
              `}
              style={{ fontSize: 'clamp(1rem, 2.5vw, 1.5rem)', marginTop: 'clamp(0.25rem, 0.5vw, 0.5rem)' }}
            >
              For creators who lead.
            </p>
          </div>

          {/* Email form - awwwards style */}
          <form
            onSubmit={handleSubmit}
            className={`
              transition-all duration-1000 ease-out delay-500
              ${mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"}
            `}
            style={{ marginTop: 'clamp(1.5rem, 4vh, 3rem)' }}
          >
            <div
              className={`
                relative flex items-center
                bg-white/[0.03]
                backdrop-blur-md
                transition-all duration-500 ease-out
                overflow-hidden
                group
              `}
              style={{
                height: 'clamp(52px, 7vw, 64px)',
                borderRadius: 'clamp(14px, 2vw, 18px)',
                border: focused
                  ? '1px solid rgba(255, 255, 255, 0.15)'
                  : '1px solid rgba(255, 255, 255, 0.06)',
                boxShadow: focused
                  ? '0 20px 40px rgba(0, 0, 0, 0.3)'
                  : '0 10px 30px rgba(0, 0, 0, 0.2)',
                maxWidth: 'clamp(320px, 50vw, 480px)',
              }}
            >
              {/* Email icon */}
              <div
                className="flex-shrink-0 flex items-center justify-center text-white/30 transition-colors duration-300"
                style={{
                  width: 'clamp(44px, 6vw, 56px)',
                }}
              >
                <svg
                  className="transition-all duration-300"
                  style={{ width: 'clamp(18px, 2.5vw, 22px)', height: 'clamp(18px, 2.5vw, 22px)' }}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect x="2" y="4" width="20" height="16" rx="3" />
                  <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
                </svg>
              </div>

              {/* Input */}
              <input
                ref={inputRef}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                placeholder="Enter your email"
                required
                disabled={loading}
                className="
                  flex-1 min-w-0
                  bg-transparent text-white
                  placeholder:text-white/25
                  focus:outline-none focus:ring-0
                  disabled:opacity-50
                "
                style={{
                  fontSize: 'clamp(14px, 2vw, 16px)',
                  fontWeight: 400,
                  letterSpacing: '0.01em',
                }}
              />

              {/* Button */}
              <button
                type="submit"
                disabled={loading || !email.trim()}
                onMouseEnter={() => setButtonHover(true)}
                onMouseLeave={() => setButtonHover(false)}
                className="
                  flex-shrink-0
                  text-black font-syne font-bold
                  transition-all duration-300
                  disabled:opacity-30 disabled:cursor-not-allowed
                  hover:scale-[1.02]
                  active:scale-[0.98]
                  whitespace-nowrap
                  focus:outline-none focus:ring-0
                "
                style={{
                  background: 'linear-gradient(135deg, #ff6b1a 0%, #f95400 50%, #cc4400 100%)',
                  fontSize: 'clamp(12px, 1.8vw, 14px)',
                  height: 'clamp(36px, 5vw, 44px)',
                  padding: '0 clamp(16px, 2.5vw, 24px)',
                  borderRadius: 'clamp(10px, 1.5vw, 14px)',
                  marginRight: 'clamp(6px, 1vw, 10px)',
                  boxShadow: '0 4px 20px rgba(249, 84, 0, 0.3)',
                }}
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                  </span>
                ) : (
                  "Join Waitlist"
                )}
              </button>
            </div>

            {/* Error message */}
            {error && (
              <p className="text-red-400 animate-shake mt-3" style={{ fontSize: 'clamp(11px, 1.5vw, 14px)' }}>{error}</p>
            )}

            {/* Helper text - only show after valid email entered */}
            {email.trim() && email.includes('@') && (
              <p className="text-white/20 mt-3" style={{ fontSize: 'clamp(11px, 1.5vw, 13px)' }}>
                Join Telegram to complete waitlist application.
              </p>
            )}
          </form>
        </div>

        {/* Footer */}
        <footer
          className={`
            flex-shrink-0
            flex items-center justify-between
            transition-all duration-1000 ease-out delay-700
            ${mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}
          `}
          style={{
            paddingLeft: 'clamp(1.25rem, 5vw, 7rem)',
            paddingRight: 'clamp(1.25rem, 5vw, 7rem)',
            paddingTop: 'clamp(1rem, 2vh, 2rem)',
            paddingBottom: 'clamp(1rem, 3vh, 2.5rem)'
          }}
        >
          <p className="text-white/20" style={{ fontSize: 'clamp(11px, 1.5vw, 14px)' }}>
            built to make communities louder, together.
          </p>

          <span className="text-white/15" style={{ fontSize: 'clamp(10px, 1.3vw, 12px)' }}>© 2025 Loudrr</span>
        </footer>
      </div>
    </main>
    </>
  );
}
