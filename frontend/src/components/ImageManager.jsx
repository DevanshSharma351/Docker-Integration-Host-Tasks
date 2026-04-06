import { useState } from 'react';
import { imageService } from '../services/imageService';

export default function ImageManager({ hostId, onImageCreated }) {
  const [pullImageRef, setPullImageRef] = useState('alpine:latest');
  const [pullLoading, setPullLoading] = useState(false);

  const [buildDockerfile, setBuildDockerfile] = useState('FROM alpine:latest\nCMD ["echo", "hello world"]');
  const [buildTag, setBuildTag] = useState('my-custom-image:v1');
  const [buildLoading, setBuildLoading] = useState(false);
  const [buildOutput, setBuildOutput] = useState([]);

  const [inspectImageRef, setInspectImageRef] = useState('');
  const [inspectData, setInspectData] = useState(null);

  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const clearMessages = () => { setError(''); setSuccess(''); };

  const handlePull = async () => {
    if (!hostId) return setError('Host ID is required');
    clearMessages();
    setPullLoading(true);
    try {
      await imageService.pullImage(hostId, pullImageRef);
      setSuccess(`Background pull job started for ${pullImageRef}. Check the registry refresh in a few seconds.`);
      onImageCreated?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setPullLoading(false);
    }
  };

  const handleBuild = async () => {
    if (!hostId) return setError('Host ID is required');
    clearMessages();
    setBuildLoading(true);
    setBuildOutput([]);
    try {
      await imageService.buildImageStream({
        hostId,
        tag: buildTag,
        dockerfile: buildDockerfile,
        onEvent: (evt) => {
          setBuildOutput(prev => [...prev, evt.stream || evt.status || JSON.stringify(evt)]);
        }
      });
      setSuccess(`Image built successfully.`);
      onImageCreated?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBuildLoading(false);
    }
  };

  const handleInspect = async () => {
    if (!hostId || !inspectImageRef) return;
    clearMessages();
    try {
      const data = await imageService.inspectImage(hostId, inspectImageRef);
      setInspectData(data);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDelete = async () => {
    if (!hostId || !inspectImageRef) return;
    clearMessages();
    if (!window.confirm(`Are you sure you want to prune/delete ${inspectImageRef}?`)) return;
    try {
      await imageService.deleteImage(hostId, inspectImageRef);
      setSuccess(`Background delete job started for ${inspectImageRef}.`);
      setInspectData(null);
      setInspectImageRef('');
      onImageCreated?.();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="empty-state" style={{ textAlign: 'left', padding: '1.2rem', marginTop: '24px' }}>
      <p className="section-label" style={{ marginBottom: '16px' }}>Image Operations Panel</p>

      {error && <p className="form-error">{error}</p>}
      {success && <p className="form-error" style={{ borderColor: '#22c55e', backgroundColor: '#f0fdf4', color: '#166534' }}>{success}</p>}

      <div style={{ display: 'grid', gap: '20px', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>

        {/* Pull Panel */}
        <div style={{ padding: '15px', border: '1px solid #e5e5e5', borderRadius: '10px' }}>
          <p className="section-label">Pull Image</p>
          <label className="form-label">Image Reference (e.g., node:18-alpine)</label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              className="form-input"
              value={pullImageRef}
              onChange={e => setPullImageRef(e.target.value)}
            />
            <button className="btn-primary" style={{ width: 'auto', marginTop: 0 }} onClick={handlePull} disabled={pullLoading || !hostId}>
              {pullLoading ? 'Pulling...' : 'Pull'}
            </button>
          </div>
        </div>

        {/* Inspect/Delete Panel */}
        <div style={{ padding: '15px', border: '1px solid #e5e5e5', borderRadius: '10px' }}>
          <p className="section-label">Inspect & Prune Image</p>
          <label className="form-label">Target Image Reference</label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              className="form-input"
              value={inspectImageRef}
              onChange={e => setInspectImageRef(e.target.value)}
            />
            <button className="btn-secondary" style={{ width: 'auto', marginTop: 0 }} onClick={handleInspect} disabled={!hostId || !inspectImageRef}>
              Inspect
            </button>
            <button className="btn-primary" style={{ width: 'auto', marginTop: 0, backgroundColor: '#ef4444' }} onClick={handleDelete} disabled={!hostId || !inspectImageRef}>
              Delete
            </button>
          </div>
        </div>

      </div>

      {inspectData && (
        <div style={{ marginTop: '16px', padding: '15px', border: '1px solid #e5e5e5', borderRadius: '10px', background: '#fafafa' }}>
          <p className="section-label">Inspection Results: {inspectImageRef}</p>
          <div className="stats-grid" style={{ marginBottom: '12px' }}>
            <div className="stats-chip"><span>Size</span><strong>{(inspectData.size / 1024 / 1024).toFixed(2)} MB</strong></div>
            <div className="stats-chip"><span>Architecture</span><strong>{inspectData.architecture} / {inspectData.os}</strong></div>
            <div className="stats-chip"><span>Exposed Ports</span><strong>{Object.keys(inspectData.exposed_ports || {}).join(', ') || 'None'}</strong></div>
            <div className="stats-chip"><span>Environment Vars</span><strong>{(inspectData.env || []).length} vars</strong></div>
          </div>
          <p className="form-label">Docker Entrypoint</p>
          <pre className="container-logs" style={{ maxHeight: '80px', marginBottom: '10px' }}>{JSON.stringify(inspectData.entrypoint || [], null, 2)}</pre>
        </div>
      )}

      {/* Build Panel */}
      <div style={{ marginTop: '16px', padding: '15px', border: '1px solid #e5e5e5', borderRadius: '10px' }}>
        <p className="section-label">Automated Build Pipeline (Dockerfile)</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '10px' }}>
          <div>
            <label className="form-label">Image Tag Name</label>
            <input className="form-input" value={buildTag} onChange={e => setBuildTag(e.target.value)} />
          </div>
          <div>
            <label className="form-label">Dockerfile Contents</label>
            <textarea
              className="form-textarea"
              rows={4}
              value={buildDockerfile}
              onChange={e => setBuildDockerfile(e.target.value)}
            />
          </div>
          <button className="btn-primary" style={{ width: '150px' }} onClick={handleBuild} disabled={buildLoading || !hostId}>
            {buildLoading ? 'Building...' : 'Start Build'}
          </button>
        </div>

        {buildOutput.length > 0 && (
          <div style={{ marginTop: '14px' }}>
            <p className="form-label">Build Stream Output</p>
            <pre className="container-logs" style={{ maxHeight: '200px' }}>
              {buildOutput.join('\n')}
            </pre>
          </div>
        )}
      </div>

    </div>
  );
}
