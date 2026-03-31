export default function HostCard({ host }) {
  return (
    <div style={{ border: '1px solid #ccc', padding: '12px', margin: '8px 0' }}>
      <h4>{host.alias}</h4>
      <p>{host.ip_address}:{host.port}</p>
      <small>Added by: {host.created_by}</small>
    </div>
  );
}
