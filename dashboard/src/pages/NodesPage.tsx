import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchNodes } from '../api/nodes';
import { useNodesStore } from '../store/nodesStore';
import StatusChip from '../components/StatusChip';

export default function NodesPage() {
  const [query, setQuery] = useState('');
  const nodes = useNodesStore((state) => state.nodes);
  const setNodes = useNodesStore((state) => state.setNodes);
  const navigate = useNavigate();

  useEffect(() => {
    fetchNodes().then(setNodes).catch(() => undefined);
  }, [setNodes]);

  const filtered = useMemo(() => {
    return nodes.filter((node) => node.node_id.toLowerCase().includes(query.toLowerCase()));
  }, [nodes, query]);

  return (
    <div className="panel p-6">
      <div className="flex items-center justify-between">
        <div className="text-lg font-mono">Nodes</div>
        <input
          className="bg-[#0d0d0d] border border-[#2a2a2a] rounded-md px-3 py-1 text-sm"
          placeholder="Search node..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      <table className="w-full mt-4 text-sm font-mono">
        <thead>
          <tr className="text-gray-500">
            <th className="text-left py-2">NODE</th>
            <th className="text-left">TYPE</th>
            <th className="text-left">STATE</th>
            <th className="text-left">REST</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((node) => (
            <tr
              key={node.node_id}
              className="border-b border-[#1e1e1e] hover:bg-[#111111] cursor-pointer"
              onClick={() => navigate(`/nodes/${node.node_id}`)}
            >
              <td className="py-2">{node.node_id}</td>
              <td>{node.type}</td>
              <td><StatusChip state={node.state} /></td>
              <td>{node.rest_url}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
