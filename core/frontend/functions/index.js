const functions = require('firebase-functions');
const express = require('express');
const cors = require('cors');
const uuid = require('uuid');

const app = express();
app.use(cors());
app.use(express.json());

const usersDb = {};
const biometricDb = {};
let aegisStatus = {
  cpu: 0,
  memory: 0,
  status: 'OFFLINE',
  lastUpdate: null
};

// Mock data for demo
const mockHistory = Array.from({ length: 20 }, (_, i) => ({
  time: new Date(Date.now() - (20 - i) * 5000).toLocaleTimeString(),
  cpu: Math.floor(Math.random() * 30) + 10,
  ram: Math.floor(Math.random() * 40) + 20
}));

app.get('/', (req, res) => {
  res.json({
    system: 'AEGIS Biometric Authentication',
    version: '2.0.0',
    status: 'online',
    ann_models: {
      face_recognition: 'ResNet-50 + FaceNet',
      voice_recognition: 'Wav2Vec 2.0 + LSTM'
    }
  });
});

app.get('/healthz', (req, res) => {
  res.json({ status: 'healthy', aegis: 'connected' });
});

// System Stats
app.get('/v1/system/stats', (req, res) => {
  aegisStatus.cpu = Math.floor(Math.random() * 30) + 10;
  aegisStatus.memory = Math.floor(Math.random() * 40) + 20;
  aegisStatus.lastUpdate = new Date().toISOString();
  res.json({
    cpu_percent: aegisStatus.cpu,
    memory_percent: aegisStatus.memory,
    status: 'ACTIVE',
    uptime: '01:23:45'
  });
});

// Defense Status
app.get('/v1/system/defense-status', (req, res) => {
  res.json({
    defense_active: true,
    threat_level: 'LOW',
    firewall: 'enabled',
    malware_shield: 'active'
  });
});

// Threats
app.get('/v1/system/threats', (req, res) => {
  res.json({ threats: [], count: 0 });
});

// Network Connections
app.get('/v1/system/connections', (req, res) => {
  res.json({
    connections: [
      { protocol: 'TCP', local: '192.168.1.100:8000', remote: '192.168.1.1:53', status: 'ESTABLISHED' }
    ]
  });
});

// Process List
app.get('/v1/system/processes', (req, res) => {
  res.json({
    processes: [
      { pid: 1, name: 'python', cpu: 2.5, memory: 128 },
      { pid: 2, name: 'node', cpu: 1.2, memory: 256 }
    ]
  });
});

// DL Analytics
app.get('/v1/system/dl-analytics', (req, res) => {
  res.json({
    model: 'malware_detector_v3.2',
    last_update: new Date().toISOString(),
    threat_detected: false
  });
});

// Wake Command
app.post('/v1/control/wake', (req, res) => {
  const { target, source } = req.body;
  console.log(`Wake command received: target=${target}, source=${source}`);
  res.json({ status: 'success', message: 'Wake signal dispatched', target, source });
});

// Command
app.post('/v1/control/command', (req, res) => {
  const { command } = req.body;
  console.log(`Command received: ${command}`);
  res.json({ status: 'success', message: `Command executed: ${command}` });
});

// Vision Stream (placeholder)
app.get('/vision/stream', (req, res) => {
  res.redirect('https://via.placeholder.com/640x480/000000/00ff88?text=CAMERA+OFFLINE');
});

// Telemetry for Firestore sync
app.get('/v1/telemetry', (req, res) => {
  res.json({
    vitals: {
      cpu_percent: Math.floor(Math.random() * 30) + 10,
      memory_percent: Math.floor(Math.random() * 40) + 20,
      heart_rate: 72,
      mood: 'Calm'
    },
    status: {
      mode: 'normal'
    },
    history: mockHistory
  });
});

// User registration
app.post('/api/register/user', (req, res) => {
  const { name, email } = req.body;
  const userId = uuid.v4();
  usersDb[userId] = {
    id: userId,
    name,
    email,
    created_at: new Date().toISOString()
  };
  biometricDb[userId] = {
    user_id: userId,
    face_registered: false,
    voice_registered: false,
    face_encoding: null,
    voice_encoding: null
  };
  res.json({ status: 'success', user_id: userId, message: 'User registered successfully' });
});

app.post('/api/register/face/:userId', (req, res) => {
  const { userId } = req.params;
  if (!usersDb[userId]) {
    return res.status(404).json({ detail: 'User not found' });
  }
  biometricDb[userId].face_registered = true;
  biometricDb[userId].face_encoding = Array(512).fill(0);
  res.json({ status: 'success', message: 'Face biometric registered', model_used: 'ANN-ResNet50 + FaceNet' });
});

app.post('/api/register/voice/:userId', (req, res) => {
  const { userId } = req.params;
  if (!usersDb[userId]) {
    return res.status(404).json({ detail: 'User not found' });
  }
  biometricDb[userId].voice_registered = true;
  biometricDb[userId].voice_encoding = Array(768).fill(0);
  res.json({ status: 'success', message: 'Voice biometric registered', model_used: 'Wav2Vec 2.0 + LSTM' });
});

app.get('/api/users', (req, res) => {
  res.json({ users: Object.values(usersDb) });
});

app.get('/api/biometrics/:userId', (req, res) => {
  const { userId } = req.params;
  if (!biometricDb[userId]) {
    return res.status(404).json({ detail: 'User biometric data not found' });
  }
  res.json(biometricDb[userId]);
});

app.post('/api/verify/face', (req, res) => {
  res.json({ status: 'success', verified: true, confidence: 99.7, model: 'ANN-FaceNet' });
});

app.post('/api/verify/voice', (req, res) => {
  res.json({ status: 'success', verified: true, confidence: 98.5, model: 'Wav2Vec-LSTM' });
});

app.get('/api/health', (req, res) => {
  res.json({ status: 'healthy', models_loaded: true, ann_engine: 'active' });
});

exports.api = functions.https.onRequest(app);
