"""Asynchronous server entry point for Believe-It-or-Not."""

import asyncio
import gettext
from asyncio import StreamReader
from asyncio import StreamWriter
from pathlib import Path

from believe.common import HOST
from believe.common import INVITATION_TIMEOUT
from believe.common import MAX_PLAYERS
from believe.common import PORT


LOCALE_NAMES = {
    "en": None,
    "ru": "ru_RU",
    "ru-2": "ru_BY",
}


def create_game() -> object | None:
    """Create a game object when the game model is available."""
    try:
        from believe.server.game import Game
    except ImportError:
        return None

    return Game()


class Server:
    """Believe-It-or-Not asynchronous server."""

    def __init__(
        self,
        host: str = HOST,
        port: int = PORT,
    ) -> None:
        """Create server state."""
        self.host = host
        self.port = port
        self.game = create_game()
        self.clients: dict[str, StreamWriter] = {}
        self.locales: dict[str, str] = {}

        self.invitation_timeout = INVITATION_TIMEOUT
        self.invitation_owner: str | None = None
        self.accepted_players: list[str] = []
        self.invitation_task: asyncio.Task[None] | None = None
        self.invitation_deadline: float | None = None

    def game_started(self) -> bool:
        """Check whether a game is already running."""
        return bool(getattr(self.game, "started", False))

    def validate_username(self, username: str) -> str | None:
        """Return an error message if username cannot be registered."""
        if not username or any(char.isspace() for char in username):
            return "ERROR bad or busy username"

        if username in self.clients:
            return "ERROR bad or busy username"

        if len(self.clients) >= MAX_PLAYERS:
            return "ERROR server is full"

        if self.game_started():
            return "ERROR game already started"

        return None

    def invitation_active(self) -> bool:
        """Check whether invitation is active."""
        return self.invitation_owner is not None

    def reset_invitation(self) -> None:
        """Reset invitation state."""
        self.invitation_owner = None
        self.accepted_players = []
        self.invitation_deadline = None
        self.invitation_task = None

    def translation(self, username: str) -> gettext.NullTranslations:
        """Return translation object for one player."""
        locale = self.locales.get(username, "en")
        language = LOCALE_NAMES.get(locale)

        if language is None:
            return gettext.NullTranslations()

        localedir = Path(__file__).resolve().parent / "po"

        return gettext.translation(
            "believe_server",
            localedir=localedir,
            languages=[language],
            fallback=True,
        )

    def format_message(
        self,
        username: str,
        message: object,
        *args: object,
    ) -> str:
        """Translate and format one outgoing message."""
        text = self.translation(username).gettext(str(message))

        if args:
            text = text.format(*args)

        return text

    def format_plural_message(
        self,
        username: str,
        singular: object,
        plural: object,
        number: int,
        format_args: object,
    ) -> str:
        """Translate and format one plural message."""
        text = self.translation(username).ngettext(
            str(singular),
            str(plural),
            number,
        )

        if isinstance(format_args, tuple):
            return text.format(*format_args)

        if isinstance(format_args, list):
            return text.format(*format_args)

        return text.format(format_args)

    async def send_line(
        self,
        writer: StreamWriter,
        message: str,
    ) -> None:
        """Send one raw text line to a client."""
        writer.write(f"{message}\n".encode())
        await writer.drain()

    async def send_to(
        self,
        username: str,
        message: object,
        *args: object,
    ) -> None:
        """Send one translated message to a connected client."""
        writer = self.clients.get(username)

        if writer is None:
            return

        text = self.format_message(username, message, *args)
        await self.send_line(writer, text)

    async def send_plural_to(
        self,
        username: str,
        singular: object,
        plural: object,
        number: int,
        format_args: object,
    ) -> None:
        """Send one translated plural message to a connected client."""
        writer = self.clients.get(username)

        if writer is None:
            return

        text = self.format_plural_message(
            username,
            singular,
            plural,
            number,
            format_args,
        )
        await self.send_line(writer, text)

    async def broadcast_all(
        self,
        message: object,
        *args: object,
    ) -> None:
        """Send one translated message to all connected clients."""
        for username in list(self.clients):
            await self.send_to(username, message, *args)

    async def broadcast_game(
        self,
        message: object,
        *args: object,
    ) -> None:
        """Send one translated message to current game participants."""
        player_order = getattr(self.game, "player_order", [])

        for username in list(player_order):
            if username in self.clients:
                await self.send_to(username, message, *args)

    async def broadcast_game_plural(
        self,
        singular: object,
        plural: object,
        number: int,
        format_args: object,
    ) -> None:
        """Send one translated plural message to game participants."""
        player_order = getattr(self.game, "player_order", [])

        for username in list(player_order):
            if username in self.clients:
                await self.send_plural_to(
                    username,
                    singular,
                    plural,
                    number,
                    format_args,
                )

    async def start_invitation(self, username: str) -> None:
        """Start waiting for players."""
        if self.game_started():
            await self.send_to(username, "Игра уже началась.")
            return

        if self.invitation_active():
            await self.send_to(username, "Набор игроков уже идёт.")
            return

        if username not in self.clients:
            return

        loop = asyncio.get_running_loop()
        self.invitation_owner = username
        self.accepted_players = [username]
        self.invitation_deadline = loop.time() + self.invitation_timeout
        self.invitation_task = asyncio.create_task(self.wait_for_players())

        await self.send_to(
            username,
            "Приглашение отправлено. "
            "Ожидание игроков: 10 секунд.",
        )

        for player_name in list(self.clients):
            if player_name != username:
                await self.send_to(
                    player_name,
                    "Игрок {} приглашает вас в игру. "
                    "Введите yes в течение 10 секунд.",
                    username,
                )

    async def accept_invitation(self, username: str) -> None:
        """Accept active game invitation."""
        if not self.invitation_active():
            await self.send_to(username, "Сейчас нет активного приглашения.")
            return

        if self.invitation_deadline is not None:
            loop = asyncio.get_running_loop()

            if loop.time() > self.invitation_deadline:
                await self.send_to(
                    username,
                    "Сейчас нет активного приглашения.",
                )
                return

        if username == self.invitation_owner:
            await self.send_to(
                username,
                "Вы уже являетесь создателем этой игры.",
            )
            return

        if username in self.accepted_players:
            await self.send_to(
                username,
                "Вы уже присоединились к этой игре.",
            )
            return

        if len(self.accepted_players) >= MAX_PLAYERS:
            await self.send_to(
                username,
                "В игре уже участвуют четыре игрока.",
            )
            return

        self.accepted_players.append(username)
        player_number = len(self.accepted_players)

        await self.send_to(
            username,
            "Вы присоединились к игре как игрок №{}.",
            player_number,
        )

        for player_name in self.accepted_players:
            if player_name != username:
                await self.send_to(
                    player_name,
                    "Игрок №{} {} присоединился к игре.",
                    player_number,
                    username,
                )

        if len(self.accepted_players) == MAX_PLAYERS:
            if self.invitation_task is not None:
                self.invitation_task.cancel()

            await self.broadcast_all(
                "Набрано максимальное количество игроков. "
                "Игра начинается досрочно.",
            )
            await self.begin_game()

    async def wait_for_players(self) -> None:
        """Wait for players to accept invitation."""
        try:
            await asyncio.sleep(self.invitation_timeout)
        except asyncio.CancelledError:
            return

        if len(self.accepted_players) < 2:
            owner = self.invitation_owner

            if owner is not None:
                await self.send_to(
                    owner,
                    "Никто не присоединился. Игра не началась.",
                )

            await self.broadcast_all(
                "Набор игроков завершён без начала игры.",
            )
            self.reset_invitation()
            return

        await self.begin_game()

    async def begin_game(self) -> None:
        """Begin game with accepted players."""
        usernames = list(self.accepted_players)

        current_task = asyncio.current_task()

        if (
            self.invitation_task is not None
            and self.invitation_task is not current_task
        ):
            self.invitation_task.cancel()

        self.reset_invitation()

        if len(usernames) < 2:
            return

        if self.game is None or not hasattr(self.game, "start"):
            await self.broadcast_all(
                "Набор игроков завершён. "
                "Игровая модель ещё не готова.",
            )
            return

        events = self.game.start(usernames)

        await self.broadcast_game(
            "Игра начинается. Участники: {}",
            ", ".join(usernames),
        )

        await self.dispatch_events(events)

    async def dispatch_events(self, events: list[object]) -> None:
        """Dispatch game events returned by the game model."""
        event_queue = list(events)

        while event_queue:
            event = event_queue.pop(0)

            if not isinstance(event, tuple):
                continue

            if not event:
                continue

            event_name = event[0]

            if event_name == "broadcast":
                await self.broadcast_game(*event[1:])
                continue

            if event_name == "broadcast_ngettext":
                singular = event[1]
                plural = event[2]
                number = int(event[3])
                format_args = event[4]
                await self.broadcast_game_plural(
                    singular,
                    plural,
                    number,
                    format_args,
                )
                continue

            if event_name == "private":
                username = str(event[1])
                message = event[2]
                await self.send_to(username, message, *event[3:])
                continue

            if event_name == "sleep":
                await asyncio.sleep(float(event[1]))
                continue

            if event_name == "prepare_turn":
                if self.game is None or not hasattr(self.game, "prepare_turn"):
                    continue

                new_events = self.game.prepare_turn()
                event_queue.extend(new_events)
                continue

            if event_name == "game_over":
                if self.game is not None and hasattr(self.game, "stop"):
                    self.game.stop()
                continue

    async def unregister_client(self, username: str) -> None:
        """Remove disconnected client from server state."""
        if not username:
            return

        was_owner = username == self.invitation_owner
        was_accepted = username in self.accepted_players

        self.clients.pop(username, None)
        self.locales.pop(username, None)

        if was_owner:
            if self.invitation_task is not None:
                self.invitation_task.cancel()

            self.reset_invitation()
            await self.broadcast_all(
                "Создатель игры вышел. Набор игроков отменён.",
            )
            return

        if was_accepted:
            self.accepted_players = [
                player_name
                for player_name in self.accepted_players
                if player_name != username
            ]

    async def handle_client(
        self,
        reader: StreamReader,
        writer: StreamWriter,
    ) -> None:
        """Handle one connected client."""
        username = ""

        try:
            username = await self.read_username(reader)

            if not username:
                await self.send_line(writer, "ERROR bad or busy username")
                return

            error_message = self.validate_username(username)

            if error_message is not None:
                await self.send_line(writer, error_message)
                return

            self.clients[username] = writer
            self.locales[username] = "en"
            await self.send_line(writer, "OK")

            await self.handle_commands(username, reader, writer)
        finally:
            await self.unregister_client(username)

            writer.close()
            await writer.wait_closed()

    async def read_username(self, reader: StreamReader) -> str:
        """Read username from the first client line."""
        data = await reader.readline()

        if not data:
            return ""

        return data.decode().rstrip("\r\n")

    async def handle_commands(
        self,
        username: str,
        reader: StreamReader,
        writer: StreamWriter,
    ) -> None:
        """Read commands from one client."""
        while not reader.at_eof():
            data = await reader.readline()

            if not data:
                break

            command = data.decode().strip()

            if not command:
                continue

            if command == "quit":
                break

            if command == "start":
                await self.start_invitation(username)
                continue

            if command == "yes":
                await self.accept_invitation(username)
                continue

            await self.send_to(
                username,
                "Server skeleton received: {}",
                command,
            )

    async def run(self) -> None:
        """Run the server forever."""
        server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port,
        )

        async with server:
            await server.serve_forever()


def serve() -> None:
    """Start the Believe-It-or-Not server."""
    asyncio.run(Server().run())


if __name__ == "__main__":
    serve()
