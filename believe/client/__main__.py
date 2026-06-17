"""Terminal client shell for Believe-It-or-Not."""

import asyncio
import cmd
import shlex
import sys
import webbrowser
from asyncio import StreamReader
from asyncio import StreamWriter
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path

from believe.common import DECLARABLE_RANKS
from believe.common import HOST
from believe.common import PORT


class CmdBelieve(cmd.Cmd):
    """Believe-It-or-Not command line."""

    prompt = "-> "

    def __init__(
        self,
        reader: StreamReader | None = None,
        writer: StreamWriter | None = None,
        username: str = "",
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Create command shell."""
        super().__init__()
        self.reader = reader
        self.writer = writer
        self.username = username
        self.loop = loop

    async def send_command(self, command: str) -> None:
        """Send one command line to the server asynchronously."""
        if self.writer is None:
            print("Client is not connected.")
            return

        self.writer.write(f"{command}\n".encode())
        await self.writer.drain()

    def request(self, command: str) -> None:
        """Send one command line to the server."""
        if self.writer is None or self.loop is None:
            print("Client is not connected.")
            return

        future = asyncio.run_coroutine_threadsafe(
            self.send_command(command),
            self.loop,
        )

        try:
            future.result(timeout=1)
        except FutureTimeoutError:
            print("Server did not accept command in time.")
        except (ConnectionError, RuntimeError, OSError):
            print("Connection to server is lost.")

    def do_start(self, arg: str) -> None:
        """Start invitation for a new game."""
        if arg.strip():
            print("Usage: start")
            return

        self.request("start")

    def do_yes(self, arg: str) -> None:
        """Accept game invitation."""
        if arg.strip():
            print("Usage: yes")
            return

        self.request("yes")

    def do_rules(self, arg: str) -> None:
        """Ask server to show game rules."""
        if arg.strip():
            print("Usage: rules")
            return

        self.request("rules")

    def do_play(self, arg: str) -> None:
        """Put cards and declare a rank."""
        try:
            arguments = shlex.split(arg)
        except ValueError as error:
            print(error)
            return

        if not arguments:
            print("Usage: play <rank> [card numbers]")
            return

        rank = arguments[0]

        if rank not in DECLARABLE_RANKS:
            print("Rank must be one of: " + " ".join(DECLARABLE_RANKS))
            return

        if len(arguments) == 1:
            indexes = input("Enter card numbers separated by spaces: ")
            indexes = indexes.strip()

            if not indexes:
                print("Usage: play <rank> <card numbers>")
                return

            self.request(f"play {rank} {indexes}")
            return

        self.request("play " + " ".join(arguments))

    def do_believe(self, arg: str) -> None:
        """Believe previous player and put more cards."""
        try:
            arguments = shlex.split(arg)
        except ValueError as error:
            print(error)
            return

        if not arguments:
            indexes = input("Enter card numbers separated by spaces: ")
            indexes = indexes.strip()

            if not indexes:
                print("Usage: believe <card numbers>")
                return

            self.request(f"believe {indexes}")
            return

        self.request("believe " + " ".join(arguments))

    def do_not(self, arg: str) -> None:
        """Doubt previous player and check one card."""
        try:
            arguments = shlex.split(arg)
        except ValueError as error:
            print(error)
            return

        if not arguments:
            index = input("Choose one card number to check: ")
            index = index.strip()

            if not index:
                print("Usage: not <card number>")
                return

            self.request(f"not {index}")
            return

        self.request("not " + " ".join(arguments))

    def do_locale(self, arg: str) -> None:
        """Change interface locale."""
        locale = arg.strip()

        if locale not in ("en", "ru", "ru-2"):
            print("Usage: locale <en|ru|ru-2>")
            return

        self.request(f"locale {locale}")

    def do_documentation(self, arg: str) -> None:
        """Open local project documentation."""
        if arg.strip():
            print("Usage: documentation")
            return

        index_path = (
            Path(__file__).resolve().parents[1]
            / "documentation"
            / "index.html"
        )

        if not index_path.exists():
            print("Documentation is not built yet.")
            return

        webbrowser.open(index_path.as_uri())

    def complete_play(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        """Complete rank for play command."""
        arguments = line[:begidx].split()

        if len(arguments) == 1:
            return [
                rank
                for rank in DECLARABLE_RANKS
                if rank.startswith(text)
            ]

        return []

    def complete_locale(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
    ) -> list[str]:
        """Complete locale command argument."""
        locales = ("en", "ru", "ru-2")

        return [
            locale
            for locale in locales
            if locale.startswith(text)
        ]

    def do_quit(self, arg: str) -> bool:
        """Close the client session."""
        if arg.strip():
            print("Usage: quit")
            return False

        self.request("quit")
        return True

    def do_EOF(self, arg: str) -> bool:
        """Close the client session on EOF."""
        print()
        self.request("quit")
        return True


async def receive_messages(reader: StreamReader) -> None:
    """Print messages received from the server."""
    while True:
        data = await reader.readline()

        if not data:
            print("\nConnection closed by server.")
            return

        message = data.decode().rstrip("\r\n")
        print(f"\n{message}")


async def connect(username: str) -> tuple[StreamReader, StreamWriter] | None:
    """Connect to server and register username."""
    try:
        reader, writer = await asyncio.open_connection(HOST, PORT)
    except OSError as error:
        print(f"Cannot connect to server: {error}")
        return None

    writer.write(f"{username}\n".encode())
    await writer.drain()

    data = await reader.readline()

    if not data:
        print("Server closed connection.")
        writer.close()
        await writer.wait_closed()
        return None

    answer = data.decode().rstrip("\r\n")
    print(answer)

    if answer != "OK":
        writer.close()
        await writer.wait_closed()
        return None

    return reader, writer


async def amain() -> None:
    """Run connected client command shell."""
    if len(sys.argv) != 2 or not sys.argv[1]:
        print("Usage: python3 -m believe.client <username>")
        return

    username = sys.argv[1]
    connection = await connect(username)

    if connection is None:
        return

    reader, writer = connection
    loop = asyncio.get_running_loop()
    shell = CmdBelieve(
        reader=reader,
        writer=writer,
        username=username,
        loop=loop,
    )
    receiver_task = asyncio.create_task(receive_messages(reader))

    try:
        await asyncio.to_thread(shell.cmdloop)
    finally:
        receiver_task.cancel()

        try:
            await receiver_task
        except asyncio.CancelledError:
            pass

        try:
            writer.close()
            await writer.wait_closed()
        except (ConnectionError, RuntimeError, OSError):
            pass


def main() -> None:
    """Run client command shell."""
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
