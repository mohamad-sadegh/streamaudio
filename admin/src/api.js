function csrfToken() {
  const match = document.cookie.match(/(?:^|; )sa_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export async function api(path, options = {}) {
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(options.headers || {}),
  };

  const method = (options.method || "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    headers["X-CSRF-Token"] = csrfToken();
  }

  const res = await fetch(path, {
    ...options,
    headers,
    credentials: "include",
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text };
    }
  }

  if (!res.ok) {
    const detail = data?.detail;
    const detailText = Array.isArray(detail)
      ? detail.map((d) => d?.msg || d).join("، ")
      : detail;
    const err = new Error(
      data?.error || detailText || `درخواست ناموفق بود (${res.status})`,
    );
    err.status = res.status;
    err.data = data;
    throw err;
  }

  return data;
}

export const Auth = {
  me: () => api("/api/auth/me"),
  login: (username, password) =>
    api("/api/auth/login", { method: "POST", body: { username, password } }),
  logout: () => api("/api/auth/logout", { method: "POST", body: {} }),
};

export const Publishers = {
  list: () => api("/api/publishers"),
  create: (username, label) =>
    api("/api/publishers", { method: "POST", body: { username, label } }),
  update: (id, patch) =>
    api(`/api/publishers/${id}`, { method: "PATCH", body: patch }),
  setDesiredMode: (id, mode) =>
    api(`/api/publishers/${id}/desired-mode`, {
      method: "POST",
      body: { mode },
    }),
  rotate: (id) =>
    api(`/api/publishers/${id}/rotate-secret`, { method: "POST", body: {} }),
  remove: (id) => api(`/api/publishers/${id}`, { method: "DELETE" }),
  listenToken: (id) =>
    api(`/api/streams/${id}/listen-token`, { method: "POST", body: {} }),
};

export const Users = {
  list: () => api("/api/users"),
  create: (username, password) =>
    api("/api/users", { method: "POST", body: { username, password } }),
  update: (id, patch) => api(`/api/users/${id}`, { method: "PATCH", body: patch }),
  remove: (id) => api(`/api/users/${id}`, { method: "DELETE" }),
};

export const Roles = {
  list: () => api("/api/roles"),
};
