"""Game objects for Believe-It-or-Not."""

import random
import shlex

from believe.common import RANKS, SUITS, DECLARABLE_RANKS


def _(message: str) -> str:
    """Mark a singular message for translation."""
    return message


def ngettext(
    singular: str,
    plural: str,
    number: int,
) -> tuple[str, str]:
    """Mark plural messages for translation."""
    del number
    return singular, plural


class Card:
    """Represent one playing card."""

    def __init__(self, suit: str, rank: str) -> None:
        """Create a card with the given suit and rank."""
        if suit not in SUITS:
            raise ValueError(_("Unknown suit"))

        if rank not in RANKS:
            raise ValueError(_("Unknown rank"))

        self.suit = suit
        self.rank = rank

    def __str__(self) -> str:
        """Return a short text representation of the card."""
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        """Return a developer representation of the card."""
        return (
            f"{self.__class__.__name__}("
            f"suit={self.suit!r}, rank={self.rank!r})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare two cards by suit and rank."""
        if not isinstance(other, Card):
            return NotImplemented

        return self.suit == other.suit and self.rank == other.rank


class Deck:
    """Represent a deck of 36 playing cards."""

    def __init__(self) -> None:
        """Create a complete deck of 36 unique cards."""
        self.cards = [
            Card(suit, rank)
            for suit in SUITS
            for rank in RANKS
        ]

    def shuffle(self) -> None:
        """Shuffle the remaining cards in random order."""
        random.shuffle(self.cards)

    def card_count(self) -> int:
        """Return the number of cards remaining in the deck."""
        return len(self.cards)

    def take_card(self) -> Card:
        """Remove and return one card from the deck."""
        if not self.cards:
            raise IndexError(_("The deck is empty"))

        return self.cards.pop()

    def deal(self, players: list["Player"]) -> None:
        """Deal all cards evenly between players."""
        if len(players) < 2 or len(players) > 4:
            raise ValueError(
                _("The number of players must be between 2 and 4")
            )

        for player in players:
            player.clear_hand()

        while self.cards:
            for player in players:
                if not self.cards:
                    break

                player.add_card(self.take_card())


class Player:
    """Represent one participant of the game."""

    def __init__(self, username: str, number: int) -> None:
        """Create a player with an empty hand."""
        self.username = username
        self.number = number
        self.hand: list[Card] = []
        self.finished = False

    def add_card(self, card: Card) -> None:
        """Add one card to the player's hand."""
        self.hand.append(card)

    def add_cards(self, cards: list[Card]) -> None:
        """Add several cards to the player's hand."""
        self.hand.extend(cards)

    def remove_cards(self, indexes: list[int]) -> list[Card]:
        """Remove and return cards selected by one-based indexes."""
        if not indexes:
            raise ValueError(_("No cards selected"))

        if any(not isinstance(index, int) for index in indexes):
            raise ValueError(_("Card numbers must be integers"))

        if any(index <= 0 for index in indexes):
            raise ValueError(_("Card numbers must be positive"))

        if len(indexes) != len(set(indexes)):
            raise ValueError(_("Card numbers must be unique"))

        if any(index > len(self.hand) for index in indexes):
            raise ValueError(_("Card number is out of range"))

        selected_cards = [
            self.hand[index - 1]
            for index in indexes
        ]

        for index in sorted(indexes, reverse=True):
            del self.hand[index - 1]

        return selected_cards

    def discard_sets(self) -> list[str]:
        """Discard complete sets of four cards, except aces."""
        rank_counts = {}

        for card in self.hand:
            rank_counts[card.rank] = (
                rank_counts.get(card.rank, 0) + 1
            )

        discarded_ranks = []

        for rank in RANKS:
            if rank == "A":
                continue

            if rank_counts.get(rank, 0) == 4:
                discarded_ranks.append(rank)

        if discarded_ranks:
            self.hand[:] = [
                card
                for card in self.hand
                if card.rank not in discarded_ranks
            ]

        return discarded_ranks

    def card_count(self) -> int:
        """Return the number of cards in the player's hand."""
        return len(self.hand)

    def hand_text(self) -> str:
        """Return the numbered list of cards in the player's hand."""
        return "\n".join(
            f"{number}. {card}"
            for number, card in enumerate(self.hand, start=1)
        )

    def clear_hand(self) -> None:
        """Remove all cards from the player's hand."""
        self.hand.clear()


class Move:
    """Store information about the previous move."""

    def __init__(
        self,
        username: str,
        cards: list[Card],
        declared_rank: str,
    ) -> None:
        """Create a record of cards placed by one player."""
        self.username = username
        self.cards = list(cards)
        self.declared_rank = declared_rank


class Game:
    """Represent the current game state."""

    def __init__(self) -> None:
        """Create an empty game state."""
        self.players = {}

        self.player_order = []
        self.active_order = []
        self.finish_order = []

        self.deck = Deck()
        self.pile = []

        self.last_move = None
        self.declared_rank = None

        self.current_player_index = 0
        self.started = False
        self.pending_winner = None

    def start(self, usernames: list[str]) -> list[object]:
        """Start a new game."""
        if len(usernames) < 2 or len(usernames) > 4:
            raise ValueError(
                _("The number of players must be between 2 and 4")
            )

        if len(usernames) != len(set(usernames)):
            raise ValueError(_("Player names must be unique"))

        self.players.clear()

        self.player_order = list(usernames)
        self.active_order = list(usernames)
        self.finish_order = []

        self.pile = []
        self.last_move = None
        self.declared_rank = None
        self.pending_winner = None

        self.current_player_index = 0

        self.deck = Deck()
        self.deck.shuffle()

        for number, username in enumerate(usernames, start=1):
            self.players[username] = Player(
                username,
                number,
            )

        players = [
            self.players[username]
            for username in usernames
        ]

        self.deck.deal(players)

        self.started = True
        return [("prepare_turn",)]

    def stop(self) -> None:
        """Stop the current game and clear its state."""
        self.players.clear()

        self.player_order = []
        self.active_order = []
        self.finish_order = []

        self.deck = Deck()
        self.pile = []

        self.last_move = None
        self.declared_rank = None

        self.current_player_index = 0
        self.started = False
        self.pending_winner = None

    def current_player(self):
        """Return the player whose turn it is."""
        if not self.started:
            return None

        if not self.active_order:
            return None

        return self.active_order[self.current_player_index]

    def next_player(self):
        """Move the turn to the next active player."""
        if not self.started:
            return None

        if not self.active_order:
            return None

        self.current_player_index += 1

        if self.current_player_index >= len(self.active_order):
            self.current_player_index = 0

        return self.current_player()

    def player_after(self, username):
        """Return the active player after the given player."""
        if not self.active_order:
            return None

        if username not in self.active_order:
            return None

        player_index = self.active_order.index(username)
        next_index = player_index + 1

        if next_index >= len(self.active_order):
            next_index = 0

        next_username = self.active_order[next_index]

        return next_username

    def remove_active_player(self, username) -> None:
        """Remove a player from the active turn order."""
        if username not in self.active_order:
            return

        removed_index = self.active_order.index(username)

        self.active_order.pop(removed_index)

        if not self.active_order:
            self.current_player_index = 0
            return

        if removed_index < self.current_player_index:
            self.current_player_index -= 1

        if self.current_player_index >= len(self.active_order):
            self.current_player_index = 0

    def only_aces_remain(self) -> bool:
        """Return True when all remaining cards are aces."""
        remaining_cards = []

        for username in self.active_order:
            player = self.players[username]
            remaining_cards.extend(player.hand)

        remaining_cards.extend(self.pile)

        if not remaining_cards:
            return False

        for card in remaining_cards:
            if card.rank != "A":
                return False

        return True

    def game_should_end(self) -> bool:
        """Return True when the game cannot continue."""
        if not self.started:
            return False

        if self.pending_winner is not None:
            return False

        if len(self.active_order) <= 1:
            return True

        if self.only_aces_remain():
            return True

        return False

    def prepare_turn(self) -> list[object]:
        """Prepare the current player for the next turn."""
        events = []

        if not self.started:
            return events

        while self.active_order:
            if self.game_should_end():
                if self.only_aces_remain():
                    events.append(
                        (
                            "broadcast",
                            _(
                                "Only aces remain in the game. "
                                "The game is over."
                            ),
                        )
                    )
                else:
                    last_username = self.active_order[0]
                    last_player = self.players[last_username]

                    events.append(
                        (
                            "broadcast",
                            _(
                                "Only one player remains with cards: "
                                "player #{} {}."
                            ),
                            last_player.number,
                            last_player.username,
                        )
                    )

                events.append(("game_over",))
                return events

            username = self.current_player()

            if username is None:
                return events

            player = self.players[username]
            discarded_ranks = player.discard_sets()

            for rank in discarded_ranks:
                events.append(
                    (
                        "broadcast",
                        _(
                            "Player #{} {} automatically discarded "
                            "four cards of rank {}."
                        ),
                        player.number,
                        player.username,
                        rank,
                    )
                )

            if player.card_count() > 0:
                events.append(
                    (
                        "broadcast",
                        _("It is now player #{} {}'s turn."),
                        player.number,
                        player.username,
                    )
                )

                events.append(
                    (
                        "private",
                        player.username,
                        _("It is your turn.\n\nYour cards:\n{}"),
                        player.hand_text(),
                    )
                )

                if self.pending_winner is not None:
                    events.append(
                        (
                            "private",
                            player.username,
                            _(
                                "The previous player placed the last cards. "
                                "You must use not."
                            ),
                        )
                    )

                elif not self.pile:
                    events.append(
                        (
                            "private",
                            player.username,
                            _(
                                "You start a new round.\n"
                                "Choose a rank with play.\n"
                                "Available ranks: 6 7 8 9 10 J D K."
                            ),
                        )
                    )

                else:
                    events.append(
                        (
                            "private",
                            player.username,
                            _(
                                "Declared rank: {}.\n"
                                "Choose believe or not."
                            ),
                            self.declared_rank,
                        )
                    )

                return events

            player.finished = True

            if player.username not in self.finish_order:
                self.finish_order.append(player.username)

            place = len(self.finish_order)

            events.append(
                (
                    "broadcast",
                    _(
                        "Player #{} {} has no cards and "
                        "finished the game. Place: {}."
                    ),
                    player.number,
                    player.username,
                    place,
                )
            )

            self.remove_active_player(player.username)

        events.append(("game_over",))

        return events

    def play(self, args: str, username: str,) -> tuple[object, list[object]]:
        """Place selected cards and start a new round."""
        if not self.started:
            return _("Game has not started."), []

        current_username = self.current_player()

        if current_username != username:
            return _("It is not your turn."), []

        current_player = self.players[current_username]

        if self.pile:
            return (
                _("The pile is not empty. Use believe or not."),
                [],
            )

        try:
            data = shlex.split(args)
        except ValueError:
            return _("Invalid command format."), []

        if not data:
            return _("Specify a rank and card numbers."), []

        declared_rank = data[0]

        if declared_rank == "A":
            return _("Aces cannot be declared."), []

        if declared_rank not in DECLARABLE_RANKS:
            return _("Invalid declared rank."), []

        try:
            indexes = [
                int(value)
                for value in data[1:]
            ]
        except ValueError:
            return _("Card numbers must be integers."), []

        try:
            cards = current_player.remove_cards(indexes)
        except ValueError as error:
            return str(error), []

        self.pile.extend(cards)

        self.last_move = Move(username, cards, declared_rank,)

        self.declared_rank = declared_rank

        if current_player.card_count() == 0:
            self.pending_winner = username

        self.next_player()

        cards_number = len(cards)

        singular, plural = ngettext(
            "Player #{} {} placed {} card of rank {}.",
            "Player #{} {} placed {} cards of rank {}.",
            cards_number,
        )

        events = [
            (
                "broadcast_ngettext",
                singular,
                plural,
                cards_number,
                (
                    current_player.number,
                    current_player.username,
                    cards_number,
                    declared_rank,
                ),
            ),
            ("sleep", 1),
            ("prepare_turn",),
        ]

        return "", events

    def believe(
            self, args: str, username: str,
            ) -> tuple[object, list[object]]:
        """Place cards while keeping the declared rank."""
        current_username = self.current_player()

        if current_username != username:
            return _("It is not your turn."), []

        current_player = self.players[current_username]

        if not self.pile:
            return _("The pile is empty. Use play."), []

        if self.declared_rank is None:
            return _("There is no declared rank."), []

        if self.pending_winner is not None:
            return (
                _(
                    "The previous player placed the last cards. "
                    "You must use not."
                ),
                [],
            )

        try:
            values = shlex.split(args)
            indexes = [int(value) for value in values]
        except ValueError:
            return _("Card numbers must be integers."), []

        try:
            cards = current_player.remove_cards(indexes)
        except ValueError as error:
            return str(error), []

        self.pile.extend(cards)

        self.last_move = Move(
            username,
            cards,
            self.declared_rank,
        )

        if current_player.card_count() == 0:
            self.pending_winner = username

        self.next_player()

        cards_number = len(cards)

        singular, plural = ngettext(
            "Player #{} {} believed and placed "
            "{} more card of rank {}.",
            "Player #{} {} believed and placed "
            "{} more cards of rank {}.",
            cards_number,
        )

        events = [
            (
                "broadcast_ngettext",
                singular,
                plural,
                cards_number,
                (
                    current_player.number,
                    current_player.username,
                    cards_number,
                    self.declared_rank,
                ),
            ),
            ("sleep", 1),
            ("prepare_turn",),
        ]

        return "", events

    def not_believe(
            self, args: str, username: str,
            ) -> tuple[object, list[object]]:
        """Check one card from the previous move."""
        current_username = self.current_player()

        if current_username != username:
            return _("It is not your turn."), []

        if self.last_move is None:
            return _("There is no previous move."), []

        try:
            values = shlex.split(args)
        except ValueError:
            return _("Invalid command format."), []

        if len(values) != 1:
            return _("Choose exactly one card."), []

        try:
            index = int(values[0])
        except ValueError:
            return _("Card number must be an integer."), []

        if index <= 0 or index > len(self.last_move.cards):
            return _("Card number is out of range."), []

        checked_card = self.last_move.cards[index - 1]
        previous_username = self.last_move.username
        declared_rank = self.declared_rank
        pile_size = len(self.pile)

        events = [
            (
                "broadcast",
                _("Checked card #{}: {}."),
                index,
                str(checked_card),
            )
        ]

        if checked_card.rank == declared_rank:
            taker_username = username

            events.append(
                (
                    "broadcast",
                    _("The checked card matches rank {}."),
                    declared_rank,
                )
            )

            if self.pending_winner == previous_username:
                previous_player = self.players[previous_username]
                previous_player.finished = True

                if previous_username not in self.finish_order:
                    self.finish_order.append(previous_username)

                events.append(
                    (
                        "broadcast",
                        _("Player #{} {} finished the game. Place: {}."),
                        previous_player.number,
                        previous_player.username,
                        len(self.finish_order),
                    )
                )

                self.remove_active_player(previous_username)

        else:
            taker_username = previous_username

            events.append(
                (
                    "broadcast",
                    _("The checked card does not match rank {}."),
                    declared_rank,
                )
            )

        taker = self.players[taker_username]
        taker.add_cards(self.pile)

        singular, plural = ngettext(
            "Player #{} {} takes {} card.",
            "Player #{} {} takes {} cards.",
            pile_size,
        )

        events.append(
            (
                "broadcast_ngettext",
                singular,
                plural,
                pile_size,
                (
                    taker.number,
                    taker.username,
                    pile_size,
                ),
            )
        )

        self.pile.clear()
        self.last_move = None
        self.declared_rank = None
        self.pending_winner = None

        if taker_username in self.active_order:
            taker_index = self.active_order.index(taker_username)
            self.current_player_index = (
                taker_index + 1
            ) % len(self.active_order)

        events.append(("sleep", 1))
        events.append(("prepare_turn",))

        return "", events

    def rules(self) -> tuple[object, list[object]]:
        """Return the game rules."""
        text = _(
            "GAME RULES\n\n"
            "1. The game has from 2 to 4 players.\n"
            "2. Players have 10 seconds to accept an invitation.\n"
            "3. A deck of 36 cards is used.\n"
            "4. The first player chooses a rank from 6 to K.\n"
            "5. Aces cannot be declared.\n"
            "6. The believe command adds cards to the pile.\n"
            "7. The not command checks one card from the last move.\n"
            "8. The loser of the check takes the whole pile.\n"
            "9. The player who takes the pile skips a turn.\n"
            "10. Four cards of one rank are discarded automatically.\n"
            "11. Four aces are not discarded automatically.\n"
            "12. A player's last cards must be checked.\n"
            "13. A player without cards finishes the game.\n"
            "14. The game ends when only aces remain."
        )

        return text, []

    def process(self, command: str, username: str,
                ) -> tuple[object, list[object]]:
        """Process one game command."""
        try:
            data = shlex.split(command)
        except ValueError:
            return _("Invalid command format."), []

        if not data:
            return "", []

        command_name = data[0]
        args = " ".join(data[1:])

        if command_name == "rules":
            if args:
                return _("The rules command takes no arguments."), []

            return self.rules()

        if command_name == "play":
            return self.play(args, username)

        if command_name == "believe":
            return self.believe(args, username)

        if command_name == "not":
            return self.not_believe(args, username)

        return _("Invalid command."), []
