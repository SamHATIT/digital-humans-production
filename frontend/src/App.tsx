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

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/pricing" element={<Pricing />} />

        {/* Protected Routes */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects"
          element={
            <ProtectedRoute>
              <Projects />
            </ProtectedRoute>
          }
        />
        {/* Legacy new project route */}
        <Route
          path="/projects/new"
          element={
            <ProtectedRoute>
              <NewProject />
            </ProtectedRoute>
          }
        />
        {/* Phase 5: Project Configuration Wizard */}
        <Route
          path="/wizard"
          element={
            <ProtectedRoute>
              <ProjectWizard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/wizard/:projectId"
          element={
            <ProtectedRoute>
              <ProjectWizard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/br-validation/:projectId"
          element={
            <ProtectedRoute>
              <BRValidationPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/project/:projectId"
          element={
            <ProtectedRoute>
              <ProjectDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/execution/:projectId"
          element={
            <ProtectedRoute>
              <ExecutionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/execution/:executionId/monitor"
          element={
            <ProtectedRoute>
              <ExecutionMonitoringPage />
            </ProtectedRoute>
          }
        />
        {/* FRNT-05: BUILD Phase Monitoring */}
        <Route
          path="/execution/:executionId/build"
          element={
            <ProtectedRoute>
              <BuildMonitoringPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/agent-tester"
          element={
            <ProtectedRoute>
              <AgentTesterPage />
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
