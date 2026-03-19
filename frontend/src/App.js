import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { LanguageProvider } from './contexts/LanguageContext';
import { DashboardShell } from './components/DashboardShell';
import { Toaster } from './components/ui/sonner';
import DashboardPage from './pages/DashboardPage';
import CheckInPage from './pages/CheckInPage';
import SubmissionsPage from './pages/SubmissionsPage';
import SubmissionDetailPage from './pages/SubmissionDetailPage';
import AgentMonitorPage from './pages/AgentMonitorPage';
import KBSControlPage from './pages/KBSControlPage';
import AuditTrailPage from './pages/AuditTrailPage';
import HotelsPage from './pages/HotelsPage';
import './App.css';

function App() {
  return (
    <LanguageProvider>
      <Router>
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
          </Routes>
        </DashboardShell>
        <Toaster position="top-right" richColors />
      </Router>
    </LanguageProvider>
  );
}

export default App;
