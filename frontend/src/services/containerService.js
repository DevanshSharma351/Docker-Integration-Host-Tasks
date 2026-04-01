import api from '../api/axios';

function normalizeError(error, fallback = 'Request failed') {
  const data = error?.response?.data;
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  if (data.error) return data.error;
  if (data.detail) return data.detail;
  const first = Object.values(data).flat?.()[0];
  return first || fallback;
}

export const containerService = {
  async bootstrapLocalHost() {
    try {
      const response = await api.post('/containers/hosts/bootstrap/');
      return response.data;
    } catch (error) {
      throw new Error(normalizeError(error, 'Failed to set up local module2 host'));
    }
  },

  async listContainers(hostId, status = '') {
    try {
      const query = status ? `?status=${encodeURIComponent(status)}` : '';
      const response = await api.get(`/hosts/${hostId}/containers/${query}`);
      return response.data;
    } catch (error) {
      throw new Error(normalizeError(error, 'Failed to load containers'));
    }
  },

  async createContainer(hostId, payload) {
    try {
      const response = await api.post(`/hosts/${hostId}/containers/`, payload);
      return response.data;
    } catch (error) {
      throw new Error(normalizeError(error, 'Failed to create container'));
    }
  },

  async action(hostId, containerId, action) {
    try {
      const response = await api.post(
        `/hosts/${hostId}/containers/${containerId}/${action}/`
      );
      return response.data;
    } catch (error) {
      throw new Error(normalizeError(error, `Failed to ${action} container`));
    }
  },

  async remove(hostId, containerId) {
    try {
      const response = await api.delete(`/hosts/${hostId}/containers/${containerId}/`);
      return response.data;
    } catch (error) {
      throw new Error(normalizeError(error, 'Failed to remove container'));
    }
  },

  async getStats(hostId, containerId) {
    try {
      const response = await api.get(`/hosts/${hostId}/containers/${containerId}/stats/`);
      return response.data;
    } catch (error) {
      throw new Error(normalizeError(error, 'Failed to load container stats'));
    }
  },

  async getLogs(hostId, containerId, tail = 200) {
    try {
      const response = await api.get(
        `/hosts/${hostId}/containers/${containerId}/logs/?tail=${tail}`
      );
      return response.data;
    } catch (error) {
      throw new Error(normalizeError(error, 'Failed to load container logs'));
    }
  },

  async getExecTicket(hostId, containerId) {
    try {
      const response = await api.post(`/hosts/${hostId}/containers/${containerId}/exec/`);
      return response.data;
    } catch (error) {
      throw new Error(normalizeError(error, 'Failed to open terminal session'));
    }
  },

  async deployContainer({ hostId, imageRef, name, command = '' }) {
    return this.createContainer(hostId, {
      image_ref: imageRef,
      name: name || `container-${Date.now()}`,
      command,
      environment: {},
      port_bindings: {},
      volumes: [],
    });
  },
};
