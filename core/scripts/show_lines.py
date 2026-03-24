import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=200)
    args = parser.parse_args()

    lines = Path(args.path).read_text(encoding="utf-8").splitlines()
    start = max(1, args.start)
    end = min(len(lines), args.end)
    for i in range(start, end + 1):
        print(f"{i:4d}: {lines[i - 1]}")


if __name__ == "__main__":
    main()
