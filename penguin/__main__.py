"""Entry point: python -m penguin"""

from penguin.app import MainApplication


def main() -> None:
    app = MainApplication()
    app.run()


if __name__ == "__main__":
    main()
