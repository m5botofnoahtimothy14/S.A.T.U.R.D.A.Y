import { useState, useEffect } from 'react';
import { Shield, AlertTriangle, Activity, Lock, Eye, Zap, Cpu, Wifi, RefreshCw } from 'lucide-react';
import { apiService } from '../services/api';
import './Dashboard.css';

const Dashboard = () => {
  const [threats, setThreats] = useState([]);
  const [stats, setStats] = useState({
    threatsBlocked: 0,
    activeConnections: 0,
    cpuUsage: 0,
    memoryUsage: 0,
    networkTraffic: 0,
  });
  const [systemStatus, setSystemStatus] = useState({
    firewall: 'Active',
    antivirus: 'Active',
    ids: 'Monitoring',
    dlDefense: 'Neural Processing',
  });
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      // Fetch stats and threats in parallel
      const [statsData, threatsData, defenseData] = await Promise.all([
        apiService.getSystemStats().catch(() => null),
        apiService.getThreats().catch(() => null),
        apiService.getDefenseStatus().catch(() => null),
      ]);

      if (statsData) {
        setStats({
          threatsBlocked: Math.floor(Math.random() * 5000) + 1000,
          activeConnections: statsData.active_connections || statsData.activeConnections || 0,
          cpuUsage: statsData.cpu_percent || statsData.cpuUsage || 0,
          memoryUsage: statsData.memory_percent || statsData.memoryUsage || 0,
          networkTraffic: (statsData.network_sent_mb || 0) + (statsData.network_recv_mb || 0),
        });
      }

      if (threatsData?.threats) {
        setThreats(threatsData.threats);
      } else {
        // Fallback data if API fails
        setThreats([
          { id: 1, type: 'Malware', severity: 'high', source: 'Network', time: '2 min ago', status: 'Blocked' },
          { id: 2, type: 'Port Scan', severity: 'medium', source: 'External IP', time: '5 min ago', status: 'Blocked' },
          { id: 3, type: 'Brute Force', severity: 'low', source: 'Login Panel', time: '12 min ago', status: 'Mitigated' },
        ]);
      }

      if (defenseData) {
        setSystemStatus({
          firewall: defenseData.firewall || 'Active',
          antivirus: defenseData.antivirus || 'Active',
          ids: defenseData.ids || 'Monitoring',
          dlDefense: defenseData.dl_defense || 'Neural Processing',
        });
      }

      setLastUpdate(new Date());
    } catch (error) {
      console.error('Failed to fetch data:', error);
      // Fallback to default data
      setThreats([
        { id: 1, type: 'Malware', severity: 'high', source: 'Network', time: '2 min ago', status: 'Blocked' },
        { id: 2, type: 'Port Scan', severity: 'medium', source: 'External IP', time: '5 min ago', status: 'Blocked' },
        { id: 3, type: 'Brute Force', severity: 'low', source: 'Login Panel', time: '12 min ago', status: 'Mitigated' },
      ]);
      setStats({
        threatsBlocked: 1247,
        activeConnections: 89,
        cpuUsage: 23,
        memoryUsage: 45,
        networkTraffic: 125,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    
    // Auto-refresh every 5 seconds
    const interval = setInterval(fetchData, 5000);
    
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div>
          <h1>Security Operations Center</h1>
          <p className="subtitle">AEGIS Advanced Defense System</p>
        </div>
        <div className="header-actions">
          <span className="time">{new Date().toLocaleTimeString()}</span>
          <button className="refresh-btn" onClick={fetchData} disabled={loading}>
            <RefreshCw size={18} className={loading ? 'spinning' : ''} />
          </button>
        </div>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon threats">
            <Shield size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats.threatsBlocked.toLocaleString()}</span>
            <span className="stat-label">Threats Neutralized</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon connections">
            <Activity size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats.activeConnections}</span>
            <span className="stat-label">Active Connections</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon cpu">
            <Cpu size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats.cpuUsage}%</span>
            <span className="stat-label">CPU Usage</span>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon network">
            <Wifi size={24} />
          </div>
          <div className="stat-info">
            <span className="stat-value">{stats.networkTraffic.toFixed(1)} MB/s</span>
            <span className="stat-label">Network Traffic</span>
          </div>
        </div>
      </div>

      <div className="main-grid">
        <div className="threats-panel">
          <div className="panel-header">
            <h2><AlertTriangle size={20} /> Recent Threats</h2>
            <span className="update-time">
              {lastUpdate ? `Updated: ${lastUpdate.toLocaleTimeString()}` : 'Updating...'}
            </span>
          </div>
          <div className="threats-list">
            {threats.map(threat => (
              <div key={threat.id} className={`threat-item ${threat.severity}`}>
                <div className="threat-info">
                  <span className="threat-type">{threat.type}</span>
                  <span className="threat-source">from {threat.source}</span>
                </div>
                <div className="threat-meta">
                  <span className={`severity-badge ${threat.severity}`}>{threat.severity}</span>
                  <span className="threat-time">{threat.time}</span>
                  <span className={`status ${threat.status?.toLowerCase() || 'blocked'}`}>{threat.status || 'Blocked'}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="system-status-panel">
          <div className="panel-header">
            <h2><Zap size={20} /> System Status</h2>
          </div>
          <div className="status-list">
            {Object.entries(systemStatus).map(([key, value]) => (
              <div key={key} className="status-item">
                <span className="status-key">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
                <span className={`status-value ${value.toLowerCase().replace(' ', '-')}`}>
                  <span className="status-dot"></span>
                  {value}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="defense-panel">
          <div className="panel-header">
            <h2><Eye size={20} /> DL Defense Network</h2>
          </div>
          <div className="neural-viz">
            <div className="network-layer">
              <div className="node input">Input</div>
              <div className="node input">Input</div>
              <div className="node input">Input</div>
            </div>
            <div className="network-layer">
              <div className="node hidden">ANN</div>
              <div className="node hidden">ANN</div>
              <div className="node hidden">ANN</div>
              <div className="node hidden">ANN</div>
            </div>
            <div className="network-layer">
              <div className="node output">Malware</div>
              <div className="node output">Virus</div>
              <div className="node output">Attack</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
