import { useEffect, useState, useRef } from "react";
import {
  Activity, Shield, Mic, Camera, LayoutDashboard,
  MessageSquare, User, Terminal, Heart,
  Settings, LogOut, Bell, BrainCircuit, Maximize, Eye, Music,
  Database, Smartphone, Zap, Radio, Globe, Wifi, Send, Power
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip
} from "recharts";
import {
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut,
  GoogleAuthProvider,
  signInWithPopup
} from "firebase/auth";
import {
  doc, onSnapshot, collection, addDoc, serverTimestamp, query, orderBy, limit
} from "firebase/firestore";
import { auth, db } from "./firebase";
import "./styles.css";

const API_BASE_URL = import.meta.env.VITE_AEGIS_GATEWAY_URL || 'http://localhost:8000';
const ADMIN_EMAILS = ['m5botkitm40@gmail.com', 'noahtimothykeba@gmail.com'];

const StatCard = ({ title, value, unit, icon: Icon, color = "var(--accent-blue)" }) => (
  <div className="health-item glow-border">
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
      <span>{title}</span>
      <Icon size={14} color={color} className="icon-pulse" />
    </div>
    <strong>{value}<small style={{ fontSize: "0.6rem", marginLeft: "4px", color: "var(--text-secondary)" }}>{unit}</small></strong>
  </div>
);

const SectionHeader = ({ title, icon: Icon, status = "ACTIVE" }) => (
  <div className="panel-header">
    <h3><Icon size={18} /> {title}</h3>
    <span style={{ fontSize: "0.6rem", color: "var(--accent-teal)", letterSpacing: "2px" }}>[{status}]</span>
  </div>
);

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState("");
  const [aegisData, setAegisData] = useState({
    cpu: 0, ram: 0, hr: 72, mood: "Calm",
    alerts: [], uptime: "00:00:00", status: "STANDBY",
    surroundings: "Workspace Clear."
  });
  const [history, setHistory] = useState([]);
  const [logs, setLogs] = useState([]);
  const [liveFeed, setLiveFeed] = useState([]);
  const [view, setView] = useState("dashboard");
  const [command, setCommand] = useState("");
  const [isCloud, setIsCloud] = useState(true);
  const [userRole, setUserRole] = useState("viewer");
  const [wakeLoading, setWakeLoading] = useState(false);
  const [modules, setModules] = useState({});
  const [homebot, setHomebot] = useState({ connected: false, status: "unknown" });

  useEffect(() => {
    if (!auth) {
      setLoading(false);
      return;
    }
    const unsub = onAuthStateChanged(auth, (u) => {
      if (u) {
        const email = u.email;
        const role = ADMIN_EMAILS.includes(email) ? 'admin' : 'viewer';
        setUserRole(role);
      }
      setUser(u);
      setLoading(false);
    });
    return unsub;
  }, []);

  const handleLogin = (email, pass) => {
    setLoading(true);
    setAuthError("");
    signInWithEmailAndPassword(auth, email, pass)
      .catch(e => setAuthError("NEURAL SCAN FAILED: " + e.message))
      .finally(() => setLoading(false));
  };

  const handleGoogleLogin = async () => {
    setLoading(true);
    setAuthError("");
    try {
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
    } catch (e) {
      setAuthError("GOOGLE AUTH FAILED: " + e.message);
    }
    setLoading(false);
  };

  const handleLogout = () => signOut(auth);

  const fetchAegisData = async () => {
    try {
      const token = user?.accessToken;
      const res = await fetch(`${API_BASE_URL}/v1/system/stats`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (res.ok) {
        const data = await res.json();
        setAegisData(prev => ({
          ...prev,
          cpu: data.cpu_percent || 0,
          ram: data.memory_percent || 0,
          status: data.status || "ACTIVE"
        }));
        const timestamp = new Date().toLocaleTimeString();
        setHistory(h => [...h, { time: timestamp, cpu: data.cpu_percent || 0, ram: data.memory_percent || 0 }].slice(-30));
      }
    } catch (err) {
      console.log("AEGIS server not reachable - using Firestore fallback");
    }
  };

  const fetchModules = async () => {
    try {
      const token = user?.accessToken;
      const res = await fetch(`${API_BASE_URL}/v1/modules`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (res.ok) {
        const data = await res.json();
        setModules(data);
      }
    } catch (err) {
      console.error("Modules fetch error:", err);
    }
  };

  const fetchHomebot = async () => {
    try {
      const token = user?.accessToken;
      const res = await fetch(`${API_BASE_URL}/v1/homebot/status`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (res.ok) {
        const data = await res.json();
        setHomebot(data);
      }
    } catch (err) {
      console.error("HomeBot fetch error:", err);
    }
  };

  useEffect(() => {
    if (!user || !db) return;

    fetchAegisData();
    fetchModules();
    fetchHomebot();
    const apiInterval = setInterval(fetchAegisData, 5000);
    const moduleInterval = setInterval(fetchModules, 8000);
    const homebotInterval = setInterval(fetchHomebot, 8000);

    const nodeRef = doc(db, "telemetry_nodes", "aegis-primary");
    const unsubNode = onSnapshot(nodeRef, (snapshot) => {
      if (snapshot.exists()) {
        const data = snapshot.data();
        setAegisData(prev => ({
          ...prev,
          cpu: data.vitals?.cpu_percent || data.metrics?.cpu_percent || 0,
          ram: data.vitals?.memory_percent || data.metrics?.memory_percent || 0,
          hr: data.vitals?.heart_rate || 72,
          mood: data.vitals?.mood || "Calm",
          status: data.status?.mode === "low" ? "IDLE" : "ACTIVE",
          alerts: data.social?.alerts || []
        }));

        const timestamp = new Date().toLocaleTimeString();
        setHistory(h => [...h, { time: timestamp, cpu: data.vitals?.cpu_percent || 0, ram: data.vitals?.memory_percent || 0 }].slice(-30));
      }
    });

    const logQuery = query(collection(nodeRef, "logs"), orderBy("timestamp", "desc"), limit(20));
    const unsubLogs = onSnapshot(logQuery, (snapshot) => {
      const newLogs = snapshot.docs.map(d => d.data());
      setLogs(newLogs);
    });

    const wsToken = user?.accessToken;
    const wsUrl = API_BASE_URL.replace(/^http/, 'ws') + `/ws/events${wsToken ? `?token=${wsToken}` : ""}`;
    let ws;
    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          const { type, data } = msg;
          if (type === "voice_response") {
            setLogs(l => [{ text: data, timestamp: Date.now() / 1000, type: 'info' }, ...l].slice(0, 200));
            setLiveFeed(f => [{ text: `RESP: ${data}`, ts: Date.now(), kind: 'success' }, ...f].slice(0, 120));
          } else if (type === "voice_command") {
            const text = typeof data === "string" ? data : data?.command || "voice command";
            setLogs(l => [{ text: `CMD: ${text}`, timestamp: Date.now() / 1000, type: 'info' }, ...l].slice(0, 200));
            setLiveFeed(f => [{ text: `CMD: ${text}`, ts: Date.now(), kind: 'info' }, ...f].slice(0, 120));
          } else if (type === "vitals_update" && data?.value) {
            setAegisData(prev => ({ ...prev, hr: data.value }));
          } else if (type === "environment_event" && data?.summary) {
            setAegisData(prev => ({ ...prev, surroundings: data.summary }));
          }
        } catch (e) {
          console.error("WS parse error", e);
        }
      };
    } catch (e) {
      console.error("WS connect failed", e);
    }

    return () => {
      clearInterval(apiInterval);
      clearInterval(moduleInterval);
      clearInterval(homebotInterval);
      unsubNode();
      unsubLogs();
      if (ws) ws.close();
    };
  }, [user]);

  const sendCommand = async (e) => {
    if (e) e.preventDefault();
    if (!command.trim()) return;

    try {
      const token = user?.accessToken;
      const res = await fetch(`${API_BASE_URL}/v1/commands`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ command })
      });
      
      if (res.ok) {
        setLogs([{ text: `Dispatching: ${command}`, timestamp: Date.now() / 1000, type: 'success' }, ...logs]);
        setCommand("");
        return;
      }
      
      const nodeRef = doc(db, "telemetry_nodes", "aegis-primary");
      await addDoc(collection(nodeRef, "remote_commands"), {
        command: command,
        status: "pending",
        timestamp: serverTimestamp(),
        source: "web-dashboard"
      });
      setLogs([{ text: `Dispatching: ${command}`, timestamp: Date.now() / 1000, type: 'success' }, ...logs]);
      setCommand("");
    } catch (err) {
      console.error("Command Error:", err);
      setLogs([{ text: `Error: ${err.message}`, timestamp: Date.now() / 1000, type: 'error' }, ...logs]);
    }
  };

  const sendModuleAction = async (name, action) => {
    try {
      const token = user?.accessToken;
      const res = await fetch(`${API_BASE_URL}/v1/modules/${name}/${action}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        }
      });
      if (res.ok) {
        setLogs(l => [{ text: `${name} -> ${action}`, timestamp: Date.now() / 1000, type: 'success' }, ...l].slice(0, 200));
        fetchModules();
      } else {
        throw new Error('Action failed');
      }
    } catch (err) {
      setLogs(l => [{ text: `Module error: ${err.message}`, timestamp: Date.now() / 1000, type: 'error' }, ...l]);
    }
  };

  const triggerWake = async () => {
    if (userRole !== 'admin') {
      alert("Admin access required for wake command");
      return;
    }
    setWakeLoading(true);
    try {
      const token = user?.accessToken;
      const res = await fetch(`${API_BASE_URL}/v1/wake`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ target: 'saturday', source: 'web_dashboard' })
      });
      
      if (res.ok) {
        alert("WAKE SIGNAL DISPATCHED TO SATURDAY");
        setLogs([{ text: "WAKE: Remote activation triggered", timestamp: Date.now() / 1000, type: 'success' }, ...logs]);
      } else {
        throw new Error('Wake failed');
      }
    } catch (err) { 
      console.error("Wake Error:", err);
      alert("Wake Failed: " + err.message); 
    }
    setWakeLoading(false);
  };

  if (loading) return <div className="auth-shell"><div className="loader">INITIALIZING AEGIS CORE...</div></div>;

  if (!user) return (
    <div className="auth-shell">
      <div className="auth-card">
        <BrainCircuit size={64} color="var(--accent-blue)" className="floating" />
        <h1 style={{ marginTop: "1rem" }}>AEGIS CORE</h1>
        <p>IDENTIFICATION REQUIRED TO ACCESS COMMAND CENTER</p>
        
        <button 
          onClick={handleGoogleLogin}
          style={{ 
            width: '100%', 
            padding: '12px', 
            marginBottom: '15px',
            background: '#fff', 
            color: '#333',
            border: 'none', 
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px'
          }}
        >
          <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" width="18" height="18" alt="Google" />
          Sign in with Google
        </button>
        
        <div style={{ textAlign: 'center', margin: '10px 0', color: 'var(--text-secondary)' }}>OR</div>
        
        <form onSubmit={(e) => { e.preventDefault(); handleLogin(document.getElementById('email').value, document.getElementById('pass').value); }}>
          <div style={{ textAlign: "left" }}>
            <label>Neural Identity</label>
            <input id="email" type="email" placeholder="Email" required />
            <label>Access Code</label>
            <input id="pass" type="password" placeholder="••••••••" required />
          </div>
          <div className="auth-actions">
            <button type="submit">ACCESS</button>
            <button type="button" onClick={() => setAuthError("Contact Admin for Neural Registration")}>REQUEST ID</button>
          </div>
        </form>
        {authError && <div className="error-msg">{authError}</div>}
      </div>
    </div>
  );

  return (
    <div className="dashboard-container">
      {/* --- Sidebar Nav --- */}
      <aside className="sidebar">
        <div className="panel" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
            <div className="avatar-orb">
              <User size={40} color="var(--accent-blue)" />
              <div className="orb-ring"></div>
            </div>
            <h4>{user.email.split('@')[0].toUpperCase()}</h4>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "5px", marginTop: "5px" }}>
              <div className="status-dot online"></div>
              <span className="auth-label">{userRole.toUpperCase()} AUTHORIZED</span>
            </div>
          </div>

          <nav className="nav-stack">
            <button className={view === "dashboard" ? "active-nav" : "nav-item"} onClick={() => setView("dashboard")}>
              <LayoutDashboard size={18} /> COMMANDS
            </button>
            <button className={view === "vision" ? "active-nav" : "nav-item"} onClick={() => setView("vision")}>
              <Camera size={18} /> VISION HUB
            </button>
            <button className={view === "modules" ? "active-nav" : "nav-item"} onClick={() => setView("modules")}>
              <Settings size={18} /> MODULES
            </button>
            <button className={view === "homebot" ? "active-nav" : "nav-item"} onClick={() => setView("homebot")}>
              <Smartphone size={18} /> HOMEBOT
            </button>
            <button className={view === "mobile" ? "active-nav" : "nav-item"} onClick={() => setView("mobile")}>
              <Smartphone size={18} /> MOBILE HUB
            </button>
          </nav>

          <div style={{ marginTop: "auto" }}>
            <div className="cloud-status panel" style={{ marginBottom: "1rem", padding: "10px", fontSize: "0.7rem", textAlign: "center" }}>
              <Globe size={14} style={{ marginRight: "5px" }} /> {isCloud ? "CLOUD RELAY ACTIVE" : "LOCAL LINK ACTIVE"}
            </div>
            <button className="nav-item logout-btn" onClick={handleLogout}>
              <LogOut size={18} /> DISCONNECT
            </button>
          </div>
        </div>
      </aside>

      {/* --- Main Dashboard --- */}
      <main className="main-content">
        {/* Top Header Stats */}
        <div className="stats-row">
          <StatCard title="CPU COMPUTE" value={Math.round(aegisData.cpu)} unit="%" icon={Activity} />
          <StatCard title="MEMORY MAP" value={Math.round(aegisData.ram)} unit="%" icon={Database} />
          <StatCard title="HEART RATE" value={aegisData.hr} unit="BPM" icon={Heart} color="#ff4b2b" />
          <StatCard title="MOOD / EMOTION" value={aegisData.mood} unit="" icon={Mic} color="#00e676" />
        </div>

        {view === "dashboard" && (
          <div className="fade-in grid-dashboard">
            {/* Chart */}
            <div className="panel chart-panel">
              <SectionHeader title="NEURAL PERFORMANCE" icon={BrainCircuit} />
              <div style={{ width: "100%", height: 260 }}>
                <ResponsiveContainer>
                  <AreaChart data={history}>
                    <defs>
                      <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--accent-blue)" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="var(--accent-blue)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="cpu" stroke="#00d2ff" fillOpacity={1} fill="url(#colorValue)" strokeWidth={2} isAnimationActive={false} />
                    <XAxis dataKey="time" hide />
                    <YAxis domain={[0, 100]} hide />
                    <Tooltip contentStyle={{ background: "#050a10", border: "1px solid var(--border-glow)", color: "#fff" }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Vision Preview */}
            <div className="panel v-broadcast">
              <SectionHeader title="SURROUNDINGS BROADCAST" icon={Eye} />
              <div className="video-shell">
                <div className="scan-line"></div>
                <div className="cam-overlay">
                  <span>REC: {new Date().toLocaleTimeString()}</span>
                  <span>DL_INTENSITY: 98%</span>
                </div>
                <img src={`${API_BASE_URL}/vision/stream`} className="stream-img" alt="LIVE_CAM_OFFLINE" />
              </div>
            </div>

            {/* Social Intelligence */}
            <div className="panel social-panel">
              <SectionHeader title="SOCIAL INTELLIGENCE" icon={Bell} />
              <div className="data-list">
                {aegisData.alerts.length > 0 ? aegisData.alerts.map((a, i) => (
                  <div key={i} className="data-row alert-row">
                    <div className="alert-badge">{a.source}</div>
                    <span className="alert-content"><strong>{a.from}</strong>: {a.text}</span>
                  </div>
                )) : (
                  <div className="empty-state">Secure. No pending social alerts.</div>
                )}
              </div>
            </div>

            {/* Directives */}
            <div className="panel directive-panel">
              <SectionHeader title="DIRECTIVES" icon={Zap} />
              <div className="action-grid">
                <button className="tile-btn" onClick={triggerWake} disabled={wakeLoading}>
                  {wakeLoading ? <Power size={18} className="spin" /> : <Zap size={18} />} 
                  {wakeLoading ? "WAKING..." : "CLOUD WAKE"}
                </button>
                <button className="tile-btn"><Music size={18} /> MUSIC SYS</button>
                <button className="tile-btn"><Shield size={18} /> DEFENSE</button>
                <button className="tile-btn"><Radio size={18} /> BROADCAST</button>
              </div>
            </div>
          </div>
        )}

        {view === "modules" && (
          <div className="fade-in grid-dashboard">
            <div className="panel">
              <SectionHeader title="MODULE STATUS" icon={Settings} />
              <div className="module-grid">
                {Object.entries(modules).map(([name, online]) => (
                  <div key={name} className={`module-card ${online ? 'online' : 'offline'}`}>
                    <div className="module-head">
                      <span className="status-dot-small" style={{ background: online ? '#00e676' : '#ff4b2b' }}></span>
                      <strong>{name.toUpperCase()}</strong>
                    </div>
                    <div className="module-actions">
                      <button onClick={() => sendModuleAction(name, 'start')}>Start</button>
                      <button onClick={() => sendModuleAction(name, 'stop')}>Stop</button>
                      <button onClick={() => sendModuleAction(name, 'restart')}>Restart</button>
                    </div>
                  </div>
                ))}
                {Object.keys(modules).length === 0 && (
                  <div className="empty-state">No modules reported yet.</div>
                )}
              </div>
            </div>
          </div>
        )}

        {view === "homebot" && (
          <div className="fade-in grid-dashboard">
            <div className="panel">
              <SectionHeader title="HOMEBOT STATUS" icon={Smartphone} />
              <p style={{ color: "var(--text-secondary)" }}>
                Connection: {homebot.connected ? "Online" : "Offline"} | State: {homebot.status}
              </p>
              <div className="action-grid">
                <button className="tile-btn" onClick={() => sendModuleAction('homebot', 'restart')}>Restart HomeBot</button>
                <button className="tile-btn" onClick={() => sendModuleAction('homebot', 'start')}>Start</button>
                <button className="tile-btn" onClick={() => sendModuleAction('homebot', 'stop')}>Stop</button>
              </div>
            </div>
          </div>
        )}

        {view === "mobile" && (
          <div className="fade-in mobile-hub">
            <div className="panel">
              <SectionHeader title="MOBILE REMOTE HUB" icon={Smartphone} />
              <p style={{ color: "var(--text-secondary)", marginBottom: "1.5rem" }}>
                Connect your phone as a remote input device or biometric sensor.
              </p>
              <div className="hub-grid">
                <div className="hub-card">
                  <h4>REMOTE ACCESS</h4>
                  <div className="qr-box">
                    <Radio size={48} color="var(--accent-blue)" />
                    <span>SCAN TO CONNECT</span>
                  </div>
                  <button className="nav-item">GET APP LINK</button>
                </div>
                <div className="hub-card">
                  <h4>OFFLINE WAKE</h4>
                  <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    Can't reach AEGIS? Use our dedicated cloud server to force a local wake.
                  </p>
                  <button className="nav-item action-btn" onClick={triggerWake}>DEPLOY WAKE SIGNAL</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {view === "vision" && (
          <div className="fade-in full-vision">
            <div className="panel" style={{ height: "100%" }}>
              <SectionHeader title="ADVANCED VISION ANALYSIS" icon={Maximize} />
              <div className="video-shell large">
                <div className="scan-effect"></div>
                <img src={`${API_BASE_URL}/vision/stream`} className="stream-img" alt="VISION_CORE" />
              </div>
            </div>
          </div>
        )}

        {view === "voice" && (
          <div className="fade-in grid-dashboard">
            <div className="panel">
              <SectionHeader title="VOICE STREAM" icon={Mic} />
              <div className="terminal-feed" style={{ minHeight: 260 }}>
                {liveFeed.map((line, i) => (
                  <div key={i} className={`terminal-line ${line.kind || 'info'}`}>
                    <span className="log-ts">[{new Date(line.ts).toLocaleTimeString()}]</span>
                    <span className="log-txt">{line.text}</span>
                  </div>
                ))}
                {liveFeed.length === 0 && <div className="empty-state">Listening for voice and responses...</div>}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* --- Right Interactive Bar --- */}
      <section className="right-bar">
        <div className="panel terminal-panel" style={{ flex: 1 }}>
          <SectionHeader title="AEGIS COMMAND INTERFACE" icon={Terminal} />
          <div className="terminal-feed">
            {logs.map((log, i) => (
              <div key={i} className={`terminal-line ${log.type}`}>
                <span className="log-ts">[{new Date(log.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}]</span>
                <span className="log-txt">{log.text}</span>
              </div>
            ))}
          </div>
          <form className="terminal-input" onSubmit={sendCommand}>
            <input
              type="text"
              placeholder="INPUT DIRECTIVE..."
              value={command}
              onChange={(e) => setCommand(e.target.value)}
            />
            <button type="submit"><Send size={16} /></button>
          </form>
        </div>
      </section>

      {/* --- Inline Extra CSS --- */}
      <style>{`
        .main-content { padding: 20px; overflow-y: auto; }
        .stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 20px; }
        .grid-dashboard { display: grid; grid-template-columns: 2fr 1.2fr; grid-template-rows: auto auto; gap: 20px; }
        .chart-panel { grid-column: 1 / 2; }
        .v-broadcast { grid-column: 2 / 3; }
        .social-panel { grid-column: 1 / 2; }
        .directive-panel { grid-column: 2 / 3; }
        .module-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
        .module-card { background: rgba(255,255,255,0.03); border: 1px solid var(--border-glow); border-radius: 12px; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
        .module-card.online { box-shadow: 0 0 10px rgba(0,230,118,0.3); }
        .module-card.offline { box-shadow: 0 0 10px rgba(255,75,43,0.2); }
        .module-head { display: flex; align-items: center; gap: 8px; font-weight: 700; }
        .status-dot-small { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .module-actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
        .module-actions button { padding: 0.5rem; font-size: 0.8rem; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); }
        .module-actions button:hover { border-color: var(--accent-blue); }

        .glow-border { border: 1px solid var(--border-glow); position: relative; }
        .glow-border:hover { border-color: var(--accent-blue); box-shadow: 0 0 15px var(--accent-glow); }
        
        .avatar-orb { 
          width: 80px; height: 80px; border-radius: 50%; margin: 0 auto 15px;
          border: 2px solid var(--accent-blue); display: flex; align-items: center; justify-content: center;
          position: relative; background: var(--bg-deep);
        }
        .orb-ring {
          position: absolute; top: -5px; left: -5px; right: -5px; bottom: -5px;
          border: 1px solid var(--accent-teal); border-radius: 50%; border-left-color: transparent;
          animation: spin 3s linear infinite;
        }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

        .terminal-feed {
          height: calc(100% - 120px); overflow-y: auto; font-family: 'JetBrains Mono', monospace;
          font-size: 0.75rem; padding: 10px; display: flex; flex-direction: column; gap: 8px;
        }
        .terminal-line { display: flex; gap: 10px; opacity: 0.8; }
        .log-ts { color: var(--text-secondary); min-width: 60px; }
        .terminal-input {
          display: flex; gap: 10px; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 12px;
          border: 1px solid var(--border-glow);
        }
        .terminal-input input { background: transparent; border: none; margin: 0; padding: 5px; flex: 1; font-family: inherit; }
        .terminal-input button { padding: 0 15px; background: var(--accent-blue); color: #000; border-radius: 8px; }

        .video-shell { 
          width: 100%; aspect-ratio: 16/9; background: #000; border-radius: 15px; 
          overflow: hidden; position: relative; border: 1px solid var(--border-glow);
        }
        .stream-img { width: 100%; height: 100%; object-fit: cover; opacity: 0.7; }
        .scan-line {
          position: absolute; top: 0; left: 0; width: 100%; height: 2px;
          background: var(--accent-blue); box-shadow: 0 0 10px var(--accent-blue);
          animation: scan 4s linear infinite; z-index: 5;
        }
        @keyframes scan { 0% { top: 0; } 100% { top: 100%; } }

        .tile-btn {
          background: rgba(255,255,255,0.05); border: 1px solid var(--border-glow);
          color: white; padding: 15px; border-radius: 12px; cursor: pointer;
          display: flex; flex-direction: column; align-items: center; gap: 10px; font-size: 0.7rem;
        }
        .tile-btn:hover { background: var(--accent-glow); border-color: var(--accent-blue); transform: translateY(-2px); }
        .action-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

        .hub-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 10px; }
        .hub-card { 
          background: rgba(255,255,255,0.03); padding: 25px; border-radius: 20px; 
          display: flex; flex-direction: column; align-items: center; gap: 15px; border: 1px solid var(--border-glow);
        }
        .qr-box { 
          width: 120px; height: 120px; background: white; border-radius: 10px; 
          display: flex; flex-direction: column; align-items: center; justify-content: center;
          color: #000; font-size: 0.6rem; font-weight: bold; padding: 10px; text-align: center;
        }
        .action-btn { background: var(--accent-blue) !important; color: #000 !important; font-weight: bold; }
        .error-msg { background: rgba(255, 75, 43, 0.1); color: var(--danger); padding: 10px; border-radius: 8px; margin-top: 1rem; font-size: 0.8rem; border: 1px solid var(--danger); }
        
        .nav-item { 
          display: flex; align-items: center; gap: 15px; padding: 12px 20px; border: none;
          background: transparent; color: var(--text-secondary); cursor: pointer; width: 100%;
          border-radius: 12px; text-align: left; font-size: 0.9rem; transition: all 0.2s;
        }
        .nav-item:hover { background: rgba(255,255,255,0.05); color: white; }
        .active-nav { background: var(--accent-glow) !important; color: var(--accent-blue) !important; font-weight: 600; }
        .logout-btn:hover { background: rgba(255, 75, 43, 0.1) !important; color: var(--danger) !important; }
      `}</style>
    </div>
  );
}

export default App;
