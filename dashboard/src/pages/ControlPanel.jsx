import React from 'react';

export default function ControlPanel() {
  return (
    <div className="page-content">
      <h2>Control Panel</h2>
      <div className="control-section">
        <h3>Breaker Controls (SBO - Select Before Operate)</h3>
        <p>Available breaker operations with 10-second lockout after selection.</p>
        <div className="info-box">
          Coming soon: Real-time breaker controls for all substations
        </div>
      </div>
    </div>
  );
}
