import argparse

from docs_rag import __version__


def main() -> None:
    parser = argparse.ArgumentParser(prog="docs-rag")
    parser.add_argument("--version", action="version", version=__version__)
    parser.parse_args()


if __name__ == "__main__":
    main()
