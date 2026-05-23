import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { wsUrl } from '../api'
import type { CardData, RoomData, Suit, WsEvent } from '../types'
import PlayingCard, { CardBack } from '../components/PlayingCard'
import SuitPicker from '../components/SuitPicker'

export default function GamePage() {
  const { roomId } = useParams<{ roomId: string }>()
  const navigate = useNavigate()
  const myId = localStorage.getItem('userId') ?? ''

  const [room, setRoom] = useState<RoomData | null>(null)
  const [lastPlayedCards, setLastPlayedCards] = useState<CardData[]>([])
  const [selected, setSelected] = useState<CardData[]>([])
  const [suitPicker, setSuitPicker] = useState(false)
  const [notification, setNotification] = useState('')
  const [gameOverInfo, setGameOverInfo] = useState<{ scores: Record<string, number> } | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const showNote = useCallback((msg: string) => {
    setNotification(msg)
    setTimeout(() => setNotification(''), 3000)
  }, [])

  useEffect(() => {
    if (!roomId) return
    const ws = new WebSocket(wsUrl(roomId))
    wsRef.current = ws

    ws.onmessage = (e) => {
      const msg: WsEvent = JSON.parse(e.data)

      if (msg.event === 'room_snapshot' || msg.event === 'player_drew') {
        setRoom(msg.room)
        if (msg.event === 'room_snapshot' && msg.room.game?.top_card) {
          setLastPlayedCards([msg.room.game.top_card])
        }
      }

      if (msg.event === 'player_played') {
        setRoom(msg.room)
        setLastPlayedCards(msg.cards)
        setSelected([])
      }

      if (msg.event === 'round_ended') {
        setRoom(msg.room)
        setLastPlayedCards([])
        setSelected([])
        const winnerId = msg.winner_id
        showNote(winnerId === myId ? '🎉 Вы выиграли раунд!' : `🏆 Раунд выиграл ${winnerId.slice(0, 8)}...`)
      }

      if (msg.event === 'game_over') {
        setRoom(msg.room)
        setGameOverInfo({ scores: msg.scores })
      }

      if (msg.event === 'error') {
        showNote(`❌ ${msg.detail}`)
      }
    }

    ws.onclose = (e) => {
      if (e.code === 4001) navigate('/login', { replace: true })
    }

    return () => { ws.close() }
  }, [roomId, navigate, myId, showNote])

  function sendWs(payload: object) {
    wsRef.current?.send(JSON.stringify(payload))
  }

  function toggleCard(card: CardData) {
    setSelected(prev => {
      const idx = prev.findIndex(c => c.rank === card.rank && c.suit === card.suit)
      if (idx >= 0) return prev.filter((_, i) => i !== idx)
      // All selected cards must be the same rank
      if (prev.length > 0 && prev[0].rank !== card.rank) return [card]
      return [...prev, card]
    })
  }

  function handlePlay() {
    if (selected.length === 0) return
    // Check if Jack is selected — need suit picker
    if (selected.some(c => c.rank === 'J')) {
      setSuitPicker(true)
      return
    }
    sendWs({ action: 'play_cards', cards: selected })
    setSelected([])
  }

  function handlePlayWithSuit(suit: Suit) {
    setSuitPicker(false)
    sendWs({ action: 'play_cards', cards: selected, declared_suit: suit })
    setSelected([])
  }

  function handleDraw() {
    sendWs({ action: 'draw_card' })
    setSelected([])
  }

  if (!room || !room.game) {
    return (
      <div className="game-page" style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
        <p style={{ color: '#90a4ae' }}>Загрузка игры...</p>
      </div>
    )
  }

  const game = room.game
  const pm = game.player_manager
  const myHand: CardData[] = pm.players[myId]?.hand ?? []
  const currentPlayerId = pm.turn_order[pm.current_player_index]
  const isMyTurn = currentPlayerId === myId
  const otherPlayerIds = room.player_ids.filter(id => id !== myId)

  return (
    <div className="game-page">
      {suitPicker && <SuitPicker onSelect={handlePlayWithSuit} onCancel={() => setSuitPicker(false)} />}

      {/* Notification */}
      <AnimatePresence>
        {notification && (
          <motion.div
            className="notification"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
          >
            {notification}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Game Over Modal */}
      {gameOverInfo && (
        <div className="modal-overlay">
          <div className="modal">
            <h2>🏁 Игра окончена!</h2>
            <div style={{ marginTop: 16, marginBottom: 20 }}>
              {Object.entries(gameOverInfo.scores)
                .sort(([, a], [, b]) => a - b)
                .map(([pid, score], i) => (
                  <div key={pid} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #2e4a35' }}>
                    <span>{i === 0 ? '🥇 ' : ''}{pid === myId ? 'Вы' : pid.slice(0, 8) + '...'}</span>
                    <span style={{ fontWeight: 600 }}>{score} очков</span>
                  </div>
                ))}
            </div>
            <button className="btn-primary" style={{ width: '100%' }} onClick={() => navigate('/rooms')}>
              В список румов
            </button>
          </div>
        </div>
      )}

      {/* Header: scores */}
      <div className="game-header">
        <button className="btn-secondary" style={{ fontSize: '0.8rem', padding: '4px 12px' }} onClick={() => navigate('/rooms')}>
          ← Выйти
        </button>
        <div className="scores">
          {room.player_ids.map(pid => (
            <span key={pid} className={`score-chip ${pid === currentPlayerId ? 'active' : ''} ${pid === myId ? 'mine' : ''}`}>
              {pid === myId ? 'Вы' : pid.slice(0, 6)}: <b>{game.scores[pid] ?? 0}</b>
            </span>
          ))}
        </div>
        <span style={{ fontSize: '0.82rem', color: '#90a4ae' }}>до {game.max_points} очков</span>
      </div>

      {/* Other players */}
      <div className="other-players">
        {otherPlayerIds.map(pid => {
          const handSize = pm.players[pid]?.hand.length ?? 0
          const isTurn = pid === currentPlayerId
          return (
            <div key={pid} className={`other-player ${isTurn ? 'their-turn' : ''}`}>
              <div style={{ fontSize: '0.8rem', color: isTurn ? '#ffd54f' : '#90a4ae', marginBottom: 6 }}>
                {isTurn ? '▶ ' : ''}{pid.slice(0, 8)}...
              </div>
              <div style={{ display: 'flex', gap: -8 }}>
                {Array.from({ length: Math.min(handSize, 8) }).map((_, i) => (
                  <div key={i} style={{ marginLeft: i > 0 ? -16 : 0 }}>
                    <CardBack />
                  </div>
                ))}
                {handSize > 8 && <span style={{ marginLeft: 4, alignSelf: 'center', color: '#90a4ae' }}>+{handSize - 8}</span>}
              </div>
              <div style={{ fontSize: '0.78rem', color: '#78909c', marginTop: 4 }}>{handSize} карт</div>
            </div>
          )
        })}
      </div>

      {/* Center: draw pile + discard pile */}
      <div className="center-area">
        {/* Draw pile */}
        <div className="pile-area">
          <div style={{ fontSize: '0.8rem', color: '#90a4ae', marginBottom: 8, textAlign: 'center' }}>Колода</div>
          <motion.div
            whileHover={isMyTurn ? { scale: 1.05 } : undefined}
            whileTap={isMyTurn ? { scale: 0.95 } : undefined}
            onClick={isMyTurn ? handleDraw : undefined}
            style={{ cursor: isMyTurn ? 'pointer' : 'default' }}
          >
            <CardBack layoutId="draw-pile" />
          </motion.div>
          {isMyTurn && (
            <div style={{ marginTop: 8, textAlign: 'center', fontSize: '0.78rem', color: '#66bb6a' }}>
              Нажмите для взятия
            </div>
          )}
        </div>

        {/* Center info */}
        <div className="center-info">
          {game.active_suit && (
            <div className="active-suit">
              Масть: <span style={{ color: ['hearts','diamonds'].includes(game.active_suit) ? '#ef5350' : '#fff', fontSize: '1.4rem' }}>
                {{ hearts: '♥', diamonds: '♦', clubs: '♣', spades: '♠' }[game.active_suit]}
              </span>
            </div>
          )}
          {game.cover_active && (
            <div style={{ color: '#ffd54f', fontSize: '0.85rem' }}>⚠️ Нужно закрыть 6!</div>
          )}
          <div style={{ fontSize: '0.82rem', color: isMyTurn ? '#66bb6a' : '#90a4ae', marginTop: 6 }}>
            {isMyTurn ? '▶ Ваш ход!' : `Ход: ${currentPlayerId.slice(0, 8)}...`}
          </div>
        </div>

        {/* Discard pile — shows cards from last move */}
        <div className="pile-area">
          <div style={{ fontSize: '0.8rem', color: '#90a4ae', marginBottom: 8, textAlign: 'center' }}>
            Сброс {lastPlayedCards.length > 1 ? `(${lastPlayedCards.length})` : ''}
          </div>
          <div className="discard-pile">
            <AnimatePresence mode="popLayout">
              {lastPlayedCards.map((card, i) => (
                <motion.div
                  key={`${card.rank}-${card.suit}`}
                  style={{ position: 'absolute', left: i * 20 }}
                  initial={{ scale: 0.5, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 0.8, opacity: 0 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 25, delay: i * 0.05 }}
                >
                  <PlayingCard
                    card={card}
                    layoutId={`discard-${card.rank}-${card.suit}`}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* My hand */}
      <div className="my-hand-area">
        <div style={{ fontSize: '0.82rem', color: '#90a4ae', marginBottom: 8 }}>
          Ваша рука ({myHand.length} карт)
          {selected.length > 0 && <span style={{ color: '#ffd54f', marginLeft: 12 }}>{selected.length} выбрано</span>}
        </div>
        <div className="my-hand">
          <AnimatePresence>
            {myHand.map((card) => {
              const isSelected = selected.some(c => c.rank === card.rank && c.suit === card.suit)
              return (
                <PlayingCard
                  key={`${card.rank}-${card.suit}`}
                  card={card}
                  selected={isSelected}
                  onClick={isMyTurn ? () => toggleCard(card) : undefined}
                  layoutId={`hand-${card.rank}-${card.suit}`}
                />
              )
            })}
          </AnimatePresence>
        </div>

        <div className="hand-actions">
          <button
            className="btn-primary"
            disabled={!isMyTurn || selected.length === 0}
            onClick={handlePlay}
          >
            Сыграть {selected.length > 0 ? `(${selected.length})` : ''}
          </button>
          <button
            className="btn-secondary"
            disabled={!isMyTurn}
            onClick={handleDraw}
          >
            Взять карту
          </button>
          {selected.length > 0 && (
            <button className="btn-warn" onClick={() => setSelected([])}>
              Отмена
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
