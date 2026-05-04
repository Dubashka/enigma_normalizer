import type { ReactNode } from 'react'

const VARIANTS = {
  high: 'bg-red-100 text-red-700 border border-red-300',
  medium: 'bg-purple-100 text-purple-700 border border-purple-300',
  low: 'bg-gray-100 text-gray-500 border border-gray-300',
  success: 'bg-green-100 text-green-700 border border-green-300',
  primary: 'bg-red-100 text-red-700 border border-red-300',
  neutral: 'bg-gray-100 text-gray-600 border border-gray-300',
}

type Variant = keyof typeof VARIANTS

interface BadgeProps {
  variant?: Variant
  children: ReactNode
}

export function Badge({ variant = 'neutral', children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold ${VARIANTS[variant]}`}
    >
      {children}
    </span>
  )
}
