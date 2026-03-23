from app.domain.games.bridge.entities import *


def test_create_deck():
    deck = Deck()
    assert deck.draw_pile != []
    assert deck.discard_pile == []
