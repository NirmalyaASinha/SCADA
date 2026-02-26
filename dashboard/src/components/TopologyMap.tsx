import ReactFlow, { Background, Controls, MiniMap, Node, Edge } from 'reactflow';
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, GitFork } from 'lucide-react';
import { useNodesStore } from '../store/nodesStore';
import { topologyEdges, topologyPositions } from '../data/topology';
import { stateToBg } from '../utils/status';

function GenNode({ data }: { data: { label: string; state: string } }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="flex items-center justify-center w-10 h-10 rounded-full border border-[#2a2a2a]" style={{ background: '#0f0f0f' }}>
        <Zap size={16} color="#00ff88" />
      </div>
      <div className="text-xs font-mono">{data.label}</div>
    </div>
  );
}

function SubNode({ data }: { data: { label: string } }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="flex items-center justify-center w-12 h-8 rounded border border-[#2a2a2a]" style={{ background: '#0f0f0f' }}>
        <GitFork size={16} color="#ffaa00" />
      </div>
      <div className="text-xs font-mono">{data.label}</div>
    </div>
  );
}

function DistNode({ data }: { data: { label: string } }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="w-10 h-6 rounded border border-[#2a2a2a]" style={{ background: '#0f0f0f' }}></div>
      <div className="text-xs font-mono">{data.label}</div>
    </div>
  );
}

const nodeTypes = {
  gen: GenNode,
  sub: SubNode,
  dist: DistNode,
};

export default function TopologyMap() {
  const nodes = useNodesStore((state) => state.nodes);
  const navigate = useNavigate();

  const flowNodes: Node[] = useMemo(() =>
    nodes.map((node) => {
      const position = topologyPositions[node.node_id] || { x: 0, y: 0, row: 0 };
      const type = node.node_id.startsWith('GEN') ? 'gen' : node.node_id.startsWith('SUB') ? 'sub' : 'dist';
      return {
        id: node.node_id,
        type,
        position: { x: position.x, y: position.y },
        data: { label: node.node_id, state: node.state },
        style: {
          borderColor: stateToBg(node.state),
          borderWidth: 2,
          borderStyle: 'solid',
          padding: 6,
          background: '#0f0f0f',
        },
      } as Node;
    }), [nodes]
  );

  const flowEdges: Edge[] = useMemo(() =>
    topologyEdges.map(([source, target], index) => ({
      id: `edge-${index}`,
      source,
      target,
      animated: true,
      style: { stroke: '#2a2a2a' },
    })), []
  );

  return (
    <div className="panel h-[420px]">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        fitView
        onNodeClick={(_, node) => navigate(`/nodes/${node.id}`)}
      >
        <Background color="#1c1c1c" gap={16} />
        <MiniMap nodeColor="#00ff88" maskColor="#0a0a0a" />
        <Controls />
      </ReactFlow>
    </div>
  );
}
