import { useState, useEffect } from 'react';
import { Brain, MessageSquare, Zap, Activity, Cpu, Network, Bot, Sparkles } from 'lucide-react';
import { apiService } from '../services/api';
import './AIAgent.css';

const AIAgent = () => {
  const [aiStatus, setAiStatus] = useState(null);
  const [brainStatus, setBrainStatus] = useState(null);
  const [command, setCommand] = useState('');
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);

  const fetchAIStatus = async () => {
    try {
      const [status, brain] = await Promise.all([
        apiService.getAIStatus().catch(() => null),
        apiService.getAIBrain().catch(() => null),
      ]);
      
      if (status) setAiStatus(status);
      if (brain) setBrainStatus(brain);
    } catch (error) {
      console.error('Failed to fetch AI status:', error);
    }
  };

  useEffect(() => {
    fetchAIStatus();
    const interval = setInterval(fetchAIStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleCommand = async (e) => {
    e.preventDefault();
    if (!command.trim()) return;
    
    setLoading(true);
    setResponse(null);
    
    try {
      const result = await apiService.sendAICommand(command);
      setResponse(result);
      setHistory(prev => [...prev, { command, response: result, time: new Date() }]);
      setCommand('');
    } catch (error) {
      setResponse({ error: 'Failed to process command' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-agent-page">
      <header className="page-header">
        <div>
          <h1><Brain size={28} /> AEGIS AI Agent</h1>
          <p className="subtitle">Real Deep Learning Powered</p>
        </div>
        <div className="status-badge">
          <span className="pulse"></span>
          Neural Network Active
        </div>
      </header>

      <div className="ai-grid">
        <div className="ai-status-card">
          <div className="card-header">
            <Bot size={24} />
            <h2>AI Agent Status</h2>
          </div>
          
          {aiStatus ? (
            <div className="status-stats">
              <div className="stat-row">
                <span className="stat-label">Active</span>
                <span className={`stat-value ${aiStatus.active ? 'online' : 'offline'}`}>
                  {aiStatus.active ? 'Online' : 'Offline'}
                </span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Commands Processed</span>
                <span className="stat-value">{aiStatus.commands_processed || 0}</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Unique Commands</span>
                <span className="stat-value">{aiStatus.unique_commands || 0}</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Patterns Learned</span>
                <span className="stat-value">{aiStatus.patterns_learned || 0}</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Neural Network Size</span>
                <span className="stat-value">{aiStatus.brain_neurons || 0} neurons</span>
              </div>
            </div>
          ) : (
            <div className="loading">Loading AI Status...</div>
          )}
        </div>

        <div className="brain-status-card">
          <div className="card-header">
            <Network size={24} />
            <h2>Neural Brain</h2>
          </div>
          
          {brainStatus ? (
            <div className="brain-visual">
              <div className="neural-layer input">
                <span>Input Layer</span>
                <div className="neurons">
                  {[...Array(8)].map((_, i) => (
                    <div key={i} className="neuron active"></div>
                  ))}
                </div>
              </div>
              <div className="neural-layer hidden">
                <span>Hidden Layer</span>
                <div className="neurons">
                  {[...Array(12)].map((_, i) => (
                    <div key={i} className="neuron processing"></div>
                  ))}
                </div>
              </div>
              <div className="neural-layer output">
                <span>Output Layer</span>
                <div className="neurons">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="neuron ready"></div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="loading">Initializing Brain...</div>
          )}
        </div>

        <div className="command-interface">
          <div className="card-header">
            <MessageSquare size={24} />
            <h2>AI Command Interface</h2>
          </div>
          
          <form onSubmit={handleCommand} className="command-form">
            <input
              type="text"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder="Ask AEGIS anything..."
              disabled={loading}
              className="command-input"
            />
            <button type="submit" disabled={loading || !command.trim()} className="send-btn">
              {loading ? <Activity className="spinning" size={18} /> : <Zap size={18} />}
              {loading ? 'Processing...' : 'Send'}
            </button>
          </form>

          {response && (
            <div className={`response ${response.type}`}>
              <div className="response-header">
                <Sparkles size={16} />
                <span>AEGIS Response</span>
                <span className="confidence">{(response.confidence * 100).toFixed(0)}% confidence</span>
              </div>
              <p>{response.message}</p>
              {response.action && response.action !== 'none' && (
                <div className="response-action">
                  Action: {response.action}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="command-history">
          <div className="card-header">
            <Activity size={24} />
            <h2>Interaction History</h2>
          </div>
          
          <div className="history-list">
            {history.length > 0 ? (
              history.slice().reverse().map((item, idx) => (
                <div key={idx} className="history-item">
                  <div className="history-command">
                    <span className="label">You:</span> {item.command}
                  </div>
                  <div className="history-response">
                    <span className="label">AEGIS:</span> {item.response?.message}
                  </div>
                </div>
              ))
            ) : (
              <div className="no-history">No interactions yet</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AIAgent;
