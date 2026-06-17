"""Asynchronous server entry point for Believe-It-or-Not."""

import asyncio
from asyncio import StreamReader
from asyncio import StreamWriter

from believe.common import HOST
from believe.common import MAX_PLAYERS
from believe.common import PORT


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

    async def send_line(
        self,
        writer: StreamWriter,
        message: str,
    ) -> None:
        """Send one text line to a client."""
        writer.write(f"{message}\n".encode())
        await writer.drain()

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
            if username in self.clients:
                self.clients.pop(username, None)
                self.locales.pop(username, None)

            writer.close()
            await writer.wait_closed()

    async def read_username(self, reader: StreamReader) -> str:
        """Read username from the first client line."""
        data = await reader.readline()

        if not data:
            return ""

        return data.decode().strip()

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

            await self.send_line(
                writer,
                f"Server skeleton received: {command}",
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
