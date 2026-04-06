import { useMemo, useState } from 'react';

export default function ImageGallery({ images = [], isLoading = false, error = '', onRefresh, onDeploy }) {
  const [query, setQuery] = useState('');

  const filteredImages = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return images;

    return images.filter((image) => {
      const ref = image.image_ref?.toLowerCase() || '';
      const source = image.source?.toLowerCase() || '';
      return ref.includes(normalized) || source.includes(normalized);
    });
  }, [images, query]);

  const statusBadgeClass = (status) => {
    const normalized = (status || '').toLowerCase();
    if (normalized === 'success') return 'badge-viewer';
    return 'badge-owner';
  };

  return (
    <div className="empty-state" style={{ textAlign: 'left', padding: '1.2rem' }}>
      <p className="empty-sub" style={{ marginBottom: '16px' }}>
        Browse available host images and deploy one to a new container.
      </p>

      {/* Header Controls */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '8px', alignItems: 'end', marginBottom: '16px' }}>
        <div>
          <label className="form-label">Search Image or Source</label>
          <input
            className="form-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by image reference..."
          />
        </div>
        <button 
          className="btn-secondary" 
          onClick={onRefresh} 
          disabled={isLoading}
          style={{ padding: '10px 14px', fontSize: '14px', width: 'auto', marginTop: 0 }}
        >
          {isLoading ? 'Refreshing...' : 'Refresh Registry'}
        </button>
      </div>

      {error ? <p className="form-error" style={{ marginTop: '10px', marginBottom: '14px' }}>{error}</p> : null}

      <div style={{ marginTop: '14px', display: 'grid', gap: '8px' }}>
        {filteredImages.length === 0 ? (
          <p className="empty-sub">
            {query ? 'No images match your search.' : 'No images available yet. Click Refresh.'}
          </p>
        ) : (
          filteredImages.map((image) => (
            <div key={image.image_ref} style={{ border: '1px solid #e5e5e5', borderRadius: '10px', padding: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
                <div>
                  <div className="host-name">{image.image_ref}</div>
                  <div className="host-addr">Source: {image.source || 'local host'}</div>
                  <span className={`host-role-badge ${statusBadgeClass(image.status)}`}>
                    {(image.status || 'READY').toUpperCase()}
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                  <button
                    className="btn-primary"
                    style={{ padding: '8px 12px', fontSize: '13px', width: 'auto', marginTop: 0 }}
                    onClick={() => onDeploy?.(image.image_ref)}
                  >
                    Deploy
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
