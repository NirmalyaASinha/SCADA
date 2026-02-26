import React from 'react';
import { useAuthStore } from '../store/authStore';

export default function SettingsPage() {
  const { user } = useAuthStore();

  return (
    <div className="page-content">
      <h2>Settings</h2>
      <div className="settings-section">
        <h3>User Profile</h3>
        <div className="setting-item">
          <label>Username</label>
          <input type="text" value={user?.username} disabled />
        </div>
        <div className="setting-item">
          <label>Role</label>
          <input type="text" value={user?.role} disabled />
        </div>
      </div>

      <div className="settings-section">
        <h3>System Configuration</h3>
        <div className="info-box">
          System settings and configuration options available to administrators.
        </div>
      </div>
    </div>
  );
}
