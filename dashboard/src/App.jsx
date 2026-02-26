import React, { useState } from 'react';
import './App.css';
import { useAuthStore } from './store/authStore';
import LoginPage from './pages/LoginPage';

export default function App() {
  const { isAuthenticated, user, logout } = useAuthStore();
  const [currentPage, setCurrentPage] = useState('grid');

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <div className="dashboard">
      <header className="header">
        <div className="header-left">
          <h1>🔌 SCADA OCC</h1>
        </div>
        <div className="header-right">
          <div className="user-menu">
            <span>{user?.username}</span>
            <button onClick={logout} className="btn-logout">Logout</button>
          </div>
        </div>
      </header>

      <div className="app-container">
        <nav className="sidebar">
          <div className="nav-section">
            <h3>Pages</h3>
            {['Grid Overview', 'Nodes', 'Control', 'Alarms', 'Security', 'Historian', 'Settings'].map(page => (
              <button
                key={page}
                className={`nav-item ${currentPage === page ? 'active' : ''}`}
                onClick={() => setCurrentPage(page)}
              >
                {page}
              </button>
            ))}
          </div>
        </nav>

        <main className="main-content">
          <h2>{currentPage}</h2>
          <p>Welcome to SCADA OCC Dashboard</p>
          <p>User: {user?.username} ({user?.role})</p>
        </main>
      </div>
    </div>
  );
}
