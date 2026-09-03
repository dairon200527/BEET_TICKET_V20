import { IconCheckSmall } from './Icons';

// Horizontal progress stepper for multi-step flows (checkout, etc.).
// `steps` is an ordered list of { key, label }; `currentKey` marks which
// one is active — everything before it renders as done.
export default function Stepper({ steps, currentKey }) {
  const currentIndex = steps.findIndex((s) => s.key === currentKey);
  return (
    <div className="stepper" role="list">
      {steps.map((step, i) => {
        const state = i < currentIndex ? 'done' : i === currentIndex ? 'active' : 'pending';
        return (
          <div className={`stepper-item stepper-${state}`} key={step.key} role="listitem">
            <span className="stepper-dot">
              {state === 'done' ? <IconCheckSmall size={11} color="#FFFFFF" /> : i + 1}
            </span>
            <span className="stepper-label">{step.label}</span>
            {i < steps.length - 1 && <span className="stepper-line" />}
          </div>
        );
      })}
    </div>
  );
}
