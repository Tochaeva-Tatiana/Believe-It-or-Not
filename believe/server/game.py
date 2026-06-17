"""Game objects for Believe-It-or-Not."""

import random

from believe.common import RANKS, SUITS


class Card:
    """Represent one playing card."""

    def __init__(self, suit: str, rank: str) -> None:
        """Create a card with the given suit and rank."""
        if suit not in SUITS:
            raise ValueError("Unknown suit")

        if rank not in RANKS:
            raise ValueError("Unknown rank")

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
            raise IndexError("The deck is empty")

        return self.cards.pop()


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
            raise ValueError("No cards selected")

        if any(not isinstance(index, int) for index in indexes):
            raise ValueError("Card numbers must be integers")

        if any(index <= 0 for index in indexes):
            raise ValueError("Card numbers must be positive")

        if len(indexes) != len(set(indexes)):
            raise ValueError("Card numbers must be unique")

        if any(index > len(self.hand) for index in indexes):
            raise ValueError("Card number is out of range")

        selected_cards = [
            self.hand[index - 1]
            for index in indexes
        ]

        for index in sorted(indexes, reverse=True):
            del self.hand[index - 1]

        return selected_cards

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
