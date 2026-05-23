import { motion } from 'framer-motion'
import type { CardData, Suit } from '../types'

const SUIT_SYMBOL: Record<Suit, string> = {
  hearts: '♥',
  diamonds: '♦',
  clubs: '♣',
  spades: '♠',
}

const RED_SUITS: Suit[] = ['hearts', 'diamonds']

function isRed(suit: Suit) { return RED_SUITS.includes(suit) }

interface Props {
  card: CardData
  selected?: boolean
  onClick?: () => void
  layoutId?: string
  small?: boolean
}

export default function PlayingCard({ card, selected, onClick, layoutId, small }: Props) {
  const red = isRed(card.suit)
  const sym = SUIT_SYMBOL[card.suit]
  const size = small ? 'card-small' : 'card'

  return (
    <motion.div
      layoutId={layoutId}
      layout
      className={`playing-card ${size} ${red ? 'red' : 'black'} ${selected ? 'selected' : ''} ${onClick ? 'clickable' : ''}`}
      onClick={onClick}
      whileHover={onClick ? { y: -8 } : undefined}
      whileTap={onClick ? { scale: 0.95 } : undefined}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
    >
      <span className="corner top-left">{card.rank}<br />{sym}</span>
      <span className="center-suit">{sym}</span>
      <span className="corner bottom-right">{card.rank}<br />{sym}</span>
    </motion.div>
  )
}

export function CardBack({ count, layoutId }: { count?: number; layoutId?: string }) {
  return (
    <motion.div layoutId={layoutId} layout className="playing-card card card-back">
      <div className="card-back-pattern" />
      {count !== undefined && <span className="card-count">{count}</span>}
    </motion.div>
  )
}
