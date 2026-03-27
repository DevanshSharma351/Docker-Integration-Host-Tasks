import { useEffect, useMemo, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const roleActionMap = {
  VIEWER: [],
  HOST_OWNER: ['start', 'stop', 'restart', 'pause', 'unpause', 'kill', 'exec', 'create'],
  ADMIN: ['start', 'stop', 'restart', 'pause', 'unpause', 'kill', 'exec', 'create', 'remove'],
};

const statusColors = {
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

export default function App() {
  const [hostId, setHostId] = useState('1');
  const [statusFilter, setStatusFilter] = useState('');
  const [role, setRole] = useState('ADMIN');
  const [containers, setContainers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedContainer, setSelectedContainer] = useState(null);
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [tail, setTail] = useState(200);
  const [command, setCommand] = useState('echo hello from exec');
  const [terminalLines, setTerminalLines] = useState([]);

  const [createForm, setCreateForm] = useState({
    image_ref: 'nginx:alpine',
    name: '',
    environment: '{"MODE":"dev"}',
    port_bindings: '{}',
    volumes: '[]',
  });

  const allowed = useMemo(() => roleActionMap[role] || [], [role]);

  async function loadContainers() {
    if (!hostId) return;
    setLoading(true);
    setError('');
    try {
      const q = statusFilter ? `?status=${statusFilter}` : '';
      const data = await request(`/api/hosts/${hostId}/containers/${q}`);
      setContainers(data.results || []);
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
    try {
      await request(`/api/hosts/${hostId}/containers/${containerId}/${action}/`, {
        method: 'POST',
      });
      await loadContainers();
    } catch (e) {
      setError(e.message);
    }
  }

  async function fetchStats(containerId) {
    setSelectedContainer(containerId);
    setStats(null);
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
    try {
      const data = await request(`/api/hosts/${hostId}/containers/${containerId}/logs/?tail=${tail}`);
      setLogs(data.logs || []);
    } catch (e) {
      setError(e.message);
    }
  }

  async function runExec(containerId) {
    setSelectedContainer(containerId);
    setTerminalLines((prev) => [...prev, `$ ${command}`]);
    try {
      const ticketResp = await request(`/api/hosts/${hostId}/containers/${containerId}/exec/`, {
        method: 'POST',
      });

      const ws = new WebSocket(ticketResp.ws_url);
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'input', data: command }));
      };
      ws.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          if (payload.data) {
            setTerminalLines((prev) => [...prev, payload.data]);
          }
        } catch {
          setTerminalLines((prev) => [...prev, evt.data]);
        }
      };
      ws.onerror = () => setError('WebSocket exec failed.');
      ws.onclose = () => {
        setTerminalLines((prev) => [...prev, '[connection closed]']);
      };
    } catch (e) {
      setError(e.message);
    }
  }

  async function createContainer() {
    const environment = parseJsonSafe(createForm.environment, {});
    const port_bindings = parseJsonSafe(createForm.port_bindings, {});
    const volumes = parseJsonSafe(createForm.volumes, []);

    if (environment === null || port_bindings === null || volumes === null) {
      setError('Invalid JSON in create form fields.');
      return;
    }

    try {
      await request(`/api/hosts/${hostId}/containers/`, {
        method: 'POST',
        body: JSON.stringify({
          image_ref: createForm.image_ref,
          name: createForm.name || `check-${Date.now()}`,
          environment,
          port_bindings,
          volumes,
        }),
      });
      await loadContainers();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <h1>Container Control Deck</h1>
        <p>Validate lifecycle, stats, logs, and exec against your backend API.</p>
      </header>

      <section className="toolbar card">
        <label>
          Host ID
          <input value={hostId} onChange={(e) => setHostId(e.target.value)} />
        </label>

        <label>
          Filter Status
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
          Simulated Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="ADMIN">ADMIN</option>
            <option value="HOST_OWNER">HOST_OWNER</option>
            <option value="VIEWER">VIEWER</option>
          </select>
        </label>

        <button onClick={loadContainers} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </section>

      {allowed.includes('create') && (
        <section className="card create-box">
          <h2>Create Container</h2>
          <div className="grid-two">
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
          </div>

          <label>
            Environment JSON
            <textarea
              value={createForm.environment}
              onChange={(e) => setCreateForm((p) => ({ ...p, environment: e.target.value }))}
            />
          </label>
          <label>
            Ports JSON
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
          <button onClick={createContainer}>Create</button>
        </section>
      )}

      {error && <div className="error card">{error}</div>}

      <section className="card">
        <h2>Containers ({containers.length})</h2>
        <div className="container-list">
          {containers.map((c) => (
            <article key={c.id} className="container-item">
              <div className="headline">
                <strong>{c.name}</strong>
                <span className={`status-pill ${statusColors[c.status] || ''}`}>{c.status}</span>
              </div>
              <p>{c.image_ref}</p>

              <div className="actions">
                <button onClick={() => fetchStats(c.id)}>Stats</button>
                <button onClick={() => fetchLogs(c.id)}>Logs</button>
                {allowed.includes('start') && <button onClick={() => runAction(c.id, 'start')}>Start</button>}
                {allowed.includes('stop') && <button onClick={() => runAction(c.id, 'stop')}>Stop</button>}
                {allowed.includes('restart') && <button onClick={() => runAction(c.id, 'restart')}>Restart</button>}
                {allowed.includes('pause') && <button onClick={() => runAction(c.id, 'pause')}>Pause</button>}
                {allowed.includes('unpause') && <button onClick={() => runAction(c.id, 'unpause')}>Unpause</button>}
                {allowed.includes('kill') && <button onClick={() => runAction(c.id, 'kill')}>Kill</button>}
                {allowed.includes('exec') && <button onClick={() => runExec(c.id)}>Exec</button>}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panels">
        <div className="card panel">
          <h3>Stats</h3>
          {!stats && <p>Select a container and click Stats.</p>}
          {stats && (
            <pre>{JSON.stringify(stats, null, 2)}</pre>
          )}
        </div>

        <div className="card panel">
          <h3>Logs</h3>
          <label>
            Tail
            <input type="number" value={tail} onChange={(e) => setTail(Number(e.target.value) || 200)} />
          </label>
          {!logs.length && <p>Select a container and click Logs.</p>}
          {logs.length > 0 && <pre>{logs.join('\n')}</pre>}
        </div>

        <div className="card panel">
          <h3>Terminal</h3>
          <p>Selected: {selectedContainer || 'none'}</p>
          <input value={command} onChange={(e) => setCommand(e.target.value)} />
          <pre>{terminalLines.join('\n')}</pre>
        </div>
      </section>
    </div>
  );
}
