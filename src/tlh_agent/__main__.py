"""Entry point for TLH Agent CLI."""

from tlh_agent.app import TLHAgentApp


def main() -> None:
    """Run the TLH Agent application."""
    app = TLHAgentApp()
    app.run()


if __name__ == "__main__":
    main()
