import { useEffect, useMemo, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const roleActionMap = {
  VIEWER: ['stats', 'logs', 'refresh'],
  HOST_OWNER: ['stats', 'logs', 'refresh', 'start', 'stop', 'restart', 'pause', 'unpause', 'kill', 'exec', 'create'],
  ADMIN: ['stats', 'logs', 'refresh', 'start', 'stop', 'restart', 'pause', 'unpause', 'kill', 'exec', 'create', 'remove'],
};

const statusClassMap = {
  RUNNING: 'status-running',
  PAUSED: 'status-paused',
  STOPPED: 'status-stopped',
  KILLED: 'status-killed',
  REMOVED: 'status-removed',
  CREATED: 'status-created',
};

function parseJsonSafe(value, fallback) {
  if (!value.trim()) return fallback;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });

  const rawText = await res.text();
  let body = {};
  try {
    body = rawText ? JSON.parse(rawText) : {};
  } catch {
    body = { raw: rawText };
  }

  if (!res.ok) {
    throw new Error(body.error || body.detail || body.raw || `HTTP ${res.status}`);
  }
  return body;
}

function metric(value, suffix = '') {
  if (value === undefined || value === null) return '--';
  return `${value}${suffix}`;
}

export default function App() {
  const [hostId, setHostId] = useState('1');
  const [statusFilter, setStatusFilter] = useState('');
  const [role, setRole] = useState('ADMIN');
  const [containers, setContainers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const [selectedContainer, setSelectedContainer] = useState(null);
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [tail, setTail] = useState(200);

  const [command, setCommand] = useState('echo health-check');
  const [terminalLines, setTerminalLines] = useState([]);

  const [createForm, setCreateForm] = useState({
    image_ref: 'nginx:alpine',
    name: '',
    command: '',
    environment: '{"MODE":"dev"}',
    port_bindings: '{}',
    volumes: '[]',
  });

  const allowed = useMemo(() => roleActionMap[role] || [], [role]);

  async function loadContainers() {
    if (!hostId) return;
    setLoading(true);
    setError('');
    setMessage('');
    try {
      const q = statusFilter ? `?status=${statusFilter}` : '';
      const data = await request(`/api/hosts/${hostId}/containers/${q}`);
      setContainers(data.results || []);
      setMessage('Synced with Docker host.');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadContainers();
  }, []);

  async function runAction(containerId, action) {
    setError('');
    setMessage('');
    try {
      await request(`/api/hosts/${hostId}/containers/${containerId}/${action}/`, {
        method: 'POST',
      });
      setMessage(`${action.toUpperCase()} completed.`);
      await loadContainers();
    } catch (e) {
      setError(e.message);
    }
  }

  async function removeContainer(containerId) {
    setError('');
    setMessage('');
    try {
      await request(`/api/hosts/${hostId}/containers/${containerId}/`, {
        method: 'DELETE',
      });
      setMessage('Container removed.');
      await loadContainers();
    } catch (e) {
      setError(e.message);
    }
  }

  async function fetchStats(containerId) {
    setSelectedContainer(containerId);
    setStats(null);
    setError('');
    try {
      const data = await request(`/api/hosts/${hostId}/containers/${containerId}/stats/`);
      setStats(data);
    } catch (e) {
      setError(e.message);
    }
  }

  async function fetchLogs(containerId) {
    setSelectedContainer(containerId);
    setLogs([]);
    setError('');
    try {
      const data = await request(`/api/hosts/${hostId}/containers/${containerId}/logs/?tail=${tail}`);
      setLogs(data.logs || []);
    } catch (e) {
      setError(e.message);
    }
  }

  async function runExec(containerId) {
    setSelectedContainer(containerId);
    setError('');
    setTerminalLines((prev) => [...prev, `$ ${command}`]);

    try {
      const ticketResp = await request(`/api/hosts/${hostId}/containers/${containerId}/exec/`, {
        method: 'POST',
      });

      const ws = new WebSocket(ticketResp.ws_url);
      ws.onopen = () => ws.send(JSON.stringify({ type: 'input', data: command }));
      ws.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          if (payload?.data) {
            setTerminalLines((prev) => [...prev, payload.data]);
          }
        } catch {
          setTerminalLines((prev) => [...prev, evt.data]);
        }
      };
      ws.onerror = () => setError('WebSocket exec failed.');
      ws.onclose = () => setTerminalLines((prev) => [...prev, '[connection closed]']);
    } catch (e) {
      setError(e.message);
    }
  }

  async function createContainer() {
    const environment = parseJsonSafe(createForm.environment, {});
    const port_bindings = parseJsonSafe(createForm.port_bindings, {});
    const volumes = parseJsonSafe(createForm.volumes, []);

    if (environment === null || port_bindings === null || volumes === null) {
      setError('Invalid JSON in create form.');
      return;
    }

    const imageLower = createForm.image_ref.trim().toLowerCase();
    let command = (createForm.command || '').trim();
    if (!command && (imageLower === 'alpine' || imageLower.startsWith('alpine:'))) {
      command = 'sleep infinity';
    }

    setError('');
    setMessage('');
    try {
      await request(`/api/hosts/${hostId}/containers/`, {
        method: 'POST',
        body: JSON.stringify({
          image_ref: createForm.image_ref,
          name: createForm.name || `container-${Date.now()}`,
          command,
          environment,
          port_bindings,
          volumes,
        }),
      });
      setMessage('Container created.');
      await loadContainers();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>Module 2 Container Console</h1>
          <p>Live control panel with Docker sync, lifecycle actions, logs, stats, and exec.</p>
        </div>
        <div className="topbar-actions">
          <button className="ghost" onClick={loadContainers} disabled={loading}>
            {loading ? 'Syncing...' : 'Sync Now'}
          </button>
        </div>
      </header>

      <section className="panel controls">
        <label>
          Host ID
          <input value={hostId} onChange={(e) => setHostId(e.target.value)} />
        </label>

        <label>
          Status Filter
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">ALL</option>
            <option value="RUNNING">RUNNING</option>
            <option value="STOPPED">STOPPED</option>
            <option value="PAUSED">PAUSED</option>
            <option value="KILLED">KILLED</option>
            <option value="REMOVED">REMOVED</option>
          </select>
        </label>

        <label>
          Role (UI simulation)
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="ADMIN">ADMIN</option>
            <option value="HOST_OWNER">HOST_OWNER</option>
            <option value="VIEWER">VIEWER</option>
          </select>
        </label>

        <label>
          Log Tail
          <input type="number" value={tail} onChange={(e) => setTail(Number(e.target.value) || 200)} />
        </label>
      </section>

      {error && <section className="panel alert error">{error}</section>}
      {message && <section className="panel alert ok">{message}</section>}

      {allowed.includes('create') && (
        <section className="panel create-panel">
          <h2>Create Container</h2>
          <div className="create-grid">
            <label>
              Image
              <input
                value={createForm.image_ref}
                onChange={(e) => setCreateForm((p) => ({ ...p, image_ref: e.target.value }))}
              />
            </label>
            <label>
              Name
              <input
                value={createForm.name}
                onChange={(e) => setCreateForm((p) => ({ ...p, name: e.target.value }))}
              />
            </label>
            <label>
              Command (optional)
              <input
                value={createForm.command}
                placeholder="e.g. sleep infinity"
                onChange={(e) => setCreateForm((p) => ({ ...p, command: e.target.value }))}
              />
            </label>
            <label>
              Environment JSON
              <textarea
                value={createForm.environment}
                onChange={(e) => setCreateForm((p) => ({ ...p, environment: e.target.value }))}
              />
            </label>
            <label>
              Port Bindings JSON
              <textarea
                value={createForm.port_bindings}
                onChange={(e) => setCreateForm((p) => ({ ...p, port_bindings: e.target.value }))}
              />
            </label>
            <label>
              Volumes JSON
              <textarea
                value={createForm.volumes}
                onChange={(e) => setCreateForm((p) => ({ ...p, volumes: e.target.value }))}
              />
            </label>
          </div>
          <button onClick={createContainer}>Create</button>
        </section>
      )}

      <section className="panel list-panel">
        <h2>Containers ({containers.length})</h2>
        <div className="container-grid">
          {containers.map((c) => (
            <article key={c.id} className="container-card">
              <div className="container-head">
                <strong>{c.name}</strong>
                <span className={`badge ${statusClassMap[c.status] || ''}`}>{c.status}</span>
              </div>
              <p className="meta">Image: {c.image_ref}</p>
              <p className="meta mono">Record: {c.id}</p>

              <div className="actions">
                <button className="soft" onClick={() => fetchStats(c.id)}>Stats</button>
                <button className="soft" onClick={() => fetchLogs(c.id)}>Logs</button>
                {allowed.includes('start') && <button onClick={() => runAction(c.id, 'start')}>Start</button>}
                {allowed.includes('stop') && <button onClick={() => runAction(c.id, 'stop')}>Stop</button>}
                {allowed.includes('restart') && <button onClick={() => runAction(c.id, 'restart')}>Restart</button>}
                {allowed.includes('pause') && <button onClick={() => runAction(c.id, 'pause')}>Pause</button>}
                {allowed.includes('unpause') && <button onClick={() => runAction(c.id, 'unpause')}>Unpause</button>}
                {allowed.includes('kill') && <button className="warn" onClick={() => runAction(c.id, 'kill')}>Kill</button>}
                {allowed.includes('remove') && <button className="danger" onClick={() => removeContainer(c.id)}>Remove</button>}
                {allowed.includes('exec') && <button onClick={() => runExec(c.id)}>Exec</button>}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="split">
        <div className="panel">
          <h3>Stats</h3>
          <p className="meta">Selected: {selectedContainer || 'none'}</p>
          {!stats ? (
            <p className="meta">Select a container and click Stats.</p>
          ) : (
            <div className="stats-grid">
              <div><span>CPU</span><strong>{metric(stats.cpu_percent, '%')}</strong></div>
              <div><span>Memory</span><strong>{metric(stats.memory?.percent, '%')}</strong></div>
              <div><span>RX</span><strong>{metric(stats.network?.rx_bytes)}</strong></div>
              <div><span>TX</span><strong>{metric(stats.network?.tx_bytes)}</strong></div>
            </div>
          )}
        </div>

        <div className="panel">
          <h3>Logs</h3>
          {logs.length ? <pre>{logs.join('\n')}</pre> : <p className="meta">No logs yet.</p>}
        </div>

        <div className="panel">
          <h3>Exec Terminal</h3>
          <input value={command} onChange={(e) => setCommand(e.target.value)} placeholder="Type command" />
          <pre>{terminalLines.join('\n')}</pre>
        </div>
      </section>
    </div>
  );
}
