const rawBase = import.meta.env.VITE_API_BASE_URL?.trim();

// In local dev, leave base empty so requests go through Vite proxy (/api -> backend).
export const API_BASE_URL = rawBase || '';
