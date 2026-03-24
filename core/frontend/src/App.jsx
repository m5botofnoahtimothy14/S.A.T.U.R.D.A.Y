import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import Terminal from './pages/Terminal';
import Biometrics from './pages/Biometrics';
import Defense from './pages/Defense';
import Login from './pages/Login';
import AIAgent from './pages/AIAgent';
import Sidebar from './components/Sidebar';
import './App.css';

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <div className="app">
                  <Sidebar />
                  <main className="main-content">
                    <Routes>
                      <Route path="/" element={<Navigate to="/dashboard" replace />} />
                      <Route path="/dashboard" element={<Dashboard />} />
                      <Route path="/terminal" element={<Terminal />} />
                      <Route path="/biometrics" element={<Biometrics />} />
                      <Route path="/defense" element={<Defense />} />
                      <Route path="/ai-agent" element={<AIAgent />} />
                    </Routes>
                  </main>
                </div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
