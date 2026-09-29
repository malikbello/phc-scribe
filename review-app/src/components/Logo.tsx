export function Logo({ size = 48, spin = false }: { size?: number; spin?: boolean }) {
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      {spin && (
        <div
          aria-hidden
          className="absolute -inset-1 animate-spinslow rounded-[22px] bg-[conic-gradient(from_0deg,#3ee6a8,#22d3ee,#c084fc,#3ee6a8)] opacity-70 blur-[6px]"
        />
      )}
      <div className="relative grid h-full w-full place-items-center rounded-[18px] bg-night-900 ring-1 ring-white/15">
        <svg viewBox="0 0 64 64" className="h-[62%] w-[62%]" aria-hidden>
          <defs>
            <linearGradient id="logo-g" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#3ee6a8" />
              <stop offset="1" stopColor="#22d3ee" />
            </linearGradient>
          </defs>
          <path d="M10 36c8 0 10-14 16-14s9 20 18 20" fill="none" stroke="url(#logo-g)" strokeWidth="6" strokeLinecap="round" />
          <circle cx="50" cy="18" r="6" fill="#ffc542" />
        </svg>
      </div>
    </div>
  );
}
