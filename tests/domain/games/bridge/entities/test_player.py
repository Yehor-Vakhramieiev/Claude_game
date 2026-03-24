from app.domain.games.bridge.entities import Player, Deck
import pytest


def test_player_functionality():
    player = Player(id="1", name="")
    deck = Deck()
    assert player.id == "1"
    assert player.name == ""

    card = deck.draw_card(1)
    player.hand.extend(card)

    assert len(player.hand) == 1
    assert player.hand[0] == card[0]

    player2 = Player(id="2", name="", hand=card)

    assert player2.id == "2"
    assert player2.name == ""
    assert len(player2.hand) == 1
    assert player2.hand[0] == card[0]


def test_player_adding_cards():
    from app.domain.games.bridge.entities.player import CardAlreadyInHandError

    player = Player(id="1", name="")
    deck = Deck()

    cards = deck.draw_card(3)

    player.add_cards(cards[0])

    assert len(player.hand) == 1
    assert player.hand[0] == cards[0]

    player.add_cards(cards[1:])
    assert len(player.hand) == 3
    assert player.hand[1] == cards[1]
    assert player.hand[2] == cards[2]

    with pytest.raises(CardAlreadyInHandError):
        player.add_cards(cards[0])


def test_player_deleting_cards():
    from app.domain.games.bridge.entities.player import CardNotRemovedError

    player = Player(id="1", name="")
    deck = Deck()

    cards = deck.draw_card(3)
    player.hand.extend(cards)

    player.remove_cards(cards[0])
    assert len(player.hand) == 2
    assert cards[0] not in player.hand
    assert cards[1] in player.hand
    assert cards[2] in player.hand

    player.remove_cards(cards[1:])

    assert len(player.hand) == 0

    with pytest.raises(CardNotRemovedError):
        player.remove_cards(cards[0])

    assert len(player.hand) == 0

    player.hand.extend(cards)

    with pytest.raises(CardNotRemovedError):
        player.remove_cards([cards[0], cards[0]])

    assert len(player.hand) == 3

    new_card = deck.draw_card(1)[0]
    with pytest.raises(CardNotRemovedError):
        player.remove_cards(new_card)


def test_player_serialization():
    player = Player(id="1", name="")
    deck = Deck()

    cards = deck.draw_card(10)
    player.hand.extend(cards)

    player_json = player.model_dump_json()

    player2 = Player.model_validate_json(player_json)

    assert player.id == player2.id
    assert player.name == player2.name

    assert len(player.hand) == len(player2.hand) == len(cards)

    for card1, card2 in zip(player.hand, player2.hand):
        assert card1 == card2
        assert type(card1) == type(card2)
