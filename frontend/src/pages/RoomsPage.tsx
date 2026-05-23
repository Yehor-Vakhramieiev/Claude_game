import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listRooms, createRoom, joinRoom } from '../api'
import type { RoomData } from '../types'

export default function RoomsPage() {
  const navigate = useNavigate()
  const myId = localStorage.getItem('userId') ?? ''
  const email = localStorage.getItem('email') ?? ''

  const [rooms, setRooms] = useState<RoomData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newMax, setNewMax] = useState(4)
  const [newLimit, setNewLimit] = useState<150 | 250>(150)
  const [creating, setCreating] = useState(false)

  async function load() {
    setLoading(true)
    try {
      setRooms(await listRooms())
    } catch {
      setError('Не удалось загрузить румы')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function logout() {
    localStorage.clear()
    navigate('/login')
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    setError('')
    try {
      const room = await createRoom(newName.trim(), newMax, newLimit)
      navigate(`/lobby/${room.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка')
      setCreating(false)
    }
  }

  async function handleJoin(roomId: string) {
    setError('')
    try {
      await joinRoom(roomId)
      navigate(`/lobby/${roomId}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка')
    }
  }

  function statusLabel(room: RoomData) {
    if (room.status === 'playing') return '🎮 Игра идёт'
    if (room.status === 'finished') return '🏁 Завершена'
    return `⏳ Ожидание (${room.player_ids.length}/${room.max_players})`
  }

  return (
    <div className="page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1>🃏 Bridge — Румы</h1>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: '0.85rem', color: '#90a4ae' }}>{email}</span>
          <button className="btn-secondary" onClick={logout}>Выйти</button>
        </div>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>}

      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <button className="btn-primary" onClick={() => setShowCreate(v => !v)}>
          {showCreate ? 'Отмена' : '+ Создать рум'}
        </button>
        <button className="btn-secondary" onClick={load}>Обновить</button>
      </div>

      {showCreate && (
        <div className="card-surface" style={{ marginBottom: 20 }}>
          <h2>Новый рум</h2>
          <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <input
              placeholder="Название рума"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              required
              maxLength={50}
              autoFocus
            />
            <div style={{ display: 'flex', gap: 12 }}>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: '0.85rem', color: '#90a4ae', display: 'block', marginBottom: 4 }}>
                  Макс. игроков
                </label>
                <select value={newMax} onChange={e => setNewMax(+e.target.value)}>
                  {[2, 3, 4, 5].map(n => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: '0.85rem', color: '#90a4ae', display: 'block', marginBottom: 4 }}>
                  Лимит очков
                </label>
                <select value={newLimit} onChange={e => setNewLimit(+e.target.value as 150 | 250)}>
                  <option value={150}>150</option>
                  <option value={250}>250</option>
                </select>
              </div>
            </div>
            <button type="submit" className="btn-primary" disabled={creating}>
              {creating ? 'Создание...' : 'Создать'}
            </button>
          </form>
        </div>
      )}

      {loading ? (
        <p style={{ color: '#90a4ae' }}>Загрузка...</p>
      ) : rooms.length === 0 ? (
        <p style={{ color: '#90a4ae' }}>Нет доступных румов. Создайте первый!</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {rooms.map(room => {
            const alreadyIn = room.player_ids.includes(myId)
            const canJoin = room.status === 'waiting' && !alreadyIn && room.player_ids.length < room.max_players
            return (
              <div key={room.id} className="card-surface" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '1.05rem' }}>{room.name}</div>
                  <div style={{ fontSize: '0.85rem', color: '#90a4ae', marginTop: 4 }}>
                    {statusLabel(room)} &nbsp;·&nbsp; лимит {room.score_limit}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {alreadyIn && (
                    <button className="btn-primary" onClick={() => navigate(`/lobby/${room.id}`)}>
                      Войти
                    </button>
                  )}
                  {canJoin && (
                    <button className="btn-secondary" onClick={() => handleJoin(room.id)}>
                      Присоединиться
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
