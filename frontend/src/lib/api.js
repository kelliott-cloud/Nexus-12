import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
// NXS-006: Use relative /api path to hide internal hostname, fall back to env var for dev
const API = (typeof window !== 'undefined' && window.location.hostname !== 'localhost')
  ? '/api'
  : `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API,
  withCredentials: true,  // N7-016: Send httpOnly cookies automatically
  timeout: 30000,
});

function getCsrfToken() {
  return document.cookie.split('; ').find(c => c.startsWith('csrf_token='))?.split('=')[1] || '';
}

// Request interceptor: CSRF token on mutations
// Session token from sessionStorage is ONLY used during Emergent bridge handoff,
// then cleared once httpOnly cookie is established (N7R-004)
api.interceptors.request.use((config) => {
  if (['post', 'put', 'delete', 'patch'].includes(config.method)) {
    config.headers['X-CSRF-Token'] = getCsrfToken();
  }
  // Bridge handoff: use token only if cookie auth hasn't been established yet
  const token = sessionStorage.getItem("nexus_session_token");
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;

});

// After first successful authenticated request, clear sessionStorage token
// (httpOnly cookie is now handling auth)
let _tokenCleared = false;
api.interceptors.response.use((response) => {
  if (!_tokenCleared && sessionStorage.getItem("nexus_session_token") && response.status === 200) {
    // First successful auth response — cookie is working, clear the JS-accessible token
    const url = response.config?.url || "";
    if (url.includes("/auth/me") || url.includes("/workspaces") || url.includes("/user/preferences")) {
      sessionStorage.removeItem("nexus_session_token");
      _tokenCleared = true;
    }
  }
  return response;
});

// Prevent multiple simultaneous 401 redirects
let isRedirecting = false;

// Grace period after login — don't redirect on 401 for 20 seconds after auth
let lastAuthTime = 0;
export function markRecentAuth() {
  lastAuthTime = Date.now();
}

// Response interceptor for better error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Don't redirect if:
      // 1. Already redirecting
      // 2. On auth page or landing
      // 3. Processing OAuth callback
      // 4. Within 20 seconds of a fresh login (grace period for cookie propagation)
      // 5. Session was just set (nexus_user exists in sessionStorage)
      const withinGracePeriod = (Date.now() - lastAuthTime) < 20000;
      const hasStoredUser = !!sessionStorage.getItem("nexus_user");
      if (
        !isRedirecting &&
        !withinGracePeriod &&
        !hasStoredUser &&
        window.location.pathname !== '/auth' &&
        window.location.pathname !== '/' &&
        !window.location.pathname.startsWith('/replay') &&
        !window.location.hash?.includes('session_id=')
      ) {
        isRedirecting = true;
        sessionStorage.removeItem("nexus_user");
        sessionStorage.removeItem("nexus_session_token");
        console.warn("Auth expired — redirecting to login");
        setTimeout(() => {
          window.location.href = '/auth';
        }, 100);
      }
    }
    return Promise.reject(error);
  }
);

export { api, API, BACKEND_URL };
