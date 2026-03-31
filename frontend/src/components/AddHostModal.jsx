import { useState } from 'react';
import { createHost } from '../api/hosts';
import '../index.css';

export default function AddHostModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    alias: '',
    ip_address: '',
    port: 2375,
    ssh_credentials: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: name === 'port' ? Number(value) : value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await createHost(form);
      onCreated(res.data);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to register host. Please check details.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2 className="modal-title">Register New Host</h2>
        <p className="modal-subtitle">Add a new Docker engine instance to the platform.</p>

        {error && <p className="form-error">{error}</p>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Alias</label>
            <input
              className="form-input"
              name="alias"
              placeholder="E.g. Production Server"
              value={form.alias}
              onChange={handleChange}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">IP Address</label>
            <input
              className="form-input"
              name="ip_address"
              placeholder="192.168.1.10"
              value={form.ip_address}
              onChange={handleChange}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Port</label>
            <input
              className="form-input"
              name="port"
              type="number"
              value={form.port}
              onChange={handleChange}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">SSH Credentials</label>
            <textarea
              className="form-textarea"
              name="ssh_credentials"
              placeholder="Paste SSH private key or password..."
              value={form.ssh_credentials}
              onChange={handleChange}
              rows={4}
              required
            />
          </div>
          
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? 'Registering...' : 'Register Host'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
