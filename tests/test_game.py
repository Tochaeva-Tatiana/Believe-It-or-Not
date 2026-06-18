"""Tests for the Believe-It-or-Not game logic."""

import unittest

from believe.common import RANKS, SUITS
from believe.server.game import Card, Deck, Game, Player


class GameLogicTest(unittest.TestCase):
    """Test cards, players, and the main game rules."""

    def test_deck_and_deal(self) -> None:
        """Check a complete deck and equal dealing."""
        deck = Deck()
        pairs = {
            (card.suit, card.rank)
            for card in deck.cards
        }

        self.assertEqual(deck.card_count(), 36)
        self.assertEqual(len(pairs), 36)
        self.assertEqual(
            {card.suit for card in deck.cards},
            set(SUITS),
        )
        self.assertEqual(
            {card.rank for card in deck.cards},
            set(RANKS),
        )
        self.assertEqual(str(Card("♥️", "D")), "D♥️")

        for player_count, hand_size in ((2, 18), (3, 12), (4, 9)):
            with self.subTest(player_count=player_count):
                players = [
                    Player(f"player{number}", number)
                    for number in range(1, player_count + 1)
                ]
                deck = Deck()
                deck.deal(players)

                self.assertEqual(deck.card_count(), 0)
                self.assertTrue(
                    all(
                        player.card_count() == hand_size
                        for player in players
                    )
                )

    def test_player_hand_operations(self) -> None:
        """Check adding, removing, and validating hand indexes."""
        first = Card("♣️", "6")
        second = Card("♦️", "7")
        third = Card("♥️", "D")

        player = Player("Tanya", 1)
        player.add_card(first)
        player.add_cards([second, third])

        self.assertEqual(player.hand, [first, second, third])

        removed = player.remove_cards([3, 1])

        self.assertEqual(removed, [third, first])
        self.assertEqual(player.hand, [second])

        for indexes in ([0], [-1], [1, 1], [2]):
            with self.subTest(indexes=indexes):
                hand_before = list(player.hand)

                with self.assertRaises(ValueError):
                    player.remove_cards(indexes)

                self.assertEqual(player.hand, hand_before)

    def test_automatic_discarding(self) -> None:
        """Check set discarding and victory after an automatic discard."""
        player = Player("Tanya", 1)
        player.hand = [
            Card(suit, "7")
            for suit in SUITS
        ] + [
            Card(suit, "K")
            for suit in SUITS
        ] + [
            Card(suit, "8")
            for suit in SUITS[:3]
        ] + [
            Card(suit, "A")
            for suit in SUITS
        ]

        discarded = player.discard_sets()

        self.assertEqual(discarded, ["7", "K"])
        self.assertEqual(
            [card.rank for card in player.hand].count("8"),
            3,
        )
        self.assertEqual(
            [card.rank for card in player.hand].count("A"),
            4,
        )

        game = Game()
        game.start(["Tanya", "Ira", "Anna"])
        game.players["Tanya"].hand = [
            Card(suit, "6")
            for suit in SUITS
        ]
        game.players["Ira"].hand = [Card("♣️", "7")]
        game.players["Anna"].hand = [Card("♦️", "8")]

        game.prepare_turn()

        self.assertTrue(game.players["Tanya"].finished)
        self.assertEqual(game.finish_order, ["Tanya"])
        self.assertNotIn("Tanya", game.active_order)
        self.assertEqual(game.current_player(), "Ira")

    def test_game_start_order_and_completion(self) -> None:
        """Check game start, cyclic order, and ending conditions."""
        for usernames in (
            ["Tanya", "Ira"],
            ["Tanya", "Ira", "Anna"],
            ["Tanya", "Ira", "Anna", "Maria"],
        ):
            with self.subTest(usernames=usernames):
                game = Game()
                game.start(usernames)

                self.assertTrue(game.started)
                self.assertEqual(game.player_order, usernames)
                self.assertEqual(game.current_player(), usernames[0])
                self.assertEqual(
                    [game.players[name].number for name in usernames],
                    list(range(1, len(usernames) + 1)),
                )

        game = Game()
        game.start(["Tanya", "Ira", "Anna"])

        self.assertEqual(game.next_player(), "Ira")
        self.assertEqual(game.next_player(), "Anna")
        self.assertEqual(game.next_player(), "Tanya")

        game.players["Ira"].finished = True
        game.remove_active_player("Ira")

        self.assertNotIn("Ira", game.active_order)
        self.assertEqual(game.next_player(), "Anna")
        self.assertEqual(game.next_player(), "Tanya")

        game.active_order = ["Tanya"]
        game.current_player_index = 0

        self.assertTrue(game.game_should_end())

        game = Game()
        game.start(["Tanya", "Ira"])
        game.players["Tanya"].hand = [Card("♣️", "A")]
        game.players["Ira"].hand = [Card("♦️", "A")]
        game.pile = [Card("♥️", "A")]

        self.assertTrue(game.only_aces_remain())
        self.assertTrue(game.game_should_end())

    def test_complete_round(self) -> None:
        """Check play, believe, doubt, pile transfer, and round reset."""
        game = Game()
        game.start(["Tanya", "Ira", "Anna"])

        game.players["Tanya"].hand = [
            Card("♣️", "7"),
            Card("♣️", "A"),
        ]
        game.players["Ira"].hand = [
            Card("♦️", "K"),
            Card("♥️", "8"),
        ]
        game.players["Anna"].hand = [
            Card("♠️", "6"),
        ]

        game.pile = []
        game.current_player_index = 0

        hand_before = list(game.players["Tanya"].hand)

        answer, events = game.play("A 1", "Tanya")

        self.assertEqual(answer, "Aces cannot be declared.")
        self.assertEqual(events, [])
        self.assertEqual(
            game.players["Tanya"].hand,
            hand_before,
        )

        answer, events = game.play("K 1", "Tanya")

        self.assertEqual(answer, "")
        self.assertEqual(game.declared_rank, "K")

        last_move = game.last_move
        assert last_move is not None

        self.assertEqual(last_move.username, "Tanya")
        self.assertEqual(game.current_player(), "Ira")
        self.assertEqual(len(game.pile), 1)

        answer, events = game.believe("1", "Ira")

        self.assertEqual(answer, "")
        self.assertEqual(game.declared_rank, "K")
        self.assertEqual(game.last_move.username, "Ira")
        self.assertEqual(
            game.last_move.cards,
            [Card("♦️", "K")],
        )
        self.assertEqual(len(game.pile), 2)
        self.assertEqual(game.current_player(), "Anna")

        answer, events = game.not_believe("1", "Anna")

        self.assertEqual(answer, "")
        self.assertIn(
            (
                "broadcast",
                "Checked card #{}: {}.",
                1,
                "K♦️",
            ),
            events,
        )

        self.assertEqual(
            game.players["Anna"].card_count(),
            3,
        )
        self.assertEqual(game.current_player(), "Tanya")
        self.assertEqual(game.pile, [])
        self.assertIsNone(game.last_move)
        self.assertIsNone(game.declared_rank)
        self.assertIsNone(game.pending_winner)

    def test_last_cards_and_winner(self) -> None:
        """Check mandatory doubt and pending-winner outcomes."""
        game = Game()
        game.start(["Tanya", "Ira", "Anna"])

        game.players["Tanya"].hand = [
            Card("♣️", "K"),
        ]
        game.players["Ira"].hand = [
            Card("♦️", "6"),
        ]
        game.players["Anna"].hand = [
            Card("♥️", "7"),
        ]

        game.current_player_index = 0

        game.play("K 1", "Tanya")

        self.assertEqual(game.pending_winner, "Tanya")

        ira_hand = list(game.players["Ira"].hand)

        answer, events = game.believe("1", "Ira")

        self.assertIn("must use not", answer)
        self.assertEqual(events, [])
        self.assertEqual(
            game.players["Ira"].hand,
            ira_hand,
        )

        game.not_believe("1", "Ira")

        self.assertTrue(game.players["Tanya"].finished)
        self.assertEqual(game.finish_order, ["Tanya"])
        self.assertNotIn("Tanya", game.active_order)
        self.assertIsNone(game.pending_winner)
        self.assertTrue(game.started)
        self.assertEqual(len(game.active_order), 2)

        game = Game()
        game.start(["Tanya", "Ira", "Anna"])

        game.players["Tanya"].hand = [
            Card("♣️", "6"),
        ]
        game.players["Ira"].hand = [
            Card("♦️", "7"),
        ]
        game.players["Anna"].hand = [
            Card("♥️", "8"),
        ]

        game.current_player_index = 0

        game.play("K 1", "Tanya")
        game.not_believe("1", "Ira")

        self.assertFalse(game.players["Tanya"].finished)
        self.assertNotIn("Tanya", game.finish_order)
        self.assertIn("Tanya", game.active_order)
        self.assertEqual(
            game.players["Tanya"].card_count(),
            1,
        )
        self.assertIsNone(game.pending_winner)
        self.assertEqual(game.current_player(), "Ira")


if __name__ == "__main__":
    unittest.main()
