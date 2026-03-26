import { API_BASE_URL } from './apiConfig';

function parseErrorPayload(payload) {
  if (!payload) return 'Request failed';
  if (typeof payload === 'string') return payload;
  if (payload.detail) return payload.detail;
  return JSON.stringify(payload);
}

export const imageService = {
  async buildImageStream({
    hostId,
    tag,
    dockerfile,
    contextZip,
    pull,
    nocache,
    onEvent,
  }) {
    const token = localStorage.getItem('access_token');
    if (!token) {
      throw new Error('Missing access token. Please login again.');
    }

    const formData = new FormData();
    if (tag?.trim()) formData.append('tag', tag.trim());
    if (dockerfile?.trim()) formData.append('dockerfile', dockerfile);
    if (contextZip) formData.append('context_zip', contextZip);
    formData.append('pull', String(Boolean(pull)));
    formData.append('nocache', String(Boolean(nocache)));

    const response = await fetch(`${API_BASE_URL}/api/hosts/${hostId}/images/build/`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
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

    if (!response.body) {
      throw new Error('Build started, but no stream output was returned by server.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        let parsed;
        try {
          parsed = JSON.parse(trimmed);
        } catch {
          parsed = { stream: trimmed };
        }

        onEvent?.(parsed);
      }
    }

    if (buffer.trim()) {
      try {
        onEvent?.(JSON.parse(buffer));
      } catch {
        onEvent?.({ stream: buffer.trim() });
      }
    }
  },
};
