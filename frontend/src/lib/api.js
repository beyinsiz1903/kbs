import axios from 'axios';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000
});

// Auth interceptor - token is set dynamically from AuthContext
// Response interceptor for 401
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // Token expired or invalid - clear auth
      const currentPath = window.location.pathname;
      if (currentPath !== '/login' && currentPath !== '/') {
        localStorage.removeItem('kbs_token');
        localStorage.removeItem('kbs_user');
        // Don't redirect here - let AuthContext handle it
      }
    }
    return Promise.reject(error);
  }
);

// ============= AUTH =============
export const loginUser = (data) => api.post('/auth/login', data).then(r => r.data);
export const getMe = () => api.get('/auth/me').then(r => r.data);
export const changePassword = (data) => api.post('/auth/change-password', data).then(r => r.data);

// ============= USERS =============
export const getUsers = () => api.get('/users').then(r => r.data);
export const createUser = (data) => api.post('/users', data).then(r => r.data);
export const updateUser = (id, data) => api.put(`/users/${id}`, data).then(r => r.data);

// ============= HOTELS =============
export const getHotels = () => api.get('/hotels').then(r => r.data);
export const createHotel = (data) => api.post('/hotels', data).then(r => r.data);
export const getHotel = (id) => api.get(`/hotels/${id}`).then(r => r.data);
export const updateHotelOnboarding = (id, data) => api.put(`/hotels/${id}/onboarding`, data).then(r => r.data);
export const testHotelIntegration = (id) => api.post(`/hotels/${id}/integration/test`).then(r => r.data);

// ============= KBS CONFIG / CREDENTIAL VAULT =============
export const getKbsConfig = (hotelId) => api.get(`/hotels/${hotelId}/kbs-config`).then(r => r.data);
export const updateKbsConfig = (hotelId, data) => api.put(`/hotels/${hotelId}/kbs-config`, data).then(r => r.data);

// ============= HOTEL HEALTH =============
export const getHotelHealth = (hotelId) => api.get(`/hotels/${hotelId}/health`).then(r => r.data);

// ============= GUESTS =============
export const createGuest = (data) => api.post('/guests', data).then(r => r.data);
export const getGuests = (hotelId) => api.get('/guests', { params: { hotel_id: hotelId } }).then(r => r.data);

// ============= CHECK-INS =============
export const createCheckIn = (data) => api.post('/checkins', data).then(r => r.data);
export const getCheckIns = (hotelId) => api.get('/checkins', { params: { hotel_id: hotelId } }).then(r => r.data);

// ============= SUBMISSIONS =============
export const getSubmissions = (params) => api.get('/submissions', { params }).then(r => r.data);
export const getSubmission = (id) => api.get(`/submissions/${id}`).then(r => r.data);
export const requeueSubmission = (id) => api.post(`/submissions/${id}/requeue`).then(r => r.data);
export const correctSubmission = (id, data) => api.post(`/submissions/${id}/correct`, data).then(r => r.data);

// ============= AGENTS =============
export const getAgents = () => api.get('/agents').then(r => r.data);
export const getAgentStatus = (hotelId) => api.get(`/agents/${hotelId}`).then(r => r.data);
export const toggleAgent = (hotelId, online) => api.post(`/agents/${hotelId}/toggle`, null, { params: { online } }).then(r => r.data);
export const startAgent = (hotelId) => api.post(`/agents/${hotelId}/start`).then(r => r.data);
export const stopAgent = (hotelId) => api.post(`/agents/${hotelId}/stop`).then(r => r.data);

// ============= KBS SIMULATION =============
export const getKBSSimulation = () => api.get('/kbs/simulation').then(r => r.data);
export const setKBSSimulation = (data) => api.post('/kbs/simulation', data).then(r => r.data);
export const resetKBSSimulation = () => api.post('/kbs/simulation/reset').then(r => r.data);

// ============= AUDIT =============
export const getAuditEvents = (params) => api.get('/audit', { params }).then(r => r.data);
export const getAuditStats = (hotelId) => api.get('/audit/stats', { params: { hotel_id: hotelId } }).then(r => r.data);

// ============= METRICS =============
export const getMetrics = (hotelId) => api.get('/metrics', { params: { hotel_id: hotelId } }).then(r => r.data);

// ============= HEALTH =============
export const getHealth = () => api.get('/health').then(r => r.data);

// ============= RESET =============
export const resetDemo = () => api.post('/reset-demo').then(r => r.data);

export default api;
