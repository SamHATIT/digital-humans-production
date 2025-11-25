import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import PMDialogue from './pages/pm/PMDialogue';
import PRDReview from './pages/pm/PRDReview';
import UserStoriesBoard from './pages/pm/UserStoriesBoard';
import RoadmapPlanning from './pages/pm/RoadmapPlanning';

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/projects/:projectId/pm-dialogue" element={<PMDialogue />} />
          <Route path="/projects/:projectId/prd-review" element={<PRDReview />} />
          <Route path="/projects/:projectId/user-stories" element={<UserStoriesBoard />} />
          <Route path="/projects/:projectId/roadmap" element={<RoadmapPlanning />} />

          {/* Default route */}
          <Route path="/" element={
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
              <div className="text-center">
                <h1 className="text-4xl font-bold text-gray-900 mb-4">
                  Digital Humans - PM Orchestrator
                </h1>
                <p className="text-gray-600 mb-8">
                  Transform your business needs into complete Salesforce implementations
                </p>
                <a
                  href="/projects/1/pm-dialogue"
                  className="inline-block px-6 py-3 bg-pm-primary text-white rounded-lg hover:bg-pm-secondary transition-colors"
                >
                  Start New Project
                </a>
              </div>
            </div>
          } />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
