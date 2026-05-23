export type Suit = 'hearts' | 'diamonds' | 'clubs' | 'spades'
export type Rank = '6' | '7' | '8' | '9' | '10' | 'J' | 'Q' | 'K' | 'A'

export interface CardData {
  rank: Rank
  suit: Suit
}

export interface PlayerData {
  id: string
  name: string
  hand: CardData[]
}

export interface PlayerManagerData {
  players: Record<string, PlayerData>
  turn_order: string[]
  current_player_index: number
  skips: Record<string, number>
}

export interface GameData {
  id: string
  player_manager: PlayerManagerData
  top_card: CardData | null
  active_suit: Suit | null
  cover_active: boolean
  status: 'waiting' | 'playing' | 'finished'
  scores: Record<string, number>
  max_points: number
}

export interface RoomData {
  id: string
  name: string
  host_id: string
  player_ids: string[]
  ready_player_ids: string[]
  max_players: number
  score_limit: number
  status: string
  game?: GameData
}

export interface AuthUser {
  id: string
  email: string
  token: string
}

// WebSocket event types
export type WsEvent =
  | { event: 'room_snapshot'; room: RoomData }
  | { event: 'player_played'; player_id: string; cards: CardData[]; declared_suit: Suit | null; room: RoomData }
  | { event: 'player_drew'; player_id: string; count: number; room: RoomData }
  | { event: 'round_ended'; winner_id: string; scores: Record<string, number>; room: RoomData }
  | { event: 'game_over'; scores: Record<string, number>; room: RoomData }
  | { event: 'player_joined'; player_id: string; room: RoomData }
  | { event: 'player_left'; player_id: string; room: RoomData }
  | { event: 'player_ready'; player_id: string; room: RoomData }
  | { event: 'game_started'; room: RoomData }
  | { event: 'error'; detail: string }
