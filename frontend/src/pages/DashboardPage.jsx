import { useEffect, useState } from 'react';
import { getMe } from '../api/auth';
import { getHosts } from '../api/hosts';
import AddHostModal from '../components/AddHostModal';
import AssignHostModal from '../components/AssignHostModal';
import '../index.css';

/* ── Helper: initials from username ── */
function initials(username) {
  return username ? username.slice(0, 2).toUpperCase() : '??';
}

/* ── Helper: status dot class (you can wire this to a real ping later) ── */
function statusClass(host) {
  // Placeholder — Module 2 will add real status
  return 'status-online';
}

/* ── HostCard ── */
function HostCard({ host }) {
  const roleClass = {
    ADMIN: 'badge-admin',
    HOST_OWNER: 'badge-owner',
    VIEWER: 'badge-viewer',
  }[host.role] || 'badge-viewer';

  const roleLabel = {
    ADMIN: 'Admin',
    HOST_OWNER: 'Host owner',
    VIEWER: 'Viewer',
  }[host.role] || host.role;

  return (
    <div className="host-card">
      <div className="host-card-top">
        <div className="host-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="2" y="3" width="20" height="14" rx="2" />
            <path d="M8 21h8M12 17v4" />
          </svg>
        </div>
        <div className={`status-dot ${statusClass(host)}`} />
      </div>
      <div className="host-name">{host.alias}</div>
      <div className="host-addr">
        {host.ip_address}:{host.port}
      </div>
      <span className={`host-role-badge ${roleClass}`}>{roleLabel}</span>
    </div>
  );
}

/* ── Dashboard ── */
export default function DashboardPage() {
    const [user, setUser] = useState(null);
    const [hosts, setHosts] = useState([]);
    const [selectedHostId, setSelectedHostId] = useState(null);
    const [showAddModal, setShowAddModal] = useState(false);
    const [assignHost, setAssignHost] = useState(null);
    const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [meRes, hostsRes] = await Promise.all([getMe(), getHosts()]);
        setUser(meRes.data);
        setHosts(hostsRes.data);
      } catch (err) {
        console.error('Failed to load dashboard:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleLogout = () => {
    localStorage.clear();
    window.location.href = '/login';
  };

  const isAdmin = user?.role?.toUpperCase() === 'ADMIN' || user?.is_superuser;

return (
  <div className="dashboard-page">
    <div className="dashboard-inner">

      {/* Top nav */}
      <div className="dash-header">
        <div className="dash-logo">
          <div className="dash-logo-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
              <rect x="2" y="2" width="20" height="20" rx="3" />
              <path d="M8 12h8M12 8v8" />
            </svg>
          </div>
          <span className="dash-logo-name">DockerIntegrationHost</span>
        </div>

        {/* User Info */}
        {user && (
          <div className="dash-user">
            <div className="user-info">
              <div className="user-name">{user.username}</div>
              <div className="user-role">{user.role || 'user'}</div>
            </div>
            <div className="avatar">{initials(user.username)}</div>
            <button className="btn-logout" onClick={handleLogout}>
              Sign out
            </button>
          </div>
        )}
      </div>

      {/* Section Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <p className="section-label" style={{ margin: 0 }}>Your hosts</p>

        {/* ADMIN: Register Host */}
        {user && (user?.role?.toUpperCase() === 'ADMIN' || user?.is_superuser) && (
          <button 
            className="btn-primary" 
            style={{ width: 'auto', marginTop: 0, padding: '6px 14px', fontSize: '13px' }}
            onClick={() => setShowAddModal(true)}
          >
            + Register New Host
          </button>
        )}
      </div>

      {/* Host list */}
      {loading ? (
        <p className="loading-text">Loading hosts…</p>
      ) : hosts.length === 0 ? (
        <div className="empty-state">
          <p className="empty-title">No hosts assigned</p>
          <p className="empty-sub">Ask an admin to assign you to a host.</p>
        </div>
      ) : (
        <div className="host-grid">
          {hosts.map((host) => (
            <div
              key={host.id}
              className={`card-wrapper ${selectedHostId === host.id ? 'active' : ''}`}
              onClick={() => setSelectedHostId(host.id)}
            >
              <HostCard host={host} />
              
              {/* Admin actions or viewer message */}
              <div style={{ marginTop: '10px', display: 'flex', gap: '8px' }}>
                {(host.role === 'ADMIN' || user?.is_superuser) ? (
                  <button 
                    className="btn-secondary" 
                    style={{ padding: '6px 10px', fontSize: '11px', flex: 1 }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setAssignHost(host);
                    }}
                  >
                    Assign User
                  </button>
                ) : (
                  <span style={{ fontSize: '11px', color: '#888', fontStyle: 'italic', padding: '6px 0' }}>
                    Cannot add roles for docker hosts
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Host Modal */}
      {showAddModal && (
        <AddHostModal
          onClose={() => setShowAddModal(false)}
          onCreated={(newHost) => setHosts([...hosts, newHost])}
        />
      )}

      {/* Assign Host Modal */}
      {assignHost && (
        <AssignHostModal
          host={assignHost}
          onClose={() => setAssignHost(null)}
          onAssigned={() => {}} // Additional UI updates on success
        />
      )}

    </div>
  </div>
);
}