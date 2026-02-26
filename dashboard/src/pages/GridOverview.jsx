import React from 'react';
import { useGridStore } from '../store/gridStore';
import { useNodesStore } from '../store/nodesStore';

export default function GridOverview() {
  const { frequency, generation, load, losses } = useGridStore();
  const { nodes } = useNodesStore();

  const healthyNodes = nodes.filter(n => n.status === 'HEALTHY').length;

  return (
    <div className="page-content">
      <h2>Grid Overview</h2>
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-value">{generation?.toFixed(1) || 0} MW</div>
          <div className="kpi-label">Total Generation</div>
          <div className="kpi-bar"><div style={{width: `${Math.min((generation || 0) / 500 * 100, 100)}%`}}></div></div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{load?.toFixed(1) || 0} MW</div>
          <div className="kpi-label">System Load</div>
          <div className="kpi-bar"><div style={{width: `${Math.min((load || 0) / 500 * 100, 100)}%`}}></div></div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{losses?.toFixed(1) || 0} MW</div>
          <div className="kpi-label">Transmission Losses</div>
          <div className="kpi-bar"><div style={{width: `${Math.min((losses || 0) / 100 * 100, 100)}%`}}></div></div>
        </div>
        <div className="kpi-card">
          <div className={`kpi-value ${frequency >= 49.8 && frequency <= 50.2 ? 'normal' : 'alert'}`}>
            {frequency?.toFixed(2) || 0} Hz
          </div>
          <div className="kpi-label">Grid Frequency</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{healthyNodes}/15</div>
          <div className="kpi-label">Nodes Online</div>
          <div className="kpi-bar"><div style={{width: `${healthyNodes * 100 / 15}%`, backgroundColor: '#00ff00'}}></div></div>
        </div>
      </div>
    </div>
  );
}
