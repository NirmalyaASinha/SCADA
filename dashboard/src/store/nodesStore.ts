import { create } from 'zustand';
import type { NodeInfo } from '../types';

export type TelemetryPoint = {
  timestamp: string;
  values: Record<string, number>;
};

type NodesState = {
  nodes: NodeInfo[];
  telemetryHistory: Record<string, TelemetryPoint[]>;
  setNodes: (nodes: NodeInfo[]) => void;
  updateNode: (nodeId: string, updates: Partial<NodeInfo>) => void;
  addTelemetry: (nodeId: string, telemetry: Record<string, number | string>) => void;
};

const MAX_HISTORY = 3600;

export const useNodesStore = create<NodesState>((set) => ({
  nodes: [],
  telemetryHistory: {},
  setNodes: (nodes) => set({ nodes }),
  updateNode: (nodeId, updates) =>
    set((state) => ({
      nodes: state.nodes.map((node) => (node.node_id === nodeId ? { ...node, ...updates } : node)),
    })),
  addTelemetry: (nodeId, telemetry) =>
    set((state) => {
      const numericValues: Record<string, number> = {};
      Object.entries(telemetry).forEach(([key, value]) => {
        const num = typeof value === 'number' ? value : Number(value);
        if (!Number.isNaN(num)) {
          numericValues[key] = num;
        }
      });

      const entry: TelemetryPoint = {
        timestamp: new Date().toISOString(),
        values: numericValues,
      };

      const history = state.telemetryHistory[nodeId] || [];
      const nextHistory = [...history, entry].slice(-MAX_HISTORY);

      return {
        nodes: state.nodes.map((node) =>
          node.node_id === nodeId ? { ...node, telemetry: telemetry as NodeInfo['telemetry'] } : node
        ),
        telemetryHistory: {
          ...state.telemetryHistory,
          [nodeId]: nextHistory,
        },
      };
    }),
}));
