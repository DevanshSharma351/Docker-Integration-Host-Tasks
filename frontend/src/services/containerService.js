import { API_BASE_URL } from './apiConfig';

function parseErrorPayload(payload) {
  if (!payload) return 'Request failed';
  if (typeof payload === 'string') return payload;
  if (payload.detail) return payload.detail;
  return JSON.stringify(payload);
}

export const containerService = {
  async deployContainer({ hostId, imageRef, name, ports, command }) {
    const token = localStorage.getItem('access_token');
    if (!token) {
      throw new Error('Missing access token. Please login again.');
    }

    const response = await fetch(`${API_BASE_URL}/api/containers/create/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        host_id: Number(hostId),
        image_ref: imageRef,
        name: name || '',
        ports: ports || '',
        command: command || '',
      }),
    });

    if (!response.ok) {
      let errorPayload = null;
      try {
        errorPayload = await response.json();
      } catch {
        errorPayload = await response.text();
      }
      throw new Error(parseErrorPayload(errorPayload));
    }

    return response.json();
  },
};
