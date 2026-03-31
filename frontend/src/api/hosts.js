import api from './axios';

export const getHosts = () => api.get('/hosts/'); 
export const createHost = (data) => api.post('/hosts/', data); 
export const deleteHost = (id) => api.delete(`/hosts/${id}/`); 
export const assignUser = (hostId, data) => api.post(`/hosts/${hostId}/assign/`, data); 