import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import Dashboard from './pages/Dashboard';
import Projects from './pages/Projects';
import ProtectedRoute from './components/ProtectedRoute';
import AppShell from './components/layout/AppShell';

// Lazy-loaded pages (split into separate chunks).
// Couloir critique = eager (Login, Dashboard, Projects).
// Tout le reste = lazy pour alléger le bundle initial.
const NewProject              = lazy(() => import('./pages/NewProject'));
const ProjectWizard           = lazy(() => import('./pages/ProjectWizard'));
const BRValidationPage        = lazy(() => import('./pages/BRValidationPage'));
const ExecutionPage           = lazy(() => import('./pages/ExecutionPage'));
const ExecutionMonitoringPage = lazy(() => import('./pages/ExecutionMonitoringPage'));
const BuildMonitoringPage     = lazy(() => import('./pages/BuildMonitoringPage'));
const ProjectDetailPage       = lazy(() => import('./pages/ProjectDetailPage'));
const AgentTesterPage         = lazy(() => import('./pages/AgentTesterPage'));
const Pricing                 = lazy(() => import('./pages/Pricing'));
const BillingSuccess          = lazy(() => import('./pages/BillingSuccess'));
const BillingCancel           = lazy(() => import('./pages/BillingCancel'));

/**
 * Loading fallback minimal Studio — affiché pendant le chunk loading.
 * Reste sobre : un point brass qui pulse, pas d'animation lourde.
 */
function StudioLoader() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4">
      <span
        className="w-2 h-2 bg-brass rounded-full animate-pulse"
        aria-hidden="true"
      />
      <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
        Loading…
      </p>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<StudioLoader />}>
        <Routes>
          {/* ─── Public Routes ─── */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route
            path="/pricing"
            element={
              <AppShell variant="public">
                <Pricing />
              </AppShell>
            }
          />
          <Route
            path="/billing/success"
            element={
              <AppShell variant="public">
                <BillingSuccess />
              </AppShell>
            }
          />
          <Route
            path="/billing/cancel"
            element={
              <AppShell variant="public">
                <BillingCancel />
              </AppShell>
            }
          />

          {/* ─── Protected Routes ─── */}
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

          {/* A5.4 — pages connexes */}
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

          {/* A5.2 — Casting tunnel */}
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

          {/* A5.3 — Theatre tunnel */}
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
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
