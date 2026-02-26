import type { NodeState } from '../types';
import { stateToBg } from '../utils/status';

export default function StatusChip({ state }: { state: NodeState }) {
  const color = stateToBg(state);
  return (
    <span className="badge font-mono" style={{ color }}>
      {state}
    </span>
  );
}
