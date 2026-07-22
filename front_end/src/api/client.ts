import axios from "axios";

const API_BASE_URL =
  window.location.hostname === "192.168.203.30"
    ? (import.meta.env.VITE_API_BASE_URL ?? "http://192.168.203.30:8000")
    : (import.meta.env.VITE_API_BASE_URL_LOCAL ?? "http://localhost:8000");

const ACCESS_TOKEN_STORAGE_KEY = "access_token";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export { ACCESS_TOKEN_STORAGE_KEY, API_BASE_URL };
