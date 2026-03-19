import axios from 'axios';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000
});

// Hotels
export const getHotels = () => api.get('/hotels').then(r => r.data);
export const createHotel = (data) => api.post('/hotels', data).then(r => r.data);
export const getHotel = (id) => api.get(`/hotels/${id}`).then(r => r.data);

// Guests
export const createGuest = (data) => api.post('/guests', data).then(r => r.data);
export const getGuests = (hotelId) => api.get('/guests', { params: { hotel_id: hotelId } }).then(r => r.data);

// Check-ins
export const createCheckIn = (data) => api.post('/checkins', data).then(r => r.data);
export const getCheckIns = (hotelId) => api.get('/checkins', { params: { hotel_id: hotelId } }).then(r => r.data);

// Submissions
export const getSubmissions = (params) => api.get('/submissions', { params }).then(r => r.data);
export const getSubmission = (id) => api.get(`/submissions/${id}`).then(r => r.data);
export const requeueSubmission = (id) => api.post(`/submissions/${id}/requeue`).then(r => r.data);
export const correctSubmission = (id, data) => api.post(`/submissions/${id}/correct`, data).then(r => r.data);

// Agents
export const getAgents = () => api.get('/agents').then(r => r.data);
export const getAgentStatus = (hotelId) => api.get(`/agents/${hotelId}`).then(r => r.data);
export const toggleAgent = (hotelId, online) => api.post(`/agents/${hotelId}/toggle`, null, { params: { online } }).then(r => r.data);
export const startAgent = (hotelId) => api.post(`/agents/${hotelId}/start`).then(r => r.data);
export const stopAgent = (hotelId) => api.post(`/agents/${hotelId}/stop`).then(r => r.data);

// KBS Simulation
export const getKBSSimulation = () => api.get('/kbs/simulation').then(r => r.data);
export const setKBSSimulation = (data) => api.post('/kbs/simulation', data).then(r => r.data);
export const resetKBSSimulation = () => api.post('/kbs/simulation/reset').then(r => r.data);

// Audit
export const getAuditEvents = (params) => api.get('/audit', { params }).then(r => r.data);
export const getAuditStats = (hotelId) => api.get('/audit/stats', { params: { hotel_id: hotelId } }).then(r => r.data);

// Metrics
export const getMetrics = (hotelId) => api.get('/metrics', { params: { hotel_id: hotelId } }).then(r => r.data);

// Health
export const getHealth = () => api.get('/health').then(r => r.data);

// Reset Demo
export const resetDemo = () => api.post('/reset-demo').then(r => r.data);

export default api;
