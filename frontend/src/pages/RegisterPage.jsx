import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { register } from '../api/auth';
import '../index.css';

const Logo = () => (
  <div className="auth-logo">
    <div className="auth-logo-icon">
      <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
        <rect x="2" y="2" width="20" height="20" rx="3" />
        <path d="M8 12h8M12 8v8" />
      </svg>
    </div>
    <span className="auth-logo-text">DockerIntegrationHost</span>
  </div>
);

export default function RegisterPage() {
  const [form, setForm] = useState({
    username: '', email: '', password: '', password_confirm: '', role: 'admin',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (form.password !== form.password_confirm) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const payload = {
        username: form.username,
        email: form.email,
        password: form.password,
        role: form.role,
      };
      await register(payload);
      navigate('/login');
    } catch (err) {
      const data = err.response?.data;
      if (typeof data === 'string') {
        setError(data);
      } else if (data?.detail) {
        setError(data.detail);
      } else if (data && typeof data === 'object') {
        const first = Object.values(data).flat()[0];
        setError(first || 'Registration failed. Please try again.');
      } else {
        setError('Registration failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <Logo />
        <p className="auth-title">Create account</p>
        <p className="auth-subtitle">Get started with DockerPanel</p>

        {error && <p className="form-error">{error}</p>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              className="form-input"
              name="username"
              placeholder="john_doe"
              value={form.username}
              onChange={handleChange}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Email</label>
            <input
              className="form-input"
              name="email"
              type="email"
              placeholder="john@example.com"
              value={form.email}
              onChange={handleChange}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              className="form-input"
              name="password"
              type="password"
              placeholder="••••••••"
              value={form.password}
              onChange={handleChange}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Confirm password</label>
            <input
              className="form-input"
              name="password_confirm"
              type="password"
              placeholder="••••••••"
              value={form.password_confirm}
              onChange={handleChange}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Role</label>
            <select
              className="form-input"
              name="role"
              value={form.role}
              onChange={handleChange}
            >
              <option value="admin">Admin</option>
              <option value="host">Host owner</option>
              <option value="viewer">Viewer</option>
            </select>
          </div>
          <button className="btn-primary" type="submit" disabled={loading}>
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}