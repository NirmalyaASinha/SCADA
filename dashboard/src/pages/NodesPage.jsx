import React from 'react';
import { useNodesStore } from '../store/nodesStore';

export default function NodesPage() {
  const { nodes } = useNodesStore();

  return (
    <div className="page-content">
      <h2>Node Status</h2>
      <table className="nodes-table">
        <thead>
          <tr>
            <th>Node ID</th>
            <th>Name</th>
            <th>Type</th>
            <th>Status</th>
            <th>Frequency</th>
            <th>Voltage</th>
          </tr>
        </thead>
        <tbody>
          {nodes.map(node => (
            <tr key={node.node_id} className={`status-${node.status.toLowerCase()}`}>
              <td>{node.node_id}</td>
              <td>{node.name}</td>
              <td>{node.node_type}</td>
              <td>{node.status}</td>
              <td>{node.frequency?.toFixed(2) || '-'} Hz</td>
              <td>{node.voltage?.toFixed(2) || '-'} kV</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
