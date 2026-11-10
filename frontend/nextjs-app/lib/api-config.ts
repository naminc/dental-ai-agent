const rawApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();

if (!rawApiUrl) {
  throw new Error(
    "NEXT_PUBLIC_API_URL is required. Copy .env.example to .env.local for development or configure it in the production build environment.",
  );
}

let parsedApiUrl: URL;
try {
  parsedApiUrl = new URL(rawApiUrl);
} catch {
  throw new Error("NEXT_PUBLIC_API_URL must be an absolute HTTP(S) URL.");
}

if (!['http:', 'https:'].includes(parsedApiUrl.protocol)) {
  throw new Error("NEXT_PUBLIC_API_URL must use HTTP or HTTPS.");
}

const isLoopback = ['127.0.0.1', 'localhost', '::1'].includes(
  parsedApiUrl.hostname,
);
if (process.env.NODE_ENV === 'production' && isLoopback) {
  throw new Error(
    "NEXT_PUBLIC_API_URL cannot point to localhost or 127.0.0.1 in production.",
  );
}

export const API_BASE_URL = rawApiUrl.replace(/\/+$/, '');

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}
