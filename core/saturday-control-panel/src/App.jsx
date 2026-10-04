import { useEffect, useState } from 'react';
import { Loader, Menu, X, Settings } from 'lucide-react';
import AIStatusCard from './components/AIStatusCard';
import CommandPanel from './components/CommandPanel';
import MonitoringDashboard from './components/MonitoringDashboard';
import TaskManager from './components/TaskManager';
import EventLog from './components/EventLog';
import { resolveApiBaseUrl } from './config/site';
import './styles.css';

const API_BASE_URL = resolveApiBaseUrl(import.meta.env, window.location);

function App() {
  const [saturdayStatus, setSaturdayStatus] = useState(null);
  const [edithStatus, setEdithStatus] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [events, setEvents] = useState([]);
  const [performance, setPerformance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeAI, setActiveAI] = useState('saturday');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Fetch all AI status
  const fetchStatus = async () => {
    try {
      const token = localStorage.getItem('aegis_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

      // Fetch Saturday status
      const satRes = await fetch(`${API_BASE_URL}/v1/ai/saturday/status`, { headers });
      if (satRes.ok) {
        setSaturdayStatus(await satRes.json());
      }

      // Fetch Edith status
      const edithRes = await fetch(`${API_BASE_URL}/v1/ai/edith/status`, { headers });
      if (edithRes.ok) {
        setEdithStatus(await edithRes.json());
      }

      setError('');
    } catch (err) {
      setError('Failed to fetch AI status: ' + err.message);
      console.error(err);
    }
  };

  // Fetch tasks
  const fetchTasks = async (ai = 'saturday') => {
    try {
      const token = localStorage.getItem('aegis_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      const res = await fetch(`${API_BASE_URL}/v1/tasks?ai=${ai}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setTasks(data.tasks || []);
      }
    } catch (err) {
      console.error('Failed to fetch tasks:', err);
    }
  };

  // Fetch events
  const fetchEvents = async (ai = 'saturday') => {
    try {
      const token = localStorage.getItem('aegis_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      const res = await fetch(`${API_BASE_URL}/v1/monitor/events?ai=${ai}&limit=50`, { headers });
      if (res.ok) {
        const data = await res.json();
        setEvents(data.events || []);
      }
    } catch (err) {
      console.error('Failed to fetch events:', err);
    }
  };

  // Fetch performance metrics
  const fetchPerformance = async (ai = 'saturday') => {
    try {
      const token = localStorage.getItem('aegis_token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      const res = await fetch(`${API_BASE_URL}/v1/monitor/performance?ai=${ai}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setPerformance(data.metrics?.cpu_samples?.map((cpu, i) => ({
          time: `${i * 5}m`,
          cpu: cpu,
          memory: data.metrics?.memory_samples?.[i] || 0,
          response_time: Math.random() * 500
        })) || []);
      }
    } catch (err) {
      console.error('Failed to fetch performance:', err);
    }
  };

  // Initialize on mount
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await Promise.all([
        fetchStatus(),
        fetchTasks('saturday'),
        fetchEvents('saturday'),
        fetchPerformance('saturday')
      ]);
      setLoading(false);
    };

    init();

    // Setup polling intervals
    const statusInterval = setInterval(fetchStatus, 5000);
    const tasksInterval = setInterval(() => fetchTasks(activeAI), 8000);
    const eventsInterval = setInterval(() => fetchEvents(activeAI), 8000);
    const perfInterval = setInterval(() => fetchPerformance(activeAI), 10000);

    // Connect to WebSocket for real-time updates
    const wsUrl = `${API_BASE_URL.replace(/^http/, 'ws')}/ws/events`;
    const token = localStorage.getItem('aegis_token');
    const fullWsUrl = token ? `${wsUrl}?token=${token}` : wsUrl;

    let ws;
    try {
      ws = new WebSocket(fullWsUrl);
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'event') {
            setEvents(prev => [msg.data, ...prev].slice(0, 50));
          }
        } catch (err) {
          console.error('WS parse error:', err);
        }
      };
      ws.onerror = (err) => {
        console.error('WS error:', err);
      };
    } catch (err) {
      console.error('WS connection failed:', err);
    }

    return () => {
      clearInterval(statusInterval);
      clearInterval(tasksInterval);
      clearInterval(eventsInterval);
      clearInterval(perfInterval);
      ws?.close();
    };
  }, [activeAI]);

  // Handle AI action
  const handleAction = async (ai, action) => {
    try {
      const token = localStorage.getItem('aegis_token');
      const headers = {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      };

      const res = await fetch(`${API_BASE_URL}/v1/control/action`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ action, ai })
      });

      if (!res.ok) throw new Error(`Action failed: ${res.status}`);
      
      // Refresh status after action
      await new Promise(r => setTimeout(r, 500));
      await fetchStatus();
    } catch (err) {
      setError(`Action failed: ${err.message}`);
      setTimeout(() => setError(''), 3000);
    }
  };

  // Handle command
  const handleCommand = async (ai, command) => {
    try {
      const token = localStorage.getItem('aegis_token');
      const headers = {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      };

      const res = await fetch(`${API_BASE_URL}/v1/control/command`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ command, ai })
      });

      if (!res.ok) throw new Error(`Command failed: ${res.status}`);
    } catch (err) {
      setError(`Command failed: ${err.message}`);
      setTimeout(() => setError(''), 3000);
    }
  };

  // Handle create task
  const handleCreateTask = async (taskData) => {
    try {
      const token = localStorage.getItem('aegis_token');
      const headers = {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      };

      const res = await fetch(`${API_BASE_URL}/v1/tasks`, {
        method: 'POST',
        headers,
        body: JSON.stringify(taskData)
      });

      if (!res.ok) throw new Error(`Task creation failed: ${res.status}`);
      
      await fetchTasks(activeAI);
    } catch (err) {
      setError(`Task creation failed: ${err.message}`);
      setTimeout(() => setError(''), 3000);
    }
  };

  // Handle delete task
  const handleDeleteTask = async (taskId) => {
    try {
      const token = localStorage.getItem('aegis_token');
      const headers = {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      };

      const res = await fetch(`${API_BASE_URL}/v1/tasks/${taskId}`, {
        method: 'DELETE',
        headers
      });

      if (!res.ok) throw new Error(`Task deletion failed: ${res.status}`);
      
      await fetchTasks(activeAI);
    } catch (err) {
      setError(`Task deletion failed: ${err.message}`);
      setTimeout(() => setError(''), 3000);
    }
  };

  const currentStatus = activeAI === 'saturday' ? saturdayStatus : edithStatus;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <button 
          className="sidebar-toggle"
          onClick={() => setSidebarOpen(!sidebarOpen)}
        >
          {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
        <div className="header-title">
          <h1>S.A.T.U.R.D.A.Y Control Panel</h1>
          <p>AI System Management & Monitoring • <span style={{color: '#00ff9f', fontWeight: 'bold'}}>★ PRO SUBSCRIBED TIER</span></p>
        </div>
        <div style={{display:'flex', gap:'10px', alignItems:'center'}}>
          <span className="status-badge status-ACTIVE">★ SUBSCRIBED</span>
          <button className="settings-btn">
            <Settings size={20} />
          </button>
        </div>
      </header>

      {/* Sidebar Navigation */}
      {sidebarOpen && (
        <aside className="sidebar">
          <nav className="nav-links">
            <button 
              className={`nav-btn ${activeAI === 'saturday' ? 'active' : ''}`}
              onClick={() => setActiveAI('saturday')}
            >
              SATURDAY
            </button>
            <button 
              className={`nav-btn ${activeAI === 'edith' ? 'active' : ''}`}
              onClick={() => setActiveAI('edith')}
            >
              EDITH
            </button>
          </nav>
        </aside>
      )}

      {/* Main Content */}
      <main className="main-content">
        {/* Error Alert */}
        {error && (
          <div className="error-alert">
            {error}
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <div className="loading-state">
            <Loader size={40} className="spinner" />
            <p>Initializing S.A.T.U.R.D.A.Y Control Panel...</p>
          </div>
        ) : (
          <>
            {/* Status Cards */}
            <div className="status-grid">
              {saturdayStatus && (
                <AIStatusCard 
                  ai="saturday"
                  status={saturdayStatus}
                  onWake={() => handleAction('saturday', 'wake')}
                  onControl={() => setActiveAI('saturday')}
                />
              )}
              {edithStatus && (
                <AIStatusCard 
                  ai="edith"
                  status={edithStatus}
                  onWake={() => handleAction('edith', 'wake')}
                  onControl={() => setActiveAI('edith')}
                />
              )}
            </div>

            {/* Control Section */}
            <div className="control-section">
              <CommandPanel 
                ai={activeAI}
                onCommand={handleCommand}
                onAction={handleAction}
              />

              <MonitoringDashboard 
                ai={activeAI}
                performanceData={performance}
              />
            </div>

            {/* Task and Event Section */}
            <div className="info-section">
              <TaskManager 
                ai={activeAI}
                tasks={tasks}
                onCreateTask={handleCreateTask}
                onDeleteTask={handleDeleteTask}
              />

              <EventLog 
                ai={activeAI}
                events={events}
              />
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
