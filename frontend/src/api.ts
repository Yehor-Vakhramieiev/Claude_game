import type { RoomData } from './types'

function token(): string {
  return localStorage.getItem('token') ?? ''
}

function authHeaders(): HeadersInit {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${token()}` }
}

async function throwIfError(res: Response): Promise<Response> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `HTTP ${res.status}`)
  }
  return res
}

export async function register(email: string, password: string) {
  const res = await fetch('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  return throwIfError(res)
}

export async function login(email: string, password: string): Promise<{ access_token: string }> {
  const form = new URLSearchParams({ username: email, password })
  const res = await fetch('/auth/jwt/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  })
  await throwIfError(res)
  return res.json()
}

export async function getMe(): Promise<{ id: string; email: string }> {
  const res = await fetch('/auth/users/me', { headers: authHeaders() })
  await throwIfError(res)
  return res.json()
}

export async function listRooms(): Promise<RoomData[]> {
  const res = await fetch('/rooms', { headers: authHeaders() })
  await throwIfError(res)
  return res.json()
}

export async function createRoom(name: string, maxPlayers: number, scoreLimit: 150 | 250): Promise<RoomData> {
  const res = await fetch('/rooms', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ name, max_players: maxPlayers, score_limit: scoreLimit }),
  })
  await throwIfError(res)
  return res.json()
}

export async function joinRoom(roomId: string): Promise<RoomData> {
  const res = await fetch(`/rooms/${roomId}/join`, { method: 'POST', headers: authHeaders() })
  await throwIfError(res)
  return res.json()
}

export async function leaveRoom(roomId: string): Promise<void> {
  await fetch(`/rooms/${roomId}/leave`, { method: 'POST', headers: authHeaders() })
}

export async function markReady(roomId: string): Promise<RoomData> {
  const res = await fetch(`/rooms/${roomId}/ready`, { method: 'POST', headers: authHeaders() })
  await throwIfError(res)
  return res.json()
}

export function wsUrl(roomId: string): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}/ws/rooms/${roomId}?token=${token()}`
}
