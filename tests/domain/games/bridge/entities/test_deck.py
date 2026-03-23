from app.domain.games.bridge.entities import *


def test_create_deck():
    deck = Deck()
    assert deck.draw_pile
    assert not deck.discard_pile
    assert deck.flips_count == 0

    assert len(deck.draw_pile) == 36


def test_deck_draw_and_discard_cards():
    deck = Deck()

    cards = deck.draw_card(1)

    assert isinstance(cards[0], Card)

    cards += deck.draw_card(2)

    assert len(cards) == 3
    assert len(deck.draw_pile) == 33

    deck.discard_card(cards)
    assert len(deck.discard_pile) == 3

    deck.discard_card(deck.draw_card(2))
    assert len(deck.discard_pile) == 5
    assert len(deck.draw_pile) == 31


def test_deck_shuffle():
    deck = Deck()

    assert deck.flips_count == 0
    temp_pile = deck.draw_pile[:]
    deck.shuffle()
    assert deck.flips_count == 0
    assert temp_pile != deck.draw_pile

    deck.discard_card(deck.draw_card(15))
    temp_pile = deck.discard_pile[-5:]
    deck.shuffle(amount_to_save=5)

    assert deck.flips_count == 1
    assert len(deck.draw_pile) == 31
    assert temp_pile == deck.discard_pile

    deck.flips_count = 5
    deck.discard_card(deck.draw_card(15))
    temp_pile = deck.discard_pile[-5:]
    deck.shuffle(amount_to_save=5)

    assert deck.flips_count == 6
    assert len(deck.draw_pile) == 31
    assert temp_pile == deck.discard_pile


def test_card_effects():
    from app.domain.games.bridge.entities.deck import create_standard_36

    cards = create_standard_36()

    deck = Deck(draw_pile=cards)
    for card in deck.draw_pile:
        effects = card.apply_effect()
        if not effects:
            continue

        for effect in effects:
            assert isinstance(effect, Effect)


def test_serialisation():
    deck = Deck()

    deck.flips_count = 5
    deck.discard_card(deck.draw_card(15))

    deck_dict = deck.model_dump()

    deck2 = Deck.model_validate(deck_dict)

    assert deck.flips_count == deck2.flips_count
    assert deck.discard_pile == deck2.discard_pile
    assert deck.draw_pile == deck2.draw_pile

    deck = Deck()

    deck_dict = deck.model_dump()

    deck2 = Deck.model_validate(deck_dict)

    assert deck.flips_count == deck2.flips_count
    assert deck.discard_pile == deck2.discard_pile
    assert deck.draw_pile == deck2.draw_pile

    deck = Deck()

    deck.flips_count = 5
    deck.discard_card(deck.draw_card(36))

    deck_dict = deck.model_dump()

    deck2 = Deck.model_validate(deck_dict)

    assert deck.flips_count == deck2.flips_count
    assert deck.discard_pile == deck2.discard_pile
    assert deck.draw_pile == deck2.draw_pile
