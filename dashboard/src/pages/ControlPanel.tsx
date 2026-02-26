import { useMemo, useState } from 'react';
import { useNodesStore } from '../store/nodesStore';
import { selectBreaker, operateBreaker } from '../api/control';
import { useAuthStore } from '../store/authStore';

export default function ControlPanel() {
  const nodes = useNodesStore((state) => state.nodes);
  const user = useAuthStore((state) => state.user);
  const [nodeId, setNodeId] = useState(nodes[0]?.node_id || 'GEN-001');
  const [breakerId, setBreakerId] = useState('BRK-01');
  const [action, setAction] = useState<'open' | 'close'>('open');
  const [reason, setReason] = useState('');
  const [countdown, setCountdown] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [result, setResult] = useState<string>('');
  const [responseMs, setResponseMs] = useState<number | null>(null);
  const [audit, setAudit] = useState<Array<Record<string, string>>>([]);

  const nodeOptions = useMemo(() => nodes.map((node) => node.node_id), [nodes]);

  const onSelect = async () => {
    if (!user) {
      return;
    }

    const response = await selectBreaker({
      node_id: nodeId,
      breaker_id: breakerId,
      action,
      operator_id: user.username,
      reason,
    });

    setSessionId(response.session_id);
    setCountdown(Math.floor(response.time_remaining_s));
    setResult('');
    setResponseMs(null);

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const onOperate = async () => {
    if (!sessionId || !user) {
      return;
    }

    const response = await operateBreaker({
      session_id: sessionId,
      operator_id: user.username,
    });

    setResult(response.result);
    setResponseMs(response.response_time_ms);
    setAudit((state) => [
      {
        time: new Date().toLocaleTimeString(),
        node: nodeId,
        breaker: breakerId,
        action,
        result: response.result,
      },
      ...state,
    ]);
  };

  return (
    <div className="space-y-6">
      <div className="panel p-6">
        <div className="text-lg font-mono">Breaker Control (SBO)</div>
        <div className="grid grid-cols-4 gap-4 mt-4">
          <div>
            <label className="text-xs text-gray-400">Node</label>
            <select
              className="mt-1 w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm"
              value={nodeId}
              onChange={(event) => setNodeId(event.target.value)}
            >
              {nodeOptions.map((node) => (
                <option key={node} value={node}>
                  {node}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400">Breaker</label>
            <input
              className="mt-1 w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm"
              value={breakerId}
              onChange={(event) => setBreakerId(event.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-gray-400">Action</label>
            <select
              className="mt-1 w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm"
              value={action}
              onChange={(event) => setAction(event.target.value as 'open' | 'close')}
            >
              <option value="open">Open</option>
              <option value="close">Close</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400">Reason</label>
            <input
              className="mt-1 w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Routine switching"
            />
          </div>
        </div>

        <div className="flex items-center gap-4 mt-4">
          <button onClick={onSelect} className="bg-[#ffaa00] text-black px-4 py-2 rounded-md">
            SELECT
          </button>
          <button
            onClick={onOperate}
            className="bg-[#00ff88] text-black px-4 py-2 rounded-md"
            disabled={!sessionId}
          >
            OPERATE
          </button>
          {countdown !== null && (
            <div className="text-2xl font-mono status-amber">{countdown}s</div>
          )}
          {result && (
            <div className="text-sm status-green">
              {result.toUpperCase()} ({responseMs} ms)
            </div>
          )}
        </div>
      </div>

      <div className="panel p-4">
        <div className="text-sm uppercase tracking-widest text-gray-400">Audit Log</div>
        <table className="w-full text-xs font-mono mt-3">
          <thead>
            <tr className="text-gray-500">
              <th className="text-left py-2">TIME</th>
              <th className="text-left">NODE</th>
              <th className="text-left">BREAKER</th>
              <th className="text-left">ACTION</th>
              <th className="text-left">RESULT</th>
            </tr>
          </thead>
          <tbody>
            {audit.length === 0 && (
              <tr>
                <td colSpan={5} className="py-3 text-gray-500">No operations recorded</td>
              </tr>
            )}
            {audit.map((entry, index) => (
              <tr key={`${entry.time}-${index}`}>
                <td className="py-2">{entry.time}</td>
                <td>{entry.node}</td>
                <td>{entry.breaker}</td>
                <td>{entry.action}</td>
                <td>{entry.result}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
