import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
    // Custom header forces CORS preflight on every request, blocking
    // cross-origin attacks against the loopback API.
    'X-KBS-Client': 'kbs-bridge',
  },
  timeout: 60000,
});

let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401 && onUnauthorized) {
      onUnauthorized();
    }
    return Promise.reject(err);
  }
);

export function errorMessage(err) {
  if (!err) return 'Bilinmeyen hata';
  if (err.response?.data?.detail) return err.response.data.detail;
  if (err.message?.includes('Network')) return "PMS'e veya sunucuya ulasilamiyor";
  return err.message || 'Bilinmeyen hata';
}

// ----- Auth & settings -----
export const getSettings = () => api.get('/settings').then((r) => r.data);
export const saveSettings = (data) => api.post('/settings', data).then((r) => r.data);
export const login = (data) => api.post('/auth/login', data).then((r) => r.data);
export const me = () => api.get('/auth/me').then((r) => r.data);
export const logout = () => api.post('/auth/logout').then((r) => r.data);

// ----- Worker -----
export const getWorkerStatus = () => api.get('/worker/status').then((r) => r.data);
export const triggerWorkerPoll = () => api.post('/worker/poll-now').then((r) => r.data);

export default api;
