import { useId } from 'react'
import { Link } from 'react-router-dom'
import type { SVGProps } from 'react'

/**
 * The app mark: a gradient "flux badge" — a rising concentration curve with gas
 * bubbles lifting off it, the visual heart of a closed-chamber flux measurement.
 * Self-contained SVG (its own gradients), so it scales and themes cleanly.
 */
export function LogoMark(props: SVGProps<SVGSVGElement>) {
  // Unique ids so multiple marks on a page don't share gradient defs.
  const uid = useId().replace(/:/g, '')
  const badge = `flux-badge-${uid}`
  const glow = `flux-glow-${uid}`
  const stroke = `flux-stroke-${uid}`
  return (
    <svg
      viewBox="0 0 40 40"
      role="img"
      aria-hidden
      focusable="false"
      {...props}
    >
      <defs>
        <linearGradient id={badge} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#0f766e" />
          <stop offset="55%" stopColor="#0d9488" />
          <stop offset="100%" stopColor="#22d3ee" />
        </linearGradient>
        <radialGradient id={glow} cx="30%" cy="22%" r="70%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.55" />
          <stop offset="60%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={stroke} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0%" stopColor="#ecfeff" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#ffffff" />
        </linearGradient>
      </defs>

      {/* Badge + soft top-left highlight for depth. */}
      <rect
        x="0"
        y="0"
        width="40"
        height="40"
        rx="11"
        fill={`url(#${badge})`}
      />
      <rect x="0" y="0" width="40" height="40" rx="11" fill={`url(#${glow})`} />

      {/* Rising concentration curve (dC/dt — the flux). */}
      <path
        d="M8 30 Q 17 29 21 20 T 33 9"
        fill="none"
        stroke={`url(#${stroke})`}
        strokeWidth="2.6"
        strokeLinecap="round"
      />

      {/* Gas bubbles lifting off, largest to smallest as they rise. */}
      <circle cx="11" cy="29" r="2.4" fill="#ffffff" fillOpacity="0.95" />
      <circle cx="20" cy="20.5" r="3.1" fill="#ffffff" />
      <circle cx="29.5" cy="11" r="2" fill="#ffffff" fillOpacity="0.9" />
    </svg>
  )
}

/** App mark + gradient wordmark; links home. */
export function Logo({ withSlogan = false }: { withSlogan?: boolean }) {
  return (
    <Link
      to="/"
      className="group flex items-center gap-2.5 rounded-lg"
      aria-label="Flux Calculation — home"
    >
      <LogoMark className="h-9 w-9 shrink-0 drop-shadow-sm transition-transform group-hover:scale-105" />
      <span className="flex flex-col leading-tight">
        <span className="bg-gradient-to-r from-[var(--primary)] to-[#22d3ee] bg-clip-text text-base font-bold tracking-tight text-transparent">
          Flux Calculation
        </span>
        {withSlogan && (
          <span className="hidden text-xs text-muted sm:inline">
            From messy field notes to clean fluxes
          </span>
        )}
      </span>
    </Link>
  )
}
