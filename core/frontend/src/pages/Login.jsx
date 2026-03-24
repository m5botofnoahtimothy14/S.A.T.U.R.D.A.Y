import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, AlertTriangle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './Auth.css';

const Login = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleGoogleLogin = async () => {
    setError('');
    setLoading(true);

    const result = await login();

    if (result.success) {
      navigate('/dashboard');
    } else {
      setError(result.error);
    }

    setLoading(false);
  };

  return (
    <div className="login-container">
      <div className="login-background">
        <div className="grid-overlay"></div>
        <div className="scan-line"></div>
      </div>

      <div className="login-card">
        <div className="login-header">
          <div className="logo-container">
            <Shield className="shield-icon" size={48} />
            <div className="shield-pulse"></div>
          </div>
          <h1>AEGIS</h1>
          <p className="login-subtitle">Advanced Defense System</p>
        </div>

        <div className="login-form">
          <button 
            onClick={handleGoogleLogin} 
            className="login-button google-login" 
            disabled={loading}
          >
            {loading ? (
              <span className="loading-spinner"></span>
            ) : (
              <>
                <img 
                  src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" 
                  alt="Google" 
                  style={{ width: 18, height: 18 }}
                />
                Sign in with Google
              </>
            )}
          </button>

          {error && (
            <div className="error-message">
              <AlertTriangle size={16} />
              {error}
            </div>
          )}
        </div>

        <div className="login-footer">
          <div className="security-badge">
            <Shield size={14} />
            <span>Google OAuth 2.0</span>
          </div>
        </div>
      </div>

      <div className="system-status">
        <div className="status-item">
          <span className="status-dot online"></span>
          <span>System Online</span>
        </div>
        <div className="status-item">
          <span className="status-dot secure"></span>
          <span>Neural Network Active</span>
        </div>
      </div>
    </div>
  );
};

export default Login;
