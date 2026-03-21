from enum import StrEnum


class CardRank(StrEnum):
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


class CardSuit(StrEnum):
    HEARTS = "hearts"
    CLUBS = "club"
    DIAMONDS = "diamonds"
    SPADES = "spades"


DEFAULT_VALUES = {
    CardRank.SIX: 0,
    CardRank.SEVEN: 0,
    CardRank.EIGHT: 0,
    CardRank.NINE: 0,
    CardRank.TEN: 10,
    CardRank.JACK: 20,
    CardRank.QUEEN: 10,
    CardRank.KING: 10,
    CardRank.ACE: 15,
}


class Card:
    value: int

    def __init__(self, rank: CardRank, suit: CardSuit):
        self.rank = rank
        self.suit = suit
        self.value = DEFAULT_VALUES.get(rank)

    def apply_effect(self):
        pass

    def get_value(self):
        return self.value


class SixCard(Card):
    def apply_effect(self):
        pass


class SevenCard(Card):
    def apply_effect(self):
        pass


class EightCard(Card):
    def apply_effect(self):
        pass


class JackCard(Card):
    def apply_effect(self):
        pass


class JackSpadesCard(JackCard):
    def __init__(self, rank: CardRank, suit: CardSuit):
        super().__init__(rank, suit)
        self.value = 40


class KingHeartsCard(Card):
    def __init__(self, rank: CardRank, suit: CardSuit):
        super().__init__(rank, suit)
        self.value = 40

    def apply_effect(self):
        pass


class AceCard(Card):
    def apply_effect(self):
        pass


CARD_REGISTRY = {
    (CardRank.SIX, None): SixCard,
    (CardRank.SEVEN, None): SevenCard,
    (CardRank.EIGHT, None): EightCard,
    (CardRank.JACK, None): JackCard,
    (CardRank.JACK, CardSuit.SPADES): JackSpadesCard,
    (CardRank.KING, CardSuit.HEARTS): KingHeartsCard,
    (CardRank.ACE, None): AceCard,
}
