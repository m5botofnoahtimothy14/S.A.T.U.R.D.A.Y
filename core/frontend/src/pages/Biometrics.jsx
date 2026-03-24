import { useState } from 'react';
import { Fingerprint, Camera, Mic, User, Shield, CheckCircle, AlertCircle } from 'lucide-react';
import './Biometrics.css';

const Biometrics = () => {
  const [faceStatus, setFaceStatus] = useState('idle');
  const [voiceStatus, setVoiceStatus] = useState('idle');
  const [registeredUsers, setRegisteredUsers] = useState([
    { id: 1, name: 'Admin', face: true, voice: true, lastAuth: '2 min ago' },
    { id: 2, name: 'Security Officer', face: true, voice: false, lastAuth: '1 hour ago' },
  ]);

  const handleFaceCapture = () => {
    setFaceStatus('capturing');
    setTimeout(() => {
      setFaceStatus('success');
      setTimeout(() => setFaceStatus('idle'), 2000);
    }, 2000);
  };

  const handleVoiceCapture = () => {
    setVoiceStatus('recording');
    setTimeout(() => {
      setVoiceStatus('success');
      setTimeout(() => setVoiceStatus('idle'), 2000);
    }, 3000);
  };

  return (
    <div className="biometrics">
      <header className="page-header">
        <h1>Biometric Authentication</h1>
        <p className="subtitle">Face & Voice Registration System</p>
      </header>

      <div className="bio-grid">
        <div className="capture-card">
          <div className="card-header">
            <Camera size={24} />
            <h2>Face Recognition</h2>
          </div>
          <div className="capture-area">
            <div className={`camera-preview ${faceStatus}`}>
              {faceStatus === 'idle' && <div className="placeholder">Click to Capture</div>}
              {faceStatus === 'capturing' && <div className="scanning">Scanning...</div>}
              {faceStatus === 'success' && <CheckCircle size={48} className="success-icon" />}
            </div>
          </div>
          <button 
            className={`capture-btn ${faceStatus}`}
            onClick={handleFaceCapture}
            disabled={faceStatus !== 'idle'}
          >
            {faceStatus === 'idle' ? 'Capture Face' : 
             faceStatus === 'capturing' ? 'Processing...' : 'Captured!'}
          </button>
          <div className="model-info">
            <Shield size={14} />
            <span>ANN Model: ResNet-50 + FaceNet</span>
          </div>
        </div>

        <div className="capture-card">
          <div className="card-header">
            <Mic size={24} />
            <h2>Voice Recognition</h2>
          </div>
          <div className="capture-area">
            <div className={`audio-preview ${voiceStatus}`}>
              {voiceStatus === 'idle' && <div className="placeholder">Click to Record</div>}
              {voiceStatus === 'recording' && (
                <div className="waveform">
                  <div className="bar"></div>
                  <div className="bar"></div>
                  <div className="bar"></div>
                  <div className="bar"></div>
                  <div className="bar"></div>
                </div>
              )}
              {voiceStatus === 'success' && <CheckCircle size={48} className="success-icon" />}
            </div>
          </div>
          <button 
            className={`capture-btn ${voiceStatus}`}
            onClick={handleVoiceCapture}
            disabled={voiceStatus !== 'idle'}
          >
            {voiceStatus === 'idle' ? 'Record Voice' : 
             voiceStatus === 'recording' ? 'Recording...' : 'Recorded!'}
          </button>
          <div className="model-info">
            <Shield size={14} />
            <span>DL Model: Wav2Vec 2.0 + LSTM</span>
          </div>
        </div>

        <div className="users-card">
          <div className="card-header">
            <User size={24} />
            <h2>Registered Users</h2>
          </div>
          <div className="users-list">
            {registeredUsers.map(user => (
              <div key={user.id} className="user-item">
                <div className="user-info">
                  <span className="user-name">{user.name}</span>
                  <span className="user-auth">Auth: {user.lastAuth}</span>
                </div>
                <div className="auth-badges">
                  <span className={`badge ${user.face ? 'active' : 'inactive'}`}>
                    <Fingerprint size={12} /> Face
                  </span>
                  <span className={`badge ${user.voice ? 'active' : 'inactive'}`}>
                    <Mic size={12} /> Voice
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Biometrics;
