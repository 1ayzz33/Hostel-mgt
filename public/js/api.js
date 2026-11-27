const BASE = '/api';

export class ApiError extends Error {
  constructor(status, message, details = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

function buildQuery(query) {
  if (!query) return '';
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) {
      params.set(key, value);
    }
  });
  const text = params.toString();
  return text ? `?${text}` : '';
}

async function request(method, path, { query, body } = {}) {
  const options = {
    method,
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  };
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(`${BASE}${path}${buildQuery(query)}`, options);
  } catch {
    throw new ApiError(0, 'Unable to reach the server. Check that HostelHub is running.');
  }
  const contentType = response.headers.get('Content-Type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : {};
  if (!response.ok) {
    throw new ApiError(response.status, payload.error || 'Something went wrong.', payload.details);
  }
  return payload;
}

export const api = {
  get: (path, query) => request('GET', path, { query }),
  post: (path, body = {}) => request('POST', path, { body }),
  patch: (path, body = {}) => request('PATCH', path, { body }),
  delete: (path) => request('DELETE', path),
};

export async function loadSession() {
  try {
    const data = await api.get('/auth/me');
    return data.user;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}
