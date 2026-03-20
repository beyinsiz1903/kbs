import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { LanguageProvider } from './contexts/LanguageContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { DashboardShell } from './components/DashboardShell';
import { Toaster } from './components/ui/sonner';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import CheckInPage from './pages/CheckInPage';
import SubmissionsPage from './pages/SubmissionsPage';
import SubmissionDetailPage from './pages/SubmissionDetailPage';
import AgentMonitorPage from './pages/AgentMonitorPage';
import KBSControlPage from './pages/KBSControlPage';
import AuditTrailPage from './pages/AuditTrailPage';
import HotelsPage from './pages/HotelsPage';
import HotelOnboardingPage from './pages/HotelOnboardingPage';
import HotelHealthPage from './pages/HotelHealthPage';
import UsersPage from './pages/UsersPage';
import './App.css';

function ProtectedRoute({ children, requiredRoles }) {
  const { isAuthenticated, loading, user } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="h-8 w-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requiredRoles && requiredRoles.length > 0 && !requiredRoles.includes(user?.role)) {
    return <Navigate to="/" replace />;
  }

  return children;
}

function AppRoutes() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="h-8 w-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <DashboardShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/checkin" element={<CheckInPage />} />
        <Route path="/submissions" element={<SubmissionsPage />} />
        <Route path="/submissions/:id" element={<SubmissionDetailPage />} />
        <Route path="/agents" element={<AgentMonitorPage />} />
        <Route path="/kbs-control" element={<KBSControlPage />} />
        <Route path="/audit" element={<AuditTrailPage />} />
        <Route path="/hotels" element={<HotelsPage />} />
        <Route path="/hotels/:id/onboarding" element={<HotelOnboardingPage />} />
        <Route path="/hotels/:id/health" element={<HotelHealthPage />} />
        <Route path="/users" element={
          <ProtectedRoute requiredRoles={['admin']}>
            <UsersPage />
          </ProtectedRoute>
        } />
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </DashboardShell>
  );
}

function App() {
  return (
    <LanguageProvider>
      <AuthProvider>
        <Router>
          <AppRoutes />
          <Toaster position="top-right" richColors />
        </Router>
      </AuthProvider>
    </LanguageProvider>
  );
}

export default App;
