const API_BASE_URL = import.meta.env.VITE_AEGIS_GATEWAY_URL || import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiService {
  constructor() {
    this.baseUrl = API_BASE_URL;
  }

  getToken() {
    return localStorage.getItem('aegis_token');
  }

  async request(endpoint, options = {}) {
    const token = this.getToken();
    
    const headers = {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
      ...options.headers
    };

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async getSystemStats() {
    return this.request('/v1/system/stats');
  }

  async getDefenseStatus() {
    return this.request('/v1/system/defense-status');
  }

  async getThreats() {
    return this.request('/v1/system/threats');
  }

  async getNetworkConnections() {
    return this.request('/v1/system/connections');
  }

  async getProcessList() {
    return this.request('/v1/system/processes');
  }

  async getDLDefenseAnalytics() {
    return this.request('/v1/system/dl-analytics');
  }

  async runAntivirusScan() {
    return this.request('/v1/antivirus/scan', { method: 'POST' });
  }

  async wakeAegis(target = 'saturday') {
    return this.request('/v1/control/wake', {
      method: 'POST',
      body: JSON.stringify({ target, source: 'web_dashboard' })
    });
  }

  async healthCheck() {
    return this.request('/healthz');
  }
}

export const apiService = new ApiService();
export default apiService;
