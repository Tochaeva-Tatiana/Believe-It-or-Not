"""Tests for the Believe-It-or-Not asynchronous server."""

import asyncio
import multiprocessing
import socket
import time
import unittest
from unittest import mock

from believe.server import __main__ as server_main


HOST = "127.0.0.1"
SOCKET_TIMEOUT = 2.0
TEST_INVITATION_TIMEOUT = 0.05


class FakeWriter:
    """Small stream writer replacement for server tests."""

    def __init__(self) -> None:
        """Create an empty fake writer."""
        self.data = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        """Store written bytes."""
        self.data.extend(data)

    async def drain(self) -> None:
        """Pretend that buffered data was sent."""
        return

    def close(self) -> None:
        """Mark the writer as closed."""
        self.closed = True

    async def wait_closed(self) -> None:
        """Wait for the fake writer to close."""
        return

    def text(self) -> str:
        """Return all written text."""
        return self.data.decode()


class StubGame:
    """Small game model replacement for server tests."""

    def __init__(self) -> None:
        """Create a stopped game stub."""
        self.started = False
        self.stopped = False
        self.player_order: list[str] = []
        self.process_calls: list[tuple[str, str]] = []
        self.start_calls: list[list[str]] = []
        self.prepare_calls = 0

    def start(self, usernames: list[str]) -> list[object]:
        """Start the fake game."""
        self.started = True
        self.player_order = list(usernames)
        self.start_calls.append(list(usernames))
        return []

    def stop(self) -> None:
        """Stop the fake game."""
        self.started = False
        self.stopped = True

    def prepare_turn(self) -> list[object]:
        """Return one event produced during turn preparation."""
        self.prepare_calls += 1
        return [("broadcast", "Prepared turn.")]

    def process(
        self,
        command: str,
        username: str,
    ) -> tuple[object, list[object]]:
        """Store a game command and return a small response."""
        self.process_calls.append((command, username))
        return "Game answer.", [("private", username, "Private event.")]


def run_test_server(host: str, port: int, timeout: float) -> None:
    """Run a real server process for socket integration tests."""

    async def runner() -> None:
        server = server_main.Server(host=host, port=port)
        server.invitation_timeout = timeout
        await server.run()

    asyncio.run(runner())


def free_port() -> int:
    """Return a currently free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def read_line(sock: socket.socket) -> str:
    """Read one line from a socket."""
    data = bytearray()

    while not data.endswith(b"\n"):
        chunk = sock.recv(1)

        if not chunk:
            break

        data.extend(chunk)

    return data.decode().rstrip("\r\n")


def write_line(sock: socket.socket, text: str) -> None:
    """Write one command line to a socket."""
    sock.sendall(f"{text}\n".encode())


def wait_for_line(
    sock: socket.socket,
    expected: str,
    timeout: float = SOCKET_TIMEOUT,
) -> str:
    """Read socket lines until one contains the expected text."""
    deadline = time.monotonic() + timeout
    last_line = ""

    while time.monotonic() < deadline:
        try:
            line = read_line(sock)
        except socket.timeout:
            continue

        last_line = line

        if expected in line:
            return line

    raise AssertionError(
        f"Did not receive {expected!r}; last line was {last_line!r}"
    )


class ServerSocketTest(unittest.TestCase):
    """Test server registration and invitations through sockets."""

    def setUp(self) -> None:
        """Start a server process."""
        self.port = free_port()
        self.process = multiprocessing.Process(
            target=run_test_server,
            args=(HOST, self.port, TEST_INVITATION_TIMEOUT),
        )
        self.process.start()
        self.sockets: list[socket.socket] = []
        self.wait_until_server_accepts_connections()

    def tearDown(self) -> None:
        """Stop server process and close sockets."""
        for sock in self.sockets:
            try:
                sock.close()
            except OSError:
                pass

        self.process.terminate()
        self.process.join(timeout=1)

        if self.process.is_alive():
            self.process.kill()
            self.process.join(timeout=1)

    def wait_until_server_accepts_connections(self) -> None:
        """Wait until the child server process is listening."""
        deadline = time.monotonic() + SOCKET_TIMEOUT

        while time.monotonic() < deadline:
            try:
                with socket.create_connection(
                    (HOST, self.port),
                    timeout=0.1,
                ):
                    return
            except OSError:
                time.sleep(0.01)

        raise AssertionError("Server process did not start in time")

    def connect_client(self, username: str) -> tuple[socket.socket, str]:
        """Connect one test client and read the registration answer."""
        sock = socket.create_connection(
            (HOST, self.port),
            timeout=SOCKET_TIMEOUT,
        )
        sock.settimeout(SOCKET_TIMEOUT)
        self.sockets.append(sock)
        write_line(sock, username)
        return sock, read_line(sock)

    def test_registration_rejects_bad_and_duplicate_names(self) -> None:
        """Check registration success and bad name rejection."""
        _, answer = self.connect_client("ira")

        self.assertEqual(answer, "OK")

        _, answer = self.connect_client("ira")
        self.assertEqual(answer, "ERROR bad or busy username")

        _, answer = self.connect_client("")
        self.assertEqual(answer, "ERROR bad or busy username")

        _, answer = self.connect_client("bad name")
        self.assertEqual(answer, "ERROR bad or busy username")

    def test_fifth_client_is_rejected(self) -> None:
        """Check that only four clients can register."""
        for username in ("ira", "tanya", "anna", "maria"):
            _, answer = self.connect_client(username)
            self.assertEqual(answer, "OK")

        _, answer = self.connect_client("extra")
        self.assertEqual(answer, "ERROR server is full")

    def test_invitation_starts_game_after_timer_with_two_players(self) -> None:
        """Check start, yes, and delayed game start."""
        ira, answer = self.connect_client("ira")
        self.assertEqual(answer, "OK")
        tanya, answer = self.connect_client("tanya")
        self.assertEqual(answer, "OK")

        write_line(ira, "start")

        self.assertEqual(
            read_line(ira),
            "Invitation sent. Waiting for players: 10 seconds.",
        )
        self.assertIn(
            "Player ira invites you to join the game.",
            read_line(tanya),
        )

        write_line(tanya, "yes")

        self.assertEqual(
            read_line(tanya),
            "You joined the game as player #2.",
        )
        self.assertEqual(
            read_line(ira),
            "Player #2 tanya joined the game.",
        )

        self.assertIn(
            "The game starts. Players: ira, tanya",
            wait_for_line(ira, "The game starts. Players:"),
        )
        self.assertIn(
            "The game starts. Players: ira, tanya",
            wait_for_line(tanya, "The game starts. Players:"),
        )

    def test_invitation_without_second_player_does_not_start(self) -> None:
        """Check that a single player cannot start a game."""
        ira, answer = self.connect_client("ira")
        self.assertEqual(answer, "OK")

        write_line(ira, "start")

        self.assertEqual(
            read_line(ira),
            "Invitation sent. Waiting for players: 10 seconds.",
        )
        self.assertEqual(
            wait_for_line(ira, "Nobody joined."),
            "Nobody joined. The game did not start.",
        )
        self.assertEqual(
            wait_for_line(ira, "Player recruitment ended"),
            "Player recruitment ended without starting the game.",
        )

    def test_four_players_start_game_early(self) -> None:
        """Check that four accepted players start the game early."""
        players = []

        for username in ("ira", "tanya", "anna", "maria"):
            sock, answer = self.connect_client(username)
            self.assertEqual(answer, "OK")
            players.append(sock)

        write_line(players[0], "start")
        self.assertEqual(
            read_line(players[0]),
            "Invitation sent. Waiting for players: 10 seconds.",
        )

        for sock in players[1:]:
            self.assertIn("invites you", read_line(sock))

        for sock in players[1:]:
            write_line(sock, "yes")

        self.assertIn(
            "The game starts. Players:",
            wait_for_line(players[0], "The game starts. Players:"),
        )


class ServerUnitTest(unittest.IsolatedAsyncioTestCase):
    """Test server event routing without opening sockets."""

    async def asyncSetUp(self) -> None:
        """Create a server with fake clients."""
        self.server = server_main.Server()
        self.server.game = StubGame()
        self.ira_writer = FakeWriter()
        self.tanya_writer = FakeWriter()
        self.server.clients = {
            "ira": self.ira_writer,
            "tanya": self.tanya_writer,
        }
        self.server.locales = {
            "ira": "en",
            "tanya": "en",
        }
        self.server.game.player_order = ["ira", "tanya"]

    async def asyncTearDown(self) -> None:
        """Cancel pending invitation task if a test created one."""
        if self.server.invitation_task is not None:
            self.server.invitation_task.cancel()

            try:
                await self.server.invitation_task
            except asyncio.CancelledError:
                pass

    async def test_dispatch_events_sends_messages_and_stops_game(self) -> None:
        """Check all event kinds used by the game model."""
        events = [
            ("broadcast", "Broadcast {}.", "event"),
            ("broadcast_ngettext", "{} card", "{} cards", 2, (2,)),
            ("private", "ira", "Private {}.", "event"),
            ("sleep", 0),
            ("prepare_turn",),
            ("game_over",),
        ]

        await self.server.dispatch_events(events)

        ira_text = self.ira_writer.text()
        tanya_text = self.tanya_writer.text()

        self.assertIn("Broadcast event.\n", ira_text)
        self.assertIn("Broadcast event.\n", tanya_text)
        self.assertIn("2 cards\n", ira_text)
        self.assertIn("2 cards\n", tanya_text)
        self.assertIn("Private event.\n", ira_text)
        self.assertNotIn("Private event.\n", tanya_text)
        self.assertIn("Prepared turn.\n", ira_text)
        self.assertTrue(self.server.game.stopped)

    async def test_handle_game_command_calls_game_process(self) -> None:
        """Check that game commands are routed to Game.process()."""
        self.server.game.started = True

        await self.server.handle_game_command("ira", "play K 1 2")

        self.assertEqual(
            self.server.game.process_calls,
            [("play K 1 2", "ira")],
        )
        self.assertIn("Game answer.\n", self.ira_writer.text())
        self.assertIn("Private event.\n", self.ira_writer.text())

    async def test_game_command_before_start_is_rejected(self) -> None:
        """Check that play is rejected before the game starts."""
        self.server.game.started = False

        await self.server.handle_game_command("ira", "play K 1")

        self.assertEqual(self.server.game.process_calls, [])
        self.assertIn(
            "The game has not started yet.\n",
            self.ira_writer.text(),
        )

    async def test_non_participant_game_command_is_rejected(self) -> None:
        """Check that spectators cannot play in an active game."""
        self.server.game.started = True
        self.server.game.player_order = ["tanya"]

        await self.server.handle_game_command("ira", "play K 1")

        self.assertEqual(self.server.game.process_calls, [])
        self.assertIn(
            "You are not participating in the current game.\n",
            self.ira_writer.text(),
        )

    async def test_rules_command_is_passed_to_game_before_start(self) -> None:
        """Check that rules is available before the game starts."""
        self.server.game.started = False

        await self.server.handle_game_command("ira", "rules")

        self.assertEqual(
            self.server.game.process_calls,
            [("rules", "ira")],
        )

    async def test_locale_command_changes_player_locale(self) -> None:
        """Check server-side locale command handling."""
        await self.server.handle_locale_command("ira", "locale ru")

        self.assertEqual(self.server.locales["ira"], "ru")
        expected = self.server.format_message(
            "ira",
            "Locale changed to {}.",
            "ru",
        )
        self.assertIn(f"{expected}\n", self.ira_writer.text())

    async def test_unregister_regular_client_does_not_stop_game(self) -> None:
        """Check that non-participant disconnect does not stop a game."""
        self.server.game.started = True
        self.server.game.player_order = ["tanya"]
        self.server.clients["guest"] = FakeWriter()
        self.server.locales["guest"] = "en"

        await self.server.unregister_client("guest")

        self.assertNotIn("guest", self.server.clients)
        self.assertFalse(self.server.game.stopped)

    async def test_unregister_active_player_stops_game_for_others(
        self,
    ) -> None:
        """Check that active player disconnect stops the game."""
        self.server.game.started = True

        await self.server.unregister_client("ira")

        self.assertNotIn("ira", self.server.clients)
        self.assertTrue(self.server.game.stopped)
        self.assertIn(
            "Player ira disconnected. The game has been stopped.\n",
            self.tanya_writer.text(),
        )

    async def test_validate_username_errors(self) -> None:
        """Check every username validation error."""
        self.assertEqual(
            self.server.validate_username(""),
            "ERROR bad or busy username",
        )
        self.server.clients["taken"] = FakeWriter()
        self.assertEqual(
            self.server.validate_username("taken"),
            "ERROR bad or busy username",
        )
        self.server.clients.update({
            "anna": FakeWriter(),
            "maria": FakeWriter(),
        })
        self.assertEqual(
            self.server.validate_username("extra"),
            "ERROR server is full",
        )
        self.server.clients.clear()
        self.server.game.started = True
        self.assertEqual(
            self.server.validate_username("extra"),
            "ERROR game already started",
        )

    async def test_plural_format_argument_shapes(self) -> None:
        """Check list and scalar plural formatting arguments."""
        self.assertEqual(
            self.server.format_plural_message(
                "ira", "{} card", "{} cards", 2, [2]
            ),
            "2 cards",
        )
        self.assertEqual(
            self.server.format_plural_message(
                "ira", "{} card", "{} cards", 2, 2
            ),
            "2 cards",
        )

    async def test_invitation_workflow_and_error_branches(self) -> None:
        """Check invitation creation, acceptance, expiry, and start."""
        for username in ("anna", "maria", "extra"):
            self.server.clients[username] = FakeWriter()
            self.server.locales[username] = "en"

        await self.server.start_invitation("ira")
        await self.server.start_invitation("tanya")
        await self.server.accept_invitation("ira")
        await self.server.accept_invitation("tanya")
        await self.server.accept_invitation("tanya")
        await self.server.accept_invitation("anna")
        await self.server.accept_invitation("maria")

        self.assertEqual(
            self.server.game.start_calls,
            [["ira", "tanya", "anna", "maria"]],
        )
        self.assertFalse(self.server.invitation_active())

        await self.server.accept_invitation("extra")

        loop = asyncio.get_running_loop()
        self.server.invitation_owner = "ira"
        self.server.accepted_players = ["ira"]
        self.server.invitation_deadline = loop.time() - 1
        await self.server.accept_invitation("extra")

        self.server.accepted_players = ["ira", "tanya", "anna", "maria"]
        self.server.invitation_deadline = loop.time() + 1
        await self.server.accept_invitation("extra")

        self.server.game.started = True
        self.server.reset_invitation()
        await self.server.start_invitation("ira")

    async def test_wait_for_players_and_command_routing(self) -> None:
        """Check invitation timeout and all command routing branches."""
        self.server.invitation_timeout = 0
        self.server.invitation_owner = "ira"
        self.server.accepted_players = ["ira"]
        await self.server.wait_for_players()

        reader = asyncio.StreamReader()
        reader.feed_data(
            b"\nstart\nyes\nlocale ru\nrules\nunknown\nquit\n"
        )
        reader.feed_eof()

        with mock.patch.object(
            self.server,
            "start_invitation",
            new=mock.AsyncMock(),
        ) as start, mock.patch.object(
            self.server,
            "accept_invitation",
            new=mock.AsyncMock(),
        ) as accept, mock.patch.object(
            self.server,
            "handle_locale_command",
            new=mock.AsyncMock(),
        ) as locale, mock.patch.object(
            self.server,
            "handle_game_command",
            new=mock.AsyncMock(),
        ) as game_command:
            await self.server.handle_commands(
                "ira",
                reader,
                self.ira_writer,
            )

        start.assert_awaited_once_with("ira")
        accept.assert_awaited_once_with("ira")
        locale.assert_awaited_once_with("ira", "locale ru")
        game_command.assert_awaited_once_with("ira", "rules")
        self.assertIn("Unknown command: unknown", self.ira_writer.text())

    async def test_handle_client_registration_and_cleanup(self) -> None:
        """Check empty and successful client sessions."""
        empty_reader = asyncio.StreamReader()
        empty_reader.feed_eof()
        empty_writer = FakeWriter()
        await self.server.handle_client(empty_reader, empty_writer)
        self.assertIn("ERROR bad or busy username", empty_writer.text())
        self.assertTrue(empty_writer.closed)

        reader = asyncio.StreamReader()
        reader.feed_data(b"guest\nquit\n")
        reader.feed_eof()
        writer = FakeWriter()
        await self.server.handle_client(reader, writer)

        self.assertIn("OK\n", writer.text())
        self.assertNotIn("guest", self.server.clients)
        self.assertTrue(writer.closed)


if __name__ == "__main__":
    unittest.main()
