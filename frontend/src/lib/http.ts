import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

type RequestBody = BodyInit | Record<string, unknown>

type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: RequestBody
}

export class ApiError extends Error {
  readonly status: number
  readonly isNetworkError: boolean

  constructor(message: string, options: { status: number; isNetworkError?: boolean }) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status
    this.isNetworkError = options.isNetworkError ?? false
  }
}

export function buildApiUrl(path: string): string {
  const baseUrl = env.apiBaseUrl.endsWith('/') ? env.apiBaseUrl : `${env.apiBaseUrl}/`
  return new URL(path.replace(/^\//, ''), baseUrl).toString()
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const body = serializeBody(options.body)

  if (body !== undefined && typeof body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const {
    data: { session },
  } = await supabase.auth.getSession()

  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`)
  }

  let response: Response
  try {
    response = await fetch(buildApiUrl(path), {
      ...options,
      headers,
      body,
    })
  } catch (error) {
    throw new ApiError(error instanceof Error ? error.message : 'Network request failed', {
      status: 0,
      isNetworkError: true,
    })
  }

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), { status: response.status })
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

function serializeBody(body: RequestBody | undefined): BodyInit | undefined {
  if (body === undefined) {
    return undefined
  }
  if (
    typeof body === 'string' ||
    body instanceof FormData ||
    body instanceof Blob ||
    body instanceof URLSearchParams ||
    body instanceof ArrayBuffer ||
    body instanceof ReadableStream
  ) {
    return body
  }
  return JSON.stringify(body)
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown; message?: unknown }
    if (typeof payload.detail === 'string') {
      return payload.detail
    }
    if (typeof payload.message === 'string') {
      return payload.message
    }
  } catch {
    // Fall through to the status text when the backend did not return JSON.
  }
  return response.statusText || 'Request failed'
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: RequestBody, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: RequestBody, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: RequestBody, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { ...options, method: 'DELETE' }),
}
