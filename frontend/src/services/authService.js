import { API_BASE_URL } from './apiConfig';

const API_URL = `${API_BASE_URL}/api/auth`;

export const authService = {
  async register(userData) {
    const response = await fetch(`${API_URL}/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(userData),
    });
    if (!response.ok) throw await response.json();
    return response.json();
  },

  async login(username, password) {
    const response = await fetch(`${API_URL}/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) throw await response.json();
    const data = await response.json();
    localStorage.setItem('access_token', data.access);
    localStorage.setItem('refresh_token', data.refresh);
    localStorage.setItem('user', JSON.stringify({ username: data.username, email: data.email, role: data.role }));
    return data;
  },

  async getProfile() {
    const token = localStorage.getItem('access_token');
    const response = await fetch(`${API_URL}/profile/`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (!response.ok) throw await response.json();
    return response.json();
  },

  async refreshToken() {
    const refresh = localStorage.getItem('refresh_token');
    const response = await fetch(`${API_URL}/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    });
    if (!response.ok) throw await response.json();
    const data = await response.json();
    localStorage.setItem('access_token', data.access);
    return data;
  },

  logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  },

  getUser() {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
  },

  isAuthenticated() {
    return !!localStorage.getItem('access_token');
  },
};
