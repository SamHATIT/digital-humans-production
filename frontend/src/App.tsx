import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import Dashboard from './pages/Dashboard';
import Projects from './pages/Projects';
import NewProject from './pages/NewProject';
import ProjectWizard from './pages/ProjectWizard';
import ExecutionPage from './pages/ExecutionPage';
import ExecutionMonitoringPage from './pages/ExecutionMonitoringPage';
import BuildMonitoringPage from './pages/BuildMonitoringPage';
import AgentTesterPage from './pages/AgentTesterPage';
import BRValidationPage from './pages/BRValidationPage';
import ProjectDetailPage from './pages/ProjectDetailPage';
import Pricing from './pages/Pricing';
import ProtectedRoute from './components/ProtectedRoute';
import AppShell from './components/layout/AppShell';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ─── Public Routes ─── */}
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/pricing"
          element={
            <AppShell variant="public">
              <Pricing />
            </AppShell>
          }
        />

        {/* ─── Protected Routes (toutes en charte Studio après A5.4) ─── */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppShell>
                <Dashboard />
              </AppShell>
            </ProtectedRoute>
          }
        />

        {/* A5.4 — pages connexes en charte Studio */}
        <Route
          path="/projects"
          element={
            <ProtectedRoute>
              <AppShell>
                <Projects />
              </AppShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/project/:projectId"
          element={
            <ProtectedRoute>
              <AppShell>
                <ProjectDetailPage />
              </AppShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/agent-tester"
          element={
            <ProtectedRoute>
              <AppShell>
                <AgentTesterPage />
              </AppShell>
            </ProtectedRoute>
          }
        />

        {/* A5.2 — Casting tunnel : NewProject + Wizard + BR validation */}
        <Route
          path="/projects/new"
          element={
            <ProtectedRoute>
              <AppShell>
                <NewProject />
              </AppShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/wizard"
          element={
            <ProtectedRoute>
              <AppShell>
                <ProjectWizard />
              </AppShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/wizard/:projectId"
          element={
            <ProtectedRoute>
              <AppShell>
                <ProjectWizard />
              </AppShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/br-validation/:projectId"
          element={
            <ProtectedRoute>
              <AppShell>
                <BRValidationPage />
              </AppShell>
            </ProtectedRoute>
          }
        />

        {/* A5.3 — Theatre tunnel : ExecutionPage + Monitor + BUILD */}
        <Route
          path="/execution/:projectId"
          element={
            <ProtectedRoute>
              <AppShell>
                <ExecutionPage />
              </AppShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/execution/:executionId/monitor"
          element={
            <ProtectedRoute>
              <AppShell>
                <ExecutionMonitoringPage />
              </AppShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/execution/:executionId/build"
          element={
            <ProtectedRoute>
              <AppShell>
                <BuildMonitoringPage />
              </AppShell>
            </ProtectedRoute>
          }
        />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
