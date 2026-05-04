import { Check } from 'lucide-react'

interface StepperProps {
  steps: string[]
  current: number // 1-based
}

export function Stepper({ steps, current }: StepperProps) {
  return (
    <div className="flex items-center gap-0 overflow-x-auto pb-2">
      {steps.map((label, i) => {
        const num = i + 1
        const done = num < current
        const active = num === current

        return (
          <div key={label} className="flex items-center flex-1 min-w-[72px]">
            <div className="flex flex-col items-center flex-1">
              <div
                className={[
                  'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border z-10',
                  done
                    ? 'bg-gray-400 border-gray-400 text-white'
                    : active
                    ? 'bg-red-600 border-red-600 text-white'
                    : 'bg-white border-gray-300 text-gray-400',
                ].join(' ')}
              >
                {done ? <Check size={12} /> : num}
              </div>
              <span
                className={[
                  'text-[10px] mt-1 text-center leading-tight',
                  active ? 'text-red-600 font-semibold' : 'text-gray-400',
                ].join(' ')}
              >
                {label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div
                className={[
                  'h-px flex-1 mx-1',
                  done || active ? 'bg-red-400' : 'bg-gray-200',
                ].join(' ')}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
