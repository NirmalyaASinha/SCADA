import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import { useGridWebSocket } from './hooks/useGridWebSocket';
import AppLayout from './layouts/AppLayout';
import LoginPage from './pages/LoginPage';
import GridOverview from './pages/GridOverview';
import NodesPage from './pages/NodesPage';
import NodeDetail from './pages/NodeDetail';
import ControlPanel from './pages/ControlPanel';
import AlarmsPage from './pages/AlarmsPage';
import SecurityConsole from './pages/SecurityConsole';
import HistorianPage from './pages/HistorianPage';
import ProtectedRoute from './routes/ProtectedRoute';

export default function App() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  useGridWebSocket();

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<GridOverview />} />
        <Route path="nodes" element={<NodesPage />} />
        <Route path="nodes/:id" element={<NodeDetail />} />
        <Route
          path="control"
          element={
            <ProtectedRoute requiredRole="operator">
              <ControlPanel />
            </ProtectedRoute>
          }
        />
        <Route path="alarms" element={<AlarmsPage />} />
        <Route
          path="security"
          element={
            <ProtectedRoute requiredRole="engineer">
              <SecurityConsole />
            </ProtectedRoute>
          }
        />
        <Route path="historian" element={<HistorianPage />} />
      </Route>

      <Route path="*" element={<Navigate to={isAuthenticated ? '/' : '/login'} replace />} />
    </Routes>
  );
}
