import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { leaveRoom, markReady, wsUrl } from '../api'
import type { RoomData, WsEvent } from '../types'

export default function LobbyPage() {
  const { roomId } = useParams<{ roomId: string }>()
  const navigate = useNavigate()
  const myId = localStorage.getItem('userId') ?? ''

  const [room, setRoom] = useState<RoomData | null>(null)
  const [error, setError] = useState('')
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!roomId) return
    const ws = new WebSocket(wsUrl(roomId))
    wsRef.current = ws

    ws.onmessage = (e) => {
      const msg: WsEvent = JSON.parse(e.data)
      if (msg.event === 'room_snapshot' || msg.event === 'player_joined' ||
          msg.event === 'player_left' || msg.event === 'player_ready') {
        setRoom(msg.room)
        // If game already started (e.g. page refresh), go directly to game
        if (msg.room.status === 'playing') {
          navigate(`/game/${roomId}`, { replace: true })
        }
      }
      if (msg.event === 'game_started') {
        navigate(`/game/${roomId}`, { replace: true })
      }
      if (msg.event === 'error') setError(msg.detail)
    }

    ws.onerror = () => setError('Ошибка подключения')
    ws.onclose = (e) => {
      if (e.code === 4001) { navigate('/login', { replace: true }); return }
      if (e.code === 4003 || e.code === 4004) { navigate('/rooms', { replace: true }); return }
    }

    return () => { ws.close() }
  }, [roomId, navigate])

  async function handleReady() {
    if (!roomId) return
    setError('')
    try {
      await markReady(roomId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка')
    }
  }

  async function handleLeave() {
    if (!roomId) return
    setError('')
    try {
      await leaveRoom(roomId)
      navigate('/rooms')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка')
    }
  }

  if (!room) {
    return (
      <div className="page" style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <p style={{ color: '#90a4ae' }}>Подключение к лобби...</p>
      </div>
    )
  }

  const isReady = room.ready_player_ids.includes(myId)
  const waitingFor = room.player_ids.length - room.ready_player_ids.length

  return (
    <div className="page" style={{ maxWidth: 500, margin: '0 auto', paddingTop: 40 }}>
      <div className="card-surface">
        <h1 style={{ marginBottom: 6 }}>{room.name}</h1>
        <p style={{ color: '#90a4ae', fontSize: '0.9rem', marginBottom: 24 }}>
          Лимит очков: {room.score_limit} &nbsp;·&nbsp; До {room.max_players} игроков
        </p>

        <h2 style={{ marginBottom: 12 }}>Игроки ({room.player_ids.length}/{room.max_players})</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
          {room.player_ids.map(pid => {
            const ready = room.ready_player_ids.includes(pid)
            const isHost = pid === room.host_id
            const isMe = pid === myId
            return (
              <div key={pid} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: '#1a3a22', borderRadius: 8 }}>
                <span style={{ fontSize: '1.2rem' }}>{ready ? '✅' : '⏳'}</span>
                <span style={{ flex: 1, fontSize: '0.9rem', color: '#b0bec5' }}>
                  {isMe ? 'Вы' : pid.slice(0, 8) + '...'}
                  {isHost && <span style={{ marginLeft: 8, fontSize: '0.78rem', color: '#ffd54f' }}>👑 хост</span>}
                </span>
                <span style={{ fontSize: '0.82rem', color: ready ? '#66bb6a' : '#78909c' }}>
                  {ready ? 'Готов' : 'Не готов'}
                </span>
              </div>
            )
          })}
        </div>

        {room.player_ids.length < 2 && (
          <p style={{ color: '#ffd54f', fontSize: '0.88rem', marginBottom: 16 }}>
            ⚠️ Нужно минимум 2 игрока для старта
          </p>
        )}

        {room.player_ids.length >= 2 && !isReady && (
          <p style={{ color: '#90a4ae', fontSize: '0.88rem', marginBottom: 16 }}>
            Ожидаем {waitingFor} игрок{waitingFor === 1 ? 'а' : 'ов'}...
          </p>
        )}

        {error && <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>}

        <div style={{ display: 'flex', gap: 10 }}>
          {!isReady && (
            <button className="btn-primary" style={{ flex: 1 }} onClick={handleReady}>
              ✓ Готов
            </button>
          )}
          {isReady && (
            <div style={{ flex: 1, padding: '8px 18px', background: '#1b5e20', borderRadius: 6, textAlign: 'center', color: '#a5d6a7' }}>
              Ожидаем других...
            </div>
          )}
          <button className="btn-danger" onClick={handleLeave}>Выйти</button>
        </div>
      </div>
    </div>
  )
}
