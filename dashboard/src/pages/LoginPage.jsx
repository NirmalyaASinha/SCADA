import React, { useState } from 'react';
import { useAuthStore } from '../store/authStore';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuthStore();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(username, password);
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%)',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '400px',
        padding: '40px',
        backgroundColor: '#0a0a0a',
        border: '2px solid #ff6600',
        borderRadius: '8px',
        boxShadow: '0 8px 32px rgba(255, 102, 0, 0.15)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <h1 style={{
            fontSize: '28px',
            color: '#00ff00',
            marginBottom: '8px',
            textTransform: 'uppercase',
            letterSpacing: '2px',
          }}>
            🔌 SCADA OCC
          </h1>
          <p style={{
            fontSize: '12px',
            color: '#00cc00',
            textTransform: 'uppercase',
            opacity: '0.7',
          }}>
            Critical Infrastructure Control Center
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{
              fontSize: '12px',
              textTransform: 'uppercase',
              letterSpacing: '1px',
              color: '#00ff00',
              fontWeight: 'bold',
            }}>Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              disabled={loading}
              style={{
                padding: '12px',
                backgroundColor: '#1a1a1a',
                border: '1px solid #444',
                borderRadius: '4px',
                color: '#00ff00',
                fontFamily: 'monospace',
                fontSize: '14px',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{
              fontSize: '12px',
              textTransform: 'uppercase',
              letterSpacing: '1px',
              color: '#00ff00',
              fontWeight: 'bold',
            }}>Password</label>
            <div style={{ position: 'relative', display: 'flex' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                disabled={loading}
                style={{
                  flex: 1,
                  padding: '12px',
                  backgroundColor: '#1a1a1a',
                  border: '1px solid #444',
                  borderRadius: '4px',
                  color: '#00ff00',
                  fontFamily: 'monospace',
                  fontSize: '14px',
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                disabled={loading}
                style={{
                  position: 'absolute',
                  right: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '16px',
                  padding: 0,
                  opacity: 0.7,
                }}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          {error && <div style={{
            padding: '10px 12px',
            backgroundColor: 'rgba(255, 51, 51, 0.1)',
            border: '1px solid #ff3333',
            borderRadius: '4px',
            color: '#ff3333',
            fontSize: '12px',
          }}>{error}</div>}

          <button
            type="submit"
            disabled={loading || !username || !password}
            style={{
              padding: '12px',
              backgroundColor: '#ff6600',
              color: '#000',
              border: 'none',
              borderRadius: '4px',
              fontWeight: 'bold',
              fontSize: '14px',
              textTransform: 'uppercase',
              letterSpacing: '1px',
              cursor: 'pointer',
              fontFamily: 'monospace',
              opacity: (loading || !username || !password) ? '0.5' : '1',
            }}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div style={{
          textAlign: 'center',
          marginTop: '24px',
          paddingTop: '16px',
          borderTop: '1px solid #444',
        }}>
          <p style={{
            fontSize: '11px',
            color: '#00cc00',
            opacity: '0.6',
          }}>
            Demo: admin / scada@2024
          </p>
        </div>
      </div>
    </div>
  );
}

