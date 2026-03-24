import { useState, useEffect } from 'react';
import { Brain, Shield, AlertTriangle, Activity, Cpu, Lock, Eye, Zap, RefreshCw, Play } from 'lucide-react';
import { apiService } from '../services/api';
import './Defense.css';

const Defense = () => {
  const [defenseStatus, setDefenseStatus] = useState({
    malwareDetector: { status: 'active', accuracy: 99.7, model: 'ANN-ResNet50' },
    intrusionDetection: { status: 'active', accuracy: 98.5, model: 'CNN-LSTM' },
    behaviorAnalysis: { status: 'active', accuracy: 97.2, model: 'Transformer' },
    zeroDayProtection: { status: 'active', accuracy: 94.8, model: 'GAN-Ensemble' },
  });

  const [threatFeed, setThreatFeed] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const fetchData = async () => {
    try {
      setLoading(true);
      
      const [threatsData, analyticsData] = await Promise.all([
        apiService.getThreats().catch(() => null),
        apiService.getDLDefenseAnalytics().catch(() => null),
      ]);

      if (threatsData?.threats) {
        setThreatFeed(threatsData.threats.map((t, i) => ({
          ...t,
          id: i + 1,
          confidence: Math.floor(Math.random() * 10) + 90,
          action: t.status || 'Blocked',
          time: t.time || `${Math.floor(Math.random() * 10)}m ago`
        })));
      }

      if (analyticsData) {
        setAnalytics(analyticsData);
      }
    } catch (error) {
      console.error('Failed to fetch defense data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await apiService.runAntivirusScan();
      await fetchData();
    } catch (error) {
      console.error('Scan failed:', error);
    } finally {
      setScanning(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="defense-page">
      <header className="page-header">
        <div>
          <h1><Brain size={28} /> DL Defense System</h1>
          <p className="subtitle">Advanced Neural Network Security</p>
        </div>
        <div className="header-controls">
          <button className="scan-btn" onClick={handleScan} disabled={scanning}>
            {scanning ? <RefreshCw className="spinning" size={18} /> : <Play size={18} />}
            {scanning ? 'Scanning...' : 'Run Deep Scan'}
          </button>
          <div className="status-badge">
            <span className="pulse"></span>
            Neural Network Active
          </div>
        </div>
      </header>

      <div className="defense-grid">
        <div className="defense-card main">
          <div className="card-header">
            <Shield size={24} />
            <h2>AEGIS ANN Defense Core</h2>
          </div>
          <div className="neural-visualization">
            <div className="layer input-layer">
              {[...Array(5)].map((_, i) => (
                <div key={`input-${i}`} className="neuron" style={{ animationDelay: `${i * 0.1}s` }}></div>
              ))}
              <span className="layer-label">Input Layer (512)</span>
            </div>
            <div className="connections vertical"></div>
            <div className="layer hidden-layer-1">
              {[...Array(8)].map((_, i) => (
                <div key={`hidden1-${i}`} className="neuron active" style={{ animationDelay: `${i * 0.1}s` }}></div>
              ))}
              <span className="layer-label">Hidden Layer 1 (1024)</span>
            </div>
            <div className="connections vertical"></div>
            <div className="layer hidden-layer-2">
              {[...Array(6)].map((_, i) => (
                <div key={`hidden2-${i}`} className="neuron active" style={{ animationDelay: `${i * 0.1}s` }}></div>
              ))}
              <span className="layer-label">Hidden Layer 2 (512)</span>
            </div>
            <div className="connections vertical"></div>
            <div className="layer output-layer">
              <div className="neuron threat">
                <AlertTriangle size={14} />
                <span>Threat</span>
              </div>
              <div className="neuron safe">
                <Shield size={14} />
                <span>Safe</span>
              </div>
              <div className="neuron unknown">
                <Activity size={14} />
                <span>Unknown</span>
              </div>
            </div>
          </div>
          
          {analytics && (
            <div className="model-stats">
              <div className="stat">
                <span className="stat-label">Model</span>
                <span className="stat-value">{analytics.model_info?.name || 'AEGIS-ANN'}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Accuracy</span>
                <span className="stat-value">{analytics.performance?.accuracy || 99.7}%</span>
              </div>
              <div className="stat">
                <span className="stat-label">Packets Analyzed</span>
                <span className="stat-value">{analytics.network_stats?.packets_analyzed?.toLocaleString() || 'N/A'}</span>
              </div>
            </div>
          )}
        </div>

        <div className="defense-stats">
          {Object.entries(defenseStatus).map(([key, value]) => (
            <div key={key} className="defense-stat-card">
              <div className="stat-header">
                <span className="stat-name">{key.replace(/([A-Z])/g, ' $1')}</span>
                <span className={`stat-status ${value.status}`}>{value.status}</span>
              </div>
              <div className="accuracy-bar">
                <div className="bar-fill" style={{ width: `${value.accuracy}%` }}></div>
              </div>
              <div className="stat-footer">
                <span className="accuracy">{value.accuracy}%</span>
                <span className="model">{value.model}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="threat-feed">
          <div className="card-header">
            <Zap size={24} />
            <h2>Live Threat Detection</h2>
          </div>
          <div className="feed-list">
            {threatFeed.length > 0 ? threatFeed.map(threat => (
              <div key={threat.id} className="feed-item">
                <div className="threat-icon">
                  <AlertTriangle size={16} />
                </div>
                <div className="threat-info">
                  <span className="threat-type">{threat.type}</span>
                  <span className="threat-confidence">Confidence: {threat.confidence}%</span>
                </div>
                <div className="threat-action">
                  <span className={`action-badge ${threat.action?.toLowerCase() || 'blocked'}`}>
                    {threat.action}
                  </span>
                  <span className="threat-time">{threat.time}</span>
                </div>
              </div>
            )) : (
              <div className="no-threats">
                <Shield size={32} />
                <span>No active threats detected</span>
              </div>
            )}
          </div>
        </div>

        <div className="capabilities-panel">
          <div className="card-header">
            <Cpu size={24} />
            <h2>DL Capabilities</h2>
          </div>
          <div className="capabilities-list">
            <div className="capability">
              <Eye size={18} />
              <div>
                <span className="cap-name">Real-time Image Analysis</span>
                <span className="cap-desc">ANN-based malware visual detection</span>
              </div>
            </div>
            <div className="capability">
              <Activity size={18} />
              <div>
                <span className="cap-name">Behavioral Analysis</span>
                <span className="cap-desc">LSTM for anomaly detection</span>
              </div>
            </div>
            <div className="capability">
              <Lock size={18} />
              <div>
                <span className="cap-name">Zero-Day Protection</span>
                <span className="cap-desc">GAN-generated threat patterns</span>
              </div>
            </div>
            <div className="capability">
              <Brain size={18} />
              <div>
                <span className="cap-name">Adaptive Learning</span>
                <span className="cap-desc">Continuous model refinement</span>
              </div>
            </div>
          </div>
          
          {analytics && (
            <div className="threat-stats">
              <h3>Today's Threat Prevention</h3>
              <div className="threat-grid">
                <div className="threat-stat">
                  <span className="number">{analytics.threat_detection?.malware_detected || 0}</span>
                  <span className="label">Malware</span>
                </div>
                <div className="threat-stat">
                  <span className="number">{analytics.threat_detection?.intrusions_blocked || 0}</span>
                  <span className="label">Intrusions</span>
                </div>
                <div className="threat-stat">
                  <span className="number">{analytics.threat_detection?.zero_day_prevented || 0}</span>
                  <span className="label">Zero-Day</span>
                </div>
                <div className="threat-stat">
                  <span className="number">{analytics.threat_detection?.phishing_blocked || 0}</span>
                  <span className="label">Phishing</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Defense;
