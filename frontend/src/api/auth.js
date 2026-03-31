import api from "./axios";

export const login = (data) => api.post("/auth/login/", data);
export const register = (data) => api.post("/auth/register/", data);
export const getMe = () => api.get("/auth/me/");
export const getUsers = () => api.get("/auth/users/");
export const refreshToken = (refresh) =>
  api.post("/auth/token/refresh/", { refresh });