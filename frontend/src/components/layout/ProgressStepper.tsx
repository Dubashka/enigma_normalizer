import type { CSSProperties } from 'react';

interface Props {
  steps: string[];
  currentStep: number; // 1-based
}

type StepState = 'done' | 'active' | 'pending';

function getStepState(index: number, currentStep: number): StepState {
  const step = index + 1;
  if (step < currentStep) return 'done';
  if (step === currentStep) return 'active';
  return 'pending';
}

const circleBase: CSSProperties = {
  width: 28,
  height: 28,
  borderRadius: '50%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '0.75rem',
  fontWeight: 700,
  flexShrink: 0,
  position: 'relative',
  zIndex: 1,
  border: '1px solid',
};

const circleStyles: Record<StepState, CSSProperties> = {
  done: {
    ...circleBase,
    backgroundColor: 'var(--text-muted)',
    borderColor: 'var(--text-muted)',
    color: '#ffffff',
  },
  active: {
    ...circleBase,
    backgroundColor: 'var(--primary)',
    borderColor: 'var(--primary)',
    color: '#ffffff',
  },
  pending: {
    ...circleBase,
    backgroundColor: '#ffffff',
    borderColor: 'var(--text-muted)',
    color: 'var(--text-muted)',
  },
};

const labelStyles: Record<StepState, CSSProperties> = {
  done:    { fontSize: '0.7rem', color: 'var(--text-muted)', lineHeight: 1.2, marginTop: 4 },
  active:  { fontSize: '0.7rem', color: 'var(--primary)', fontWeight: 600, lineHeight: 1.2, marginTop: 4 },
  pending: { fontSize: '0.7rem', color: 'var(--text-muted)', lineHeight: 1.2, marginTop: 4 },
};

const connectorStyles: Record<'done' | 'pending', CSSProperties> = {
  done: {
    flex: 1,
    height: 1,
    backgroundColor: 'var(--primary)',
    marginBottom: 16, // align with circle center (28px / 2 = 14, label ~18px below)
  },
  pending: {
    flex: 1,
    height: 1,
    backgroundColor: 'var(--text-muted)',
    marginBottom: 16,
  },
};

export function ProgressStepper({ steps, currentStep }: Props) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        padding: '1rem 0 1.5rem',
        overflowX: 'auto',
      }}
    >
      {steps.map((label, i) => {
        const state = getStepState(i, currentStep);
        const isLast = i === steps.length - 1;
        // Connector is "done" if both this step and the next are done/active
        const connectorDone = currentStep > i + 1;

        return (
          <div
            key={label}
            style={{ display: 'flex', alignItems: 'flex-end', flex: 1, minWidth: 0 }}
          >
            {/* Step item */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
                minWidth: 72,
              }}
            >
              <div style={circleStyles[state]}>
                {state === 'done' ? '✓' : String(i + 1)}
              </div>
              <div style={labelStyles[state]}>{label}</div>
            </div>

            {/* Connector line (not after last step) */}
            {!isLast && (
              <div style={connectorStyles[connectorDone ? 'done' : 'pending']} />
            )}
          </div>
        );
      })}
    </div>
  );
}
