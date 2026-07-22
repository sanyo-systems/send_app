import { useEffect, useState } from "react";

import { ACCESS_TOKEN_STORAGE_KEY, apiClient } from "../api/client";

type LoginPayload = {
  username: string;
  password: string;
};

type LoginResponse = {
  access_token: string;
  token_type: string;
};

export function useAuth() {
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
  });

  useEffect(() => {
    if (token) {
      apiClient.defaults.headers.common.Authorization = `Bearer ${token}`;
      localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
      return;
    }

    delete apiClient.defaults.headers.common.Authorization;
    localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  }, [token]);

  const login = async ({ username, password }: LoginPayload) => {
    const params = new URLSearchParams();
    params.set("username", username);
    params.set("password", password);

    const response = await apiClient.post<LoginResponse>(
      "/auth/login",
      params,
      {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      },
    );

    setToken(response.data.access_token);
    return response.data;
  };

  const logout = () => {
    setToken(null);
  };

  return {
    token,
    isAuthenticated: Boolean(token),
    login,
    logout,
  };
}
