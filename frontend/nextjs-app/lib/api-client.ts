import { apiUrl } from '@/lib/api-config';

const DEFAULT_TIMEOUT_MS = 15_000;

interface ApiErrorBody {
  detail?: string | Array<{ msg?: string }>;
  message?: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class ApiUnauthorizedError extends ApiError {
  constructor(message: string, body: unknown) {
    super(message, 401, body);
    this.name = 'ApiUnauthorizedError';
  }
}

export class ApiTimeoutError extends Error {
  constructor() {
    super('Yêu cầu đã hết thời gian chờ. Vui lòng thử lại.');
    this.name = 'ApiTimeoutError';
  }
}

export interface ApiRequestOptions
  extends Omit<RequestInit, 'body' | 'headers'> {
  body?: unknown;
  headers?: HeadersInit;
  token?: string | null;
  timeoutMs?: number;
  onUnauthorized?: () => void;
}

function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

function handleUnauthorized(callback?: () => void): void {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_info');
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
  }
  callback?.();
}

export async function parseJsonResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export function errorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== 'object') return fallback;
  const value = body as ApiErrorBody;
  if (typeof value.detail === 'string') return value.detail;
  if (Array.isArray(value.detail)) {
    const messages = value.detail
      .map((item) => item.msg)
      .filter((message): message is string => Boolean(message));
    if (messages.length) return messages.join(', ');
  }
  return typeof value.message === 'string' ? value.message : fallback;
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    body,
    headers: initialHeaders,
    token = getStoredToken(),
    timeoutMs = DEFAULT_TIMEOUT_MS,
    onUnauthorized,
    signal: externalSignal,
    ...requestInit
  } = options;
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  const abortFromExternal = () => controller.abort();
  if (externalSignal?.aborted) {
    controller.abort();
  } else {
    externalSignal?.addEventListener('abort', abortFromExternal, { once: true });
  }

  const headers = new Headers(initialHeaders);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  try {
    const response = await fetch(apiUrl(path), {
      ...requestInit,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const responseBody = await parseJsonResponse(response);

    if (!response.ok) {
      const message = errorMessage(responseBody, `API error: ${response.status}`);
      if (response.status === 401) {
        handleUnauthorized(onUnauthorized);
        throw new ApiUnauthorizedError(message, responseBody);
      }
      throw new ApiError(message, response.status, responseBody);
    }

    return responseBody as T;
  } catch (error) {
    if (controller.signal.aborted && !externalSignal?.aborted) {
      throw new ApiTimeoutError();
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeoutId);
    externalSignal?.removeEventListener('abort', abortFromExternal);
  }
}
