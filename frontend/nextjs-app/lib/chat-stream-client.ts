import { apiUrl } from '@/lib/api-config';
import {
  ApiError,
  ApiUnauthorizedError,
  errorMessage,
  parseJsonResponse,
} from '@/lib/api-client';

export interface ChatStreamRequest {
  session_id: string;
  user_question: string;
  chat_history: Array<{ role: 'user' | 'assistant'; content: string }>;
}

export async function openChatStream(
  payload: ChatStreamRequest,
  token: string,
  options: { signal?: AbortSignal; onUnauthorized?: () => void } = {},
): Promise<Response> {
  const response = await fetch(apiUrl('/chat'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });

  if (response.ok) return response;

  const body = await parseJsonResponse(response);
  const message = errorMessage(body, `API error: ${response.status}`);
  if (response.status === 401) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_info');
    }
    options.onUnauthorized?.();
    throw new ApiUnauthorizedError(message, body);
  }
  throw new ApiError(message, response.status, body);
}
