import type { Suit } from '../types'

const SUITS: { suit: Suit; symbol: string; red: boolean }[] = [
  { suit: 'hearts', symbol: '♥', red: true },
  { suit: 'diamonds', symbol: '♦', red: true },
  { suit: 'clubs', symbol: '♣', red: false },
  { suit: 'spades', symbol: '♠', red: false },
]

interface Props {
  onSelect: (suit: Suit) => void
  onCancel: () => void
}

export default function SuitPicker({ onSelect, onCancel }: Props) {
  return (
    <div className="suit-picker-overlay">
      <div className="suit-picker">
        <p>Выберите масть</p>
        <div className="suit-grid">
          {SUITS.map(({ suit, symbol, red }) => (
            <button
              key={suit}
              className={`suit-btn ${red ? 'red' : 'black'}`}
              onClick={() => onSelect(suit)}
            >
              {symbol}
            </button>
          ))}
        </div>
        <button className="btn-secondary" style={{ marginTop: 12, width: '100%' }} onClick={onCancel}>
          Отмена
        </button>
      </div>
    </div>
  )
}
