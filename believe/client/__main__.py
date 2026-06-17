"""Terminal client shell for Believe-It-or-Not."""

import cmd
import sys
from asyncio import StreamReader
from asyncio import StreamWriter


class CmdBelieve(cmd.Cmd):
    """Believe-It-or-Not command line."""

    prompt = "-> "

    def __init__(
        self,
        reader: StreamReader | None = None,
        writer: StreamWriter | None = None,
        username: str = "",
    ) -> None:
        """Create command shell."""
        super().__init__()
        self.reader = reader
        self.writer = writer
        self.username = username

    def request(self, command: str) -> None:
        """Send one command line to the server."""
        if self.writer is None:
            print("Client is not connected.")
            return

        self.writer.write(f"{command}\n".encode())

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


def main() -> None:
    """Run client command shell without network connection yet."""
    username = ""

    if len(sys.argv) > 1:
        username = sys.argv[1]

    CmdBelieve(username=username).cmdloop()


if __name__ == "__main__":
    main()
