import sys

from core.engine import Engine


def main():
    # Quick level jump: python main.py level_002
    level = sys.argv[1] if len(sys.argv) > 1 else None
    game = Engine(start_level=level)
    game.run()


if __name__ == "__main__":
    main()
