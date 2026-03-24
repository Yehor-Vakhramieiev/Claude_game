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

    deck_json = deck.model_dump_json()

    deck2 = Deck.model_validate_json(deck_json)

    assert deck.flips_count == deck2.flips_count
    assert deck.discard_pile == deck2.discard_pile
    assert deck.draw_pile == deck2.draw_pile

    deck = Deck()

    deck_json = deck.model_dump_json()

    deck2 = Deck.model_validate_json(deck_json)

    assert deck.flips_count == deck2.flips_count
    assert deck.discard_pile == deck2.discard_pile
    assert deck.draw_pile == deck2.draw_pile

    deck = Deck()

    deck.flips_count = 5
    deck.discard_card(deck.draw_card(36))

    deck_json = deck.model_dump_json()

    deck2 = Deck.model_validate_json(deck_json)

    assert deck.flips_count == deck2.flips_count
    assert deck.discard_pile == deck2.discard_pile
    assert deck.draw_pile == deck2.draw_pile


def test_deep_into_serialisation():
    deck1 = Deck()
    deck1.flips_count = 5
    deck1.discard_card(deck1.draw_card(14))

    deck_json = deck1.model_dump_json()

    deck2 = Deck.model_validate_json(deck_json)

    assert deck1.flips_count == deck2.flips_count

    for card1, card2 in zip(deck1.draw_pile, deck2.draw_pile):
        assert type(card1) == type(card2)
        effects1, effects2 = card1.apply_effect(), card2.apply_effect()
        assert effects1 == effects2
        if effects1 is None:
            continue
        for effect1, effect2 in zip(effects1, effects2):
            assert type(effect1) == type(effect2)

    for card1, card2 in zip(deck1.discard_pile, deck2.discard_pile):
        assert type(card1) == type(card2)
        effects1, effects2 = card1.apply_effect(), card2.apply_effect()
        assert effects1 == effects2
        if effects1 is None:
            continue
        for effect1, effect2 in zip(effects1, effects2):
            assert type(effect1) == type(effect2)


def test_shuffle_potential_error():
    deck = Deck()
    deck.discard_card(deck.draw_card(1))
    deck.draw_pile = []

    deck.shuffle()

    assert deck.flips_count == 0
    assert len(deck.discard_pile) == 1
    assert len(deck.draw_pile) == 0


def test_not_enough_cards_to_draw():
    deck = Deck()
    deck.draw_pile = []
    cards = deck.draw_card(5)

    assert len(cards) == 0

    deck = Deck()
    deck.draw_card(33)
    cards = deck.draw_card(5)

    assert len(cards) == 3

    deck = Deck()
    cards = deck.draw_card(50)

    assert len(cards) == 36
