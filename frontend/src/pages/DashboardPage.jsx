import { useEffect, useRef, useState } from 'react';
import { getMe } from '../api/auth';
import { createHost, getHosts } from '../api/hosts';
import { containerService } from '../services/containerService';
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
    const [emptyStateError, setEmptyStateError] = useState('');
    const [creatingLocalHost, setCreatingLocalHost] = useState(false);
    const [containerHostId, setContainerHostId] = useState('1');
    const [containers, setContainers] = useState([]);
    const [containersLoading, setContainersLoading] = useState(false);
    const [containerError, setContainerError] = useState('');
    const [bootstrapLoading, setBootstrapLoading] = useState(false);
    const [statusFilter, setStatusFilter] = useState('');
    const [createImageRef, setCreateImageRef] = useState('nginx:alpine');
    const [createName, setCreateName] = useState('');
    const [openPanels, setOpenPanels] = useState({});
    const [statsByContainer, setStatsByContainer] = useState({});
    const [logsByContainer, setLogsByContainer] = useState({});
    const [terminalInputByContainer, setTerminalInputByContainer] = useState({});
    const [terminalLinesByContainer, setTerminalLinesByContainer] = useState({});
    const [terminalConnectedByContainer, setTerminalConnectedByContainer] = useState({});
    const terminalSocketsRef = useRef({});

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
    Object.values(terminalSocketsRef.current).forEach((socket) => socket?.close());
    terminalSocketsRef.current = {};
    localStorage.clear();
    window.location.href = '/login';
  };

  useEffect(() => {
    return () => {
      Object.values(terminalSocketsRef.current).forEach((socket) => socket?.close());
      terminalSocketsRef.current = {};
    };
  }, []);

  useEffect(() => {
    const outputs = document.querySelectorAll('.terminal-output');
    outputs.forEach((node) => {
      node.scrollTop = node.scrollHeight;
    });
  }, [terminalLinesByContainer]);

  const createLocalHost = async () => {
    if (creatingLocalHost) return;
    setEmptyStateError('');
    setCreatingLocalHost(true);
    try {
      const response = await createHost({
        alias: 'Local Docker Host',
        ip_address: '127.0.0.1',
        port: 2375,
        ssh_credentials: '',
      });

      const host = response?.data;
      if (host) {
        setHosts((prev) => [...prev, host]);
        setSelectedHostId(host.id);
      }
    } catch (err) {
      const message = err?.response?.data?.detail || err?.response?.data?.error ||
        'Could not create a host. Register/login with Admin role.';
      setEmptyStateError(message);
    } finally {
      setCreatingLocalHost(false);
    }
  };

  const setupModule2LocalHost = async () => {
    if (bootstrapLoading) return;
    setContainerError('');
    setBootstrapLoading(true);
    try {
      const host = await containerService.bootstrapLocalHost();
      setContainerHostId(String(host.id));
      await loadContainers();
    } catch (err) {
      setContainerError(err.message);
    } finally {
      setBootstrapLoading(false);
    }
  };

  const loadContainers = async () => {
    setContainerError('');
    setContainersLoading(true);
    try {
      const data = await containerService.listContainers(containerHostId, statusFilter);
      setContainers(data.results || []);
    } catch (err) {
      setContainers([]);
      setContainerError(err.message);
    } finally {
      setContainersLoading(false);
    }
  };

  const handleCreateContainer = async () => {
    if (!createImageRef.trim()) {
      setContainerError('Image reference is required.');
      return;
    }

    setContainerError('');
    try {
      await containerService.createContainer(containerHostId, {
        image_ref: createImageRef.trim(),
        name: createName.trim() || `container-${Date.now()}`,
        command: '',
        environment: {},
        port_bindings: {},
        volumes: [],
      });
      setCreateName('');
      await loadContainers();
    } catch (err) {
      setContainerError(err.message);
    }
  };

  const handleContainerAction = async (containerId, action) => {
    setContainerError('');
    try {
      await containerService.action(containerHostId, containerId, action);
      await loadContainers();
    } catch (err) {
      setContainerError(err.message);
    }
  };

  const handleContainerRemove = async (containerId) => {
    setContainerError('');
    try {
      await containerService.remove(containerHostId, containerId);
      await loadContainers();
    } catch (err) {
      setContainerError(err.message);
    }
  };

  const openContainerPanel = (containerId, tab) => {
    setOpenPanels((prev) => ({
      ...prev,
      [containerId]: {
        open: true,
        tab,
      },
    }));
  };

  const closeContainerPanel = (containerId) => {
    setOpenPanels((prev) => ({
      ...prev,
      [containerId]: {
        ...(prev[containerId] || {}),
        open: false,
      },
    }));
  };

  const handleStats = async (containerId) => {
    setContainerError('');
    openContainerPanel(containerId, 'stats');
    try {
      const data = await containerService.getStats(containerHostId, containerId);
      setStatsByContainer((prev) => ({
        ...prev,
        [containerId]: data,
      }));
    } catch (err) {
      setContainerError(err.message);
    }
  };

  const handleLogs = async (containerId) => {
    setContainerError('');
    openContainerPanel(containerId, 'logs');
    try {
      const data = await containerService.getLogs(containerHostId, containerId, 200);
      setLogsByContainer((prev) => ({
        ...prev,
        [containerId]: data.logs || [],
      }));
    } catch (err) {
      setContainerError(err.message);
    }
  };

  const handleOpenTerminal = async (containerId, containerName) => {
    setContainerError('');
    openContainerPanel(containerId, 'terminal');

    const existingSocket = terminalSocketsRef.current[containerId];
    if (existingSocket && existingSocket.readyState === WebSocket.OPEN) {
      setTerminalLinesByContainer((prev) => ({
        ...prev,
        [containerId]: [...(prev[containerId] || []), '[terminal already connected]'],
      }));
      return;
    }

    if (existingSocket) {
      existingSocket.close();
    }

    try {
      const ticket = await containerService.getExecTicket(containerHostId, containerId);
      const ws = new WebSocket(ticket.ws_url);
      terminalSocketsRef.current[containerId] = ws;
      setTerminalLinesByContainer((prev) => ({
        ...prev,
        [containerId]: [
          ...(prev[containerId] || []),
          `[opening terminal for ${containerName || containerId}]`,
        ],
      }));
      setTerminalInputByContainer((prev) => ({
        ...prev,
        [containerId]: prev[containerId] || 'echo hello from module2',
      }));

      ws.onopen = () => {
        setTerminalConnectedByContainer((prev) => ({
          ...prev,
          [containerId]: true,
        }));
        setTerminalLinesByContainer((prev) => ({
          ...prev,
          [containerId]: [...(prev[containerId] || []), '[terminal connected]'],
        }));
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const line = payload?.data || event.data;
          setTerminalLinesByContainer((prev) => ({
            ...prev,
            [containerId]: [...(prev[containerId] || []), line],
          }));
        } catch {
          setTerminalLinesByContainer((prev) => ({
            ...prev,
            [containerId]: [...(prev[containerId] || []), event.data],
          }));
        }
      };

      ws.onerror = () => {
        setContainerError('Terminal websocket failed.');
      };

      ws.onclose = () => {
        setTerminalConnectedByContainer((prev) => ({
          ...prev,
          [containerId]: false,
        }));
        delete terminalSocketsRef.current[containerId];
        setTerminalLinesByContainer((prev) => ({
          ...prev,
          [containerId]: [...(prev[containerId] || []), '[terminal disconnected]'],
        }));
      };
    } catch (err) {
      setContainerError(err.message);
    }
  };

  const handleCloseTerminal = (containerId) => {
    const socket = terminalSocketsRef.current[containerId];
    if (socket) {
      socket.close();
      delete terminalSocketsRef.current[containerId];
    }

    setTerminalConnectedByContainer((prev) => ({
      ...prev,
      [containerId]: false,
    }));
    setTerminalLinesByContainer((prev) => ({
      ...prev,
      [containerId]: [...(prev[containerId] || []), '[terminal closed by user]'],
    }));
  };

  const handleTerminalRun = (containerId) => {
    const command = terminalInputByContainer[containerId] || '';
    if (!command.trim()) return;

    const socket = terminalSocketsRef.current[containerId];

    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setContainerError('Open terminal first.');
      return;
    }

    socket.send(JSON.stringify({ type: 'input', data: command }));
    setTerminalLinesByContainer((prev) => ({
      ...prev,
      [containerId]: [...(prev[containerId] || []), `$ ${command}`],
    }));
    setTerminalInputByContainer((prev) => ({
      ...prev,
      [containerId]: '',
    }));
  };

  const handleTerminalKeyDown = (event, containerId) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleTerminalRun(containerId);
    }
  };

  const isAdmin = user?.role?.toUpperCase() === 'ADMIN' || user?.is_superuser;
  const isHostOwner = user?.role?.toUpperCase() === 'HOST';
  const canOperate = isAdmin || isHostOwner;

  const statusBadgeClass = (status) => {
    const normalized = (status || '').toUpperCase();
    if (normalized === 'RUNNING') return 'badge-viewer';
    if (normalized === 'PAUSED') return 'badge-owner';
    if (normalized === 'STOPPED' || normalized === 'KILLED' || normalized === 'REMOVED') return 'badge-admin';
    return 'badge-owner';
  };

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
          {isAdmin ? (
            <button
              className="btn-primary"
              style={{ marginTop: '12px', width: 'auto', padding: '8px 14px', fontSize: '13px' }}
              onClick={createLocalHost}
              disabled={creatingLocalHost}
            >
              {creatingLocalHost ? 'Creating host…' : 'Register New Host'}
            </button>
          ) : (
            <p className="empty-sub" style={{ marginTop: '10px' }}>
              Register/login as Admin to register hosts.
            </p>
          )}
          {emptyStateError ? (
            <p className="form-error" style={{ marginTop: '10px' }}>{emptyStateError}</p>
          ) : null}
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

      <div style={{ marginTop: '24px' }}>
        <p className="section-label" style={{ marginBottom: '10px' }}>Module 2 - Local container manager</p>
        <div className="empty-state" style={{ textAlign: 'left', padding: '1.2rem' }}>
          <p className="empty-sub" style={{ marginBottom: '10px' }}>
            Use a Module 2 host id (integer, usually <strong>1</strong>) to manage local Docker containers.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '120px 120px 1fr 1fr auto auto', gap: '8px', alignItems: 'end' }}>
            <div>
              <label className="form-label">Host ID</label>
              <input
                className="form-input"
                value={containerHostId}
                onChange={(e) => setContainerHostId(e.target.value)}
                placeholder="1"
              />
            </div>

            <div>
              <label className="form-label">Status</label>
              <select
                className="form-input"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">All</option>
                <option value="RUNNING">RUNNING</option>
                <option value="PAUSED">PAUSED</option>
                <option value="STOPPED">STOPPED</option>
                <option value="KILLED">KILLED</option>
                <option value="REMOVED">REMOVED</option>
              </select>
            </div>

            <div>
              <label className="form-label">Image</label>
              <input
                className="form-input"
                value={createImageRef}
                onChange={(e) => setCreateImageRef(e.target.value)}
                placeholder="nginx:alpine"
              />
            </div>

            <div>
              <label className="form-label">Container Name</label>
              <input
                className="form-input"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="optional"
              />
            </div>

            <button className="btn-secondary" onClick={loadContainers}>
              {containersLoading ? 'Refreshing…' : 'Refresh'}
            </button>

            <button
              className="btn-primary"
              style={{ marginTop: 0, width: 'auto', padding: '10px 14px' }}
              onClick={handleCreateContainer}
              disabled={!canOperate}
            >
              Create
            </button>
          </div>

          <div style={{ marginTop: '8px' }}>
            <button
              className="btn-secondary"
              onClick={setupModule2LocalHost}
              disabled={bootstrapLoading}
              style={{ padding: '6px 12px', fontSize: '12px' }}
            >
              {bootstrapLoading ? 'Setting up local module2 host…' : 'Setup Local Module2 Host'}
            </button>
          </div>

          {containerError ? <p className="form-error" style={{ marginTop: '10px' }}>{containerError}</p> : null}

          <div style={{ marginTop: '14px', display: 'grid', gap: '8px' }}>
            {containers.length === 0 ? (
              <p className="empty-sub">No containers found for this host id. Click Refresh or Create.</p>
            ) : (
              containers.map((item) => (
                <div key={item.id} style={{ border: '1px solid #e5e5e5', borderRadius: '10px', padding: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
                    <div>
                      <div className="host-name">{item.name}</div>
                      <div className="host-addr">{item.image_ref}</div>
                      <span className={`host-role-badge ${statusBadgeClass(item.status)}`}>
                        {item.status}
                      </span>
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', justifyContent: 'flex-end' }}>
                      <button className="btn-secondary" style={{ padding: '6px 9px', fontSize: '11px' }} onClick={() => handleStats(item.id)}>Stats</button>
                      <button className="btn-secondary" style={{ padding: '6px 9px', fontSize: '11px' }} onClick={() => handleLogs(item.id)}>Logs</button>
                      <button
                        className="btn-secondary"
                        style={{ padding: '6px 9px', fontSize: '11px' }}
                        onClick={() => handleOpenTerminal(item.id, item.name)}
                        disabled={!canOperate}
                      >
                        Terminal
                      </button>
                      <button className="btn-secondary" style={{ padding: '6px 9px', fontSize: '11px' }} onClick={() => handleContainerAction(item.id, 'start')} disabled={!canOperate}>Start</button>
                      <button className="btn-secondary" style={{ padding: '6px 9px', fontSize: '11px' }} onClick={() => handleContainerAction(item.id, 'stop')} disabled={!canOperate}>Stop</button>
                      <button className="btn-secondary" style={{ padding: '6px 9px', fontSize: '11px' }} onClick={() => handleContainerAction(item.id, 'restart')} disabled={!canOperate}>Restart</button>
                      <button className="btn-secondary" style={{ padding: '6px 9px', fontSize: '11px' }} onClick={() => handleContainerAction(item.id, 'pause')} disabled={!canOperate}>Pause</button>
                      <button className="btn-secondary" style={{ padding: '6px 9px', fontSize: '11px' }} onClick={() => handleContainerAction(item.id, 'unpause')} disabled={!canOperate}>Unpause</button>
                      <button className="btn-secondary" style={{ padding: '6px 9px', fontSize: '11px' }} onClick={() => handleContainerAction(item.id, 'kill')} disabled={!canOperate}>Kill</button>
                      <button className="btn-secondary" style={{ padding: '6px 9px', fontSize: '11px', color: '#b91c1c' }} onClick={() => handleContainerRemove(item.id)} disabled={!isAdmin}>Remove</button>
                    </div>
                  </div>

                  {openPanels[item.id]?.open && (
                    <div className="container-tools-panel">
                      <div className="container-tools-header">
                        <div className="container-tools-tabs">
                          <button
                            className={`tool-tab ${openPanels[item.id]?.tab === 'stats' ? 'active' : ''}`}
                            onClick={() => handleStats(item.id)}
                          >
                            Stats
                          </button>
                          <button
                            className={`tool-tab ${openPanels[item.id]?.tab === 'logs' ? 'active' : ''}`}
                            onClick={() => handleLogs(item.id)}
                          >
                            Logs
                          </button>
                          <button
                            className={`tool-tab ${openPanels[item.id]?.tab === 'terminal' ? 'active' : ''}`}
                            onClick={() => handleOpenTerminal(item.id, item.name)}
                            disabled={!canOperate}
                          >
                            Terminal
                          </button>
                        </div>
                        <button
                          className="tool-dismiss"
                          onClick={() => closeContainerPanel(item.id)}
                        >
                          Close
                        </button>
                      </div>

                      {openPanels[item.id]?.tab === 'stats' && (
                        <div className="tool-pane">
                          {statsByContainer[item.id] ? (
                            <div className="stats-grid">
                              <div className="stats-chip"><span>CPU</span><strong>{statsByContainer[item.id].cpu_percent}%</strong></div>
                              <div className="stats-chip"><span>Memory</span><strong>{statsByContainer[item.id].memory?.percent}%</strong></div>
                              <div className="stats-chip"><span>RX</span><strong>{statsByContainer[item.id].network?.rx_bytes}</strong></div>
                              <div className="stats-chip"><span>TX</span><strong>{statsByContainer[item.id].network?.tx_bytes}</strong></div>
                            </div>
                          ) : (
                            <p className="empty-sub">Loading stats...</p>
                          )}
                        </div>
                      )}

                      {openPanels[item.id]?.tab === 'logs' && (
                        <div className="tool-pane">
                          {logsByContainer[item.id]?.length ? (
                            <pre className="container-logs">{logsByContainer[item.id].join('\n')}</pre>
                          ) : (
                            <p className="empty-sub">No logs loaded yet. Click Logs again to refresh.</p>
                          )}
                        </div>
                      )}

                      {openPanels[item.id]?.tab === 'terminal' && (
                        <div className="tool-pane terminal-shell-pane">
                          <div className="terminal-toolbar">
                            <span className="terminal-status">
                              {terminalConnectedByContainer[item.id] ? 'Connected' : 'Disconnected'}
                            </span>
                            <button
                              className="btn-secondary"
                              style={{ padding: '5px 10px', fontSize: '11px', flex: 'none' }}
                              onClick={() => handleCloseTerminal(item.id)}
                              disabled={!terminalConnectedByContainer[item.id]}
                            >
                              Exit
                            </button>
                          </div>
                          <div className="terminal-input-row">
                            <span className="terminal-prompt">$</span>
                            <input
                              className="form-input terminal-input"
                              value={terminalInputByContainer[item.id] || ''}
                              onChange={(e) => setTerminalInputByContainer((prev) => ({ ...prev, [item.id]: e.target.value }))}
                              onKeyDown={(event) => handleTerminalKeyDown(event, item.id)}
                              placeholder="Type a command and press Enter"
                              disabled={!terminalConnectedByContainer[item.id]}
                            />
                          </div>
                          <pre
                            className="terminal-output"
                          >
                            {(terminalLinesByContainer[item.id] || []).join('\n')}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

    </div>
  </div>
);
}