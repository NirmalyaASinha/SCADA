import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useAuthStore } from '../store/authStore';

export default function LoginPage() {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const login = useAuthStore((state) => state.login);
  const isLoading = useAuthStore((state) => state.isLoading);
  const navigate = useNavigate();

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    try {
      await login(username, password);
      navigate('/');
      toast.success('Welcome to SCADA OCC');
    } catch {
      setError('Invalid username or password');
      toast.error('Login failed');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a]">
      <div className="panel w-[420px] p-8">
        <div className="text-[#00ff88] font-mono text-xl">SCADA OCC</div>
        <div className="text-gray-400 text-sm mt-2">Operator console login</div>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-xs text-gray-400">Username</label>
            <input
              className="w-full mt-1 bg-[#0d0d0d] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="admin"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400">Password</label>
            <input
              className="w-full mt-1 bg-[#0d0d0d] border border-[#2a2a2a] rounded-md px-3 py-2 text-sm"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          {error && <div className="text-xs text-[#ff3333]">{error}</div>}

          <button
            type="submit"
            className="w-full bg-[#00ff88] text-black font-semibold rounded-md px-3 py-2"
            disabled={isLoading}
          >
            {isLoading ? 'Authenticating...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  );
}
