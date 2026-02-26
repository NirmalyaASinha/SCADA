import { useMemo, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { useNodesStore } from '../store/nodesStore';

const tags = ['frequency_hz', 'voltage_kv', 'active_power_mw', 'reactive_power_mvar'];

export default function HistorianPage() {
  const nodes = useNodesStore((state) => state.nodes);
  const telemetryHistory = useNodesStore((state) => state.telemetryHistory);
  const [selectedNode, setSelectedNode] = useState(nodes[0]?.node_id || 'GEN-001');
  const [selectedTags, setSelectedTags] = useState<string[]>(['frequency_hz']);

  const history = telemetryHistory[selectedNode] || [];

  const chartData = useMemo(() => {
    return history.map((point) => ({
      timestamp: point.timestamp,
      ...point.values,
    }));
  }, [history]);

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((item) => item !== tag) : [...prev, tag]
    );
  };

  const exportCsv = () => {
    const headers = ['timestamp', ...selectedTags];
    const rows = chartData.map((row) =>
      headers.map((key) => String((row as Record<string, unknown>)[key] ?? '')).join(',')
    );
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${selectedNode}-historian.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="panel p-4">
        <div className="text-lg font-mono">Historian</div>
        <div className="flex gap-4 mt-3">
          <select
            className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm"
            value={selectedNode}
            onChange={(event) => setSelectedNode(event.target.value)}
          >
            {nodes.map((node) => (
              <option key={node.node_id} value={node.node_id}>
                {node.node_id}
              </option>
            ))}
          </select>
          <div className="flex gap-2">
            {tags.map((tag) => (
              <button
                key={tag}
                className={`text-xs border px-3 py-2 rounded-md ${
                  selectedTags.includes(tag) ? 'border-[#00ff88] text-[#00ff88]' : 'border-[#2a2a2a] text-gray-400'
                }`}
                onClick={() => toggleTag(tag)}
              >
                {tag}
              </button>
            ))}
          </div>
          <button onClick={exportCsv} className="ml-auto text-xs border border-[#2a2a2a] px-3 py-2 rounded-md">
            Export CSV
          </button>
        </div>
      </div>

      <div className="panel p-4">
        <div className="h-[320px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <XAxis dataKey="timestamp" hide />
              <YAxis hide />
              <Tooltip contentStyle={{ background: '#111111', border: '1px solid #2a2a2a' }} />
              {selectedTags.map((tag, index) => (
                <Line
                  key={tag}
                  dataKey={tag}
                  stroke={['#00ff88', '#ffaa00', '#33a1ff', '#aa44ff'][index % 4]}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        {chartData.length === 0 && (
          <div className="text-xs text-gray-500 mt-2">No historical data available yet.</div>
        )}
      </div>
    </div>
  );
}
