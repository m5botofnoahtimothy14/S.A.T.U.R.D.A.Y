import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Shield, Terminal, Fingerprint, Brain, Activity, LogOut, Power, User, CheckCircle, AlertCircle, MessageSquare } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiService } from '../services/api';
import './Sidebar.css';

const Sidebar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [waking, setWaking] = useState(false);
  const [wakeStatus, setWakeStatus] = useState(null);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleWakeAEGIS = async () => {
    setWaking(true);
    setWakeStatus(null);
    
    try {
      const result = await apiService.wakeAegis('aegis');
      setWakeStatus({ success: true, message: 'AEGIS Activated!' });
      setTimeout(() => setWakeStatus(null), 3000);
    } catch (error) {
      setWakeStatus({ success: false, message: 'Wake failed - System may be offline' });
      setTimeout(() => setWakeStatus(null), 3000);
    } finally {
      setWaking(false);
    }
  };

  return (
    <aside className="sidebar">
      <div className="logo">
        <Shield className="shield-icon" size={32} />
        <span>AEGIS</span>
      </div>
      
      <div className="user-info">
        <div className="user-avatar">
          <User size={16} />
        </div>
        <div className="user-details">
          <span className="username">{user?.username || 'User'}</span>
          <span className="role">{user?.role || 'Guest'}</span>
        </div>
      </div>

      <nav className="nav">
        <NavLink to="/dashboard" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Activity size={20} />
          <span>Dashboard</span>
        </NavLink>
        <NavLink to="/defense" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Brain size={20} />
          <span>DL Defense</span>
        </NavLink>
        <NavLink to="/biometrics" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Fingerprint size={20} />
          <span>Biometrics</span>
        </NavLink>
        <NavLink to="/terminal" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Terminal size={20} />
          <span>Terminal</span>
        </NavLink>
        <NavLink to="/ai-agent" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <MessageSquare size={20} />
          <span>AI Agent</span>
        </NavLink>
      </nav>
      
      <div className="sidebar-actions">
        <button 
          className={`wake-button ${waking ? 'waking' : ''}`} 
          onClick={handleWakeAEGIS}
          disabled={waking}
          title="Remote Wake Up"
        >
          {waking ? (
            <span className="wake-spinner"></span>
          ) : (
            <Power size={18} />
          )}
          <span>{waking ? 'Waking...' : 'Wake AEGIS'}</span>
        </button>
        
        {wakeStatus && (
          <div className={`wake-status ${wakeStatus.success ? 'success' : 'error'}`}>
            {wakeStatus.success ? <CheckCircle size={14} /> : <AlertCircle size={14} />}
            <span>{wakeStatus.message}</span>
          </div>
        )}
      </div>

      <div className="sidebar-footer">
        <div className="status">
          <div className="status-indicator online"></div>
          <span>System Online</span>
        </div>
        <button className="logout-button" onClick={handleLogout} title="Logout">
          <LogOut size={18} />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
