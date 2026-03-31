import { useState, useEffect } from 'react';
import { assignUser } from '../api/hosts';
import { getUsers } from '../api/auth';
import '../index.css';

export default function AssignHostModal({ host, onClose, onAssigned }) {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({
    user_id: '',
    role: 'VIEWER'
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [fetchingUsers, setFetchingUsers] = useState(true);

  useEffect(() => {
    async function loadUsers() {
      try {
        const res = await getUsers();
        setUsers(res.data);
        if (res.data.length > 0) {
          setForm(prev => ({ ...prev, user_id: res.data[0].id }));
        }
      } catch (err) {
        console.error("Failed to load users", err);
        setError("Could not load users list.");
      } finally {
        setFetchingUsers(false);
      }
    }
    loadUsers();
  }, []);

  const handleChange = (e) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.user_id) {
      setError('Please select a user.');
      return;
    }
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const res = await assignUser(host.id, form);
      setSuccess('User successfully assigned!');
      if (onAssigned) onAssigned(res.data);
      setTimeout(() => onClose(), 1500);
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.error || 'Failed to assign user. Please check User ID.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2 className="modal-title">Assign User to Host</h2>
        <p className="modal-subtitle">Grant a user access to {host.alias}.</p>

        {error && <p className="form-error">{error}</p>}
        {success && <p className="form-error" style={{ background: '#dcfce7', color: '#166534', borderColor: '#bbf7d0' }}>{success}</p>}

        {fetchingUsers ? (
          <p className="loading-text">Loading users...</p>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">User</label>
              <select
                className="form-input"
                name="user_id"
                value={form.user_id}
                onChange={handleChange}
                required
              >
                {users.map(u => (
                  <option key={u.id} value={u.id}>
                    {u.username} ({u.email})
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Role</label>
              <select
                className="form-input"
                name="role"
                value={form.role}
                onChange={handleChange}
              >
              <option value="VIEWER">Viewer (Read-only)</option>
              <option value="HOST_OWNER">Host Owner (Manage Containers)</option>
              <option value="ADMIN">Admin (Full Access)</option>
            </select>
          </div>
          
          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>
              Close
            </button>
            <button type="submit" className="btn-primary" disabled={loading || success}>
              {loading ? 'Assigning...' : 'Assign User'}
            </button>
          </div>
        </form>
        )}
      </div>
    </div>
  );
}
