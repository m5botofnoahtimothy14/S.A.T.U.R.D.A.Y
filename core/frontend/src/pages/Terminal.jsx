import { useState, useEffect, useRef } from 'react';
import { Terminal as TerminalIcon, Play, Square, RefreshCw } from 'lucide-react';
import './Terminal.css';

const Terminal = () => {
  const [history, setHistory] = useState([
    { type: 'output', content: 'AEGIS Security Terminal v2.0.0' },
    { type: 'output', content: 'Type "help" for available commands' },
    { type: 'output', content: '────────────────────────────────────────' },
  ]);
  const [input, setInput] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const terminalRef = useRef(null);

  const commands = {
    help: 'Available commands: status, scan, threats, clear, defend, network, logs',
    status: 'System Status: ONLINE\nFirewall: ACTIVE\nDL Defense: NEURAL PROCESSING\nThreats Blocked: 1247',
    scan: 'Running deep scan...\n✓ File System: Clean\n✓ Network Ports: Secure\n✓ Memory: No anomalies\n✓ Registry: Clean\nScan complete. No threats detected.',
    threats: 'Recent Threats:\n[2024-02-27 14:32] Malware blocked from 192.168.1.45\n[2024-02-27 14:28] Port scan detected from external IP\n[2024-02-27 14:15] Brute force attempt mitigated',
    defend: 'AEGIS DL Defense System Activated\n• ANN Malware Detection: RUNNING\n• Neural Network Classifier: ACTIVE\n• Behavior Analysis: MONITORING\n• Zero-Day Protection: ENABLED',
    network: 'Network Statistics:\nActive Connections: 89\nInbound Blocked: 234\nOutbound Allowed: 567\nBandwidth: 125 MB/s',
    logs: 'Fetching security logs...\n[14:32:01] BLOCK  Malicious packet from 45.33.xx.xx\n[14:31:58] ALERT  Suspicious login attempt\n[14:31:45] INFO   DL model updated: malware_detector_v3.2',
  };

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [history]);

  const handleCommand = (e) => {
    if (e.key === 'Enter') {
      const cmd = input.trim().toLowerCase();
      const newHistory = [...history, { type: 'input', content: `> ${input}` }];
      
      if (cmd === 'clear') {
        setHistory([]);
      } else if (commands[cmd]) {
        newHistory.push({ type: 'output', content: commands[cmd] });
      } else if (cmd) {
        newHistory.push({ type: 'error', content: `Command not found: ${cmd}` });
      }
      
      setHistory(newHistory);
      setInput('');
    }
  };

  return (
    <div className="terminal-page">
      <header className="terminal-header">
        <div className="header-left">
          <TerminalIcon size={24} />
          <h1>AEGIS Terminal</h1>
        </div>
        <div className="terminal-controls">
          <button className={`control-btn ${isRunning ? 'active' : ''}`} onClick={() => setIsRunning(!isRunning)}>
            {isRunning ? <Square size={16} /> : <Play size={16} />}
            {isRunning ? 'Stop' : 'Run'}
          </button>
          <button className="control-btn" onClick={() => setHistory([...history, { type: 'output', content: 'Terminal cleared' }])}>
            <RefreshCw size={16} />
          </button>
        </div>
      </header>

      <div className="terminal-container" ref={terminalRef}>
        {history.map((line, index) => (
          <div key={index} className={`terminal-line ${line.type}`}>
            {line.content}
          </div>
        ))}
        <div className="input-line">
          <span className="prompt">AEGIS&gt;</span>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleCommand}
            placeholder="Type command..."
            autoFocus
          />
        </div>
      </div>

      <div className="terminal-info">
        <span>DL Engine: Active</span>
        <span>ANN Model: Loaded</span>
        <span>Session: Secure</span>
      </div>
    </div>
  );
};

export default Terminal;
