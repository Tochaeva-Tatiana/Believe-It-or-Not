"""Tests for the Believe-It-or-Not terminal client."""

import unittest
from unittest import mock

from believe.client import __main__ as client_main
from believe.common import DECLARABLE_RANKS


class FakeWriter:
    """Small stream writer replacement for client tests."""

    def __init__(self) -> None:
        """Create an empty fake writer."""
        self.data = bytearray()
        self.drained = False

    def write(self, data: bytes) -> None:
        """Store written bytes."""
        self.data.extend(data)

    async def drain(self) -> None:
        """Mark that the writer has been drained."""
        self.drained = True


class ClientCommandTest(unittest.TestCase):
    """Test terminal command behavior."""

    def setUp(self) -> None:
        """Create a command shell for each test."""
        self.shell = client_main.CmdBelieve()

    def test_basic_commands_send_expected_strings(self) -> None:
        """Check simple client commands."""
        commands = [
            (self.shell.do_start, "", "start"),
            (self.shell.do_yes, "", "yes"),
            (self.shell.do_rules, "", "rules"),
            (self.shell.do_play, "K 1 2", "play K 1 2"),
            (self.shell.do_believe, "3 4", "believe 3 4"),
            (self.shell.do_not, "5", "not 5"),
            (self.shell.do_locale, "ru", "locale ru"),
        ]

        for method, argument, expected in commands:
            with self.subTest(command=expected):
                with mock.patch.object(self.shell, "request") as request:
                    method(argument)

                request.assert_called_once_with(expected)

    def test_quit_sends_command_and_stops_shell(self) -> None:
        """Check that quit sends a command and exits cmdloop."""
        with mock.patch.object(self.shell, "request") as request:
            result = self.shell.do_quit("")

        request.assert_called_once_with("quit")
        self.assertTrue(result)

    def test_start_with_argument_prints_usage(self) -> None:
        """Check that start rejects arguments."""
        with mock.patch("builtins.print") as print_mock:
            with mock.patch.object(self.shell, "request") as request:
                self.shell.do_start("extra")

        print_mock.assert_called_once_with("Usage: start")
        request.assert_not_called()

    def test_yes_with_argument_prints_usage(self) -> None:
        """Check that yes rejects arguments."""
        with mock.patch("builtins.print") as print_mock:
            with mock.patch.object(self.shell, "request") as request:
                self.shell.do_yes("extra")

        print_mock.assert_called_once_with("Usage: yes")
        request.assert_not_called()

    def test_rules_with_argument_prints_usage(self) -> None:
        """Check that rules rejects arguments."""
        with mock.patch("builtins.print") as print_mock:
            with mock.patch.object(self.shell, "request") as request:
                self.shell.do_rules("extra")

        print_mock.assert_called_once_with("Usage: rules")
        request.assert_not_called()

    def test_play_without_arguments_prints_usage(self) -> None:
        """Check that empty play command prints usage."""
        with mock.patch("builtins.print") as print_mock:
            with mock.patch.object(self.shell, "request") as request:
                self.shell.do_play("")

        print_mock.assert_called_once_with(
            "Usage: play <rank> <card numbers>",
        )
        request.assert_not_called()

    def test_play_without_cards_prints_usage(self) -> None:
        """Check that incomplete play command prints usage."""
        with mock.patch("builtins.print") as print_mock:
            with mock.patch.object(self.shell, "request") as request:
                self.shell.do_play("K")

        print_mock.assert_called_once_with(
            "Usage: play <rank> <card numbers>",
        )
        request.assert_not_called()

    def test_play_with_bad_rank_prints_usage(self) -> None:
        """Check that play rejects undeclarable rank."""
        with mock.patch("builtins.print") as print_mock:
            with mock.patch.object(self.shell, "request") as request:
                self.shell.do_play("A 1 2")

        print_mock.assert_called_once_with(
            "Rank must be one of: " + " ".join(DECLARABLE_RANKS),
        )
        request.assert_not_called()

    def test_believe_without_cards_prints_usage(self) -> None:
        """Check that incomplete believe command prints usage."""
        with mock.patch("builtins.print") as print_mock:
            with mock.patch.object(self.shell, "request") as request:
                self.shell.do_believe("")

        print_mock.assert_called_once_with(
            "Usage: believe <card numbers>",
        )
        request.assert_not_called()

    def test_not_without_card_prints_usage(self) -> None:
        """Check that incomplete not command prints usage."""
        with mock.patch("builtins.print") as print_mock:
            with mock.patch.object(self.shell, "request") as request:
                self.shell.do_not("")

        print_mock.assert_called_once_with(
            "Usage: not <card number>",
        )
        request.assert_not_called()

    def test_not_with_many_cards_prints_usage(self) -> None:
        """Check that not accepts exactly one card number."""
        with mock.patch("builtins.print") as print_mock:
            with mock.patch.object(self.shell, "request") as request:
                self.shell.do_not("1 2")

        print_mock.assert_called_once_with(
            "Usage: not <card number>",
        )
        request.assert_not_called()

    def test_bad_locale_prints_usage(self) -> None:
        """Check that unknown locale is rejected by the client."""
        with mock.patch("builtins.print") as print_mock:
            with mock.patch.object(self.shell, "request") as request:
                self.shell.do_locale("de")

        print_mock.assert_called_once_with("Usage: locale <en|ru|ru-2>")
        request.assert_not_called()

    def test_empty_line_does_not_repeat_previous_command(self) -> None:
        """Check that an empty line is ignored."""
        with mock.patch.object(self.shell, "request") as request:
            self.shell.do_start("")
            request.reset_mock()
            self.shell.emptyline()

        request.assert_not_called()

    def test_complete_play_suggests_declarable_ranks(self) -> None:
        """Check rank completion for the play command."""
        completions = self.shell.complete_play(
            "",
            "play ",
            len("play "),
            len("play "),
        )

        self.assertEqual(completions, list(DECLARABLE_RANKS))
        self.assertNotIn("A", completions)

    def test_complete_play_filters_by_prefix(self) -> None:
        """Check that play completion respects typed prefix."""
        completions = self.shell.complete_play(
            "K",
            "play K",
            len("play "),
            len("play K"),
        )

        self.assertEqual(completions, ["K"])

    def test_complete_locale_suggests_locales(self) -> None:
        """Check locale completion."""
        completions = self.shell.complete_locale(
            "",
            "locale ",
            len("locale "),
            len("locale "),
        )

        self.assertEqual(completions, ["en", "ru", "ru-2"])

    def test_complete_locale_filters_by_prefix(self) -> None:
        """Check that locale completion respects typed prefix."""
        completions = self.shell.complete_locale(
            "ru",
            "locale ru",
            len("locale "),
            len("locale ru"),
        )

        self.assertEqual(completions, ["ru", "ru-2"])

    def test_documentation_opens_project_documentation(self) -> None:
        """Check that documentation opens generated HTML."""
        with mock.patch.object(client_main.Path, "exists", return_value=True):
            with mock.patch.object(
                client_main.webbrowser,
                "open",
            ) as open_page:
                self.shell.do_documentation("")

        open_page.assert_called_once()
        opened_uri = open_page.call_args.args[0]

        self.assertTrue(opened_uri.startswith("file:"))
        self.assertTrue(
            opened_uri.endswith("/believe/documentation/index.html"),
        )

    def test_documentation_with_argument_prints_usage(self) -> None:
        """Check that documentation rejects arguments."""
        with mock.patch("builtins.print") as print_mock:
            with mock.patch.object(
                client_main.webbrowser,
                "open",
            ) as open_page:
                self.shell.do_documentation("extra")

        print_mock.assert_called_once_with("Usage: documentation")
        open_page.assert_not_called()

    def test_missing_documentation_prints_message(self) -> None:
        """Check message when documentation is not built."""
        with mock.patch.object(client_main.Path, "exists", return_value=False):
            with mock.patch.object(
                client_main.webbrowser,
                "open",
            ) as open_page:
                with mock.patch("builtins.print") as print_mock:
                    self.shell.do_documentation("")

        print_mock.assert_called_once_with("Documentation is not built yet.")
        open_page.assert_not_called()


class ClientNetworkTest(unittest.IsolatedAsyncioTestCase):
    """Test low-level client network helpers."""

    async def test_send_command_writes_line_to_server(self) -> None:
        """Check that send_command writes one protocol line."""
        writer = FakeWriter()
        shell = client_main.CmdBelieve(writer=writer)

        await shell.send_command("start")

        self.assertEqual(writer.data, b"start\n")
        self.assertTrue(writer.drained)

    async def test_send_command_without_writer_prints_message(self) -> None:
        """Check message when shell is not connected."""
        shell = client_main.CmdBelieve(writer=None)

        with mock.patch("builtins.print") as print_mock:
            await shell.send_command("start")

        print_mock.assert_called_once_with("Client is not connected.")


if __name__ == "__main__":
    unittest.main()
