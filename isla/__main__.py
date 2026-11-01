import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(prog="isla", description="Isla — a dynamic island for Windows 11")
    ap.add_argument("command", nargs="?", default="run", choices=["run", "install-hooks", "uninstall-hooks"])
    ap.add_argument("--dry-run", action="store_true", help="install-hooks: print the resulting settings only")
    args = ap.parse_args()

    if args.command == "install-hooks":
        from . import hooks_install
        print(hooks_install.install(dry_run=args.dry_run))
        return 0
    if args.command == "uninstall-hooks":
        from . import hooks_install
        print(hooks_install.uninstall())
        return 0
    from .app import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
