// Nodes Store
import { create } from 'zustand';

const useNodesStore = create((set) => ({
  nodes: [],
  selectedNode: null,
  
  setNodes: (nodes) => set({ nodes }),
  
  updateNodeTelemetry: (nodeId, telemetry) => set((state) => ({
    nodes: state.nodes.map((node) =>
      node.node_id === nodeId ? { ...node, telemetry } : node
    ),
    selectedNode: state.selectedNode?.node_id === nodeId
      ? { ...state.selectedNode, telemetry }
      : state.selectedNode,
  })),
  
  selectNode: (node) => set({ selectedNode: node }),
  
  clearSelection: () => set({ selectedNode: null }),
}));

export default useNodesStore;
