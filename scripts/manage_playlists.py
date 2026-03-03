"""
Playlist management CLI.

Usage:
    python -m scripts.manage_playlists add <playlist_id>
    python -m scripts.manage_playlists remove <playlist_id>
    python -m scripts.manage_playlists list
"""

import sys


def cmd_add(playlist_id: str) -> None:
    from src.database import add_playlist
    from src.spotify import SpotifyClient

    client = SpotifyClient()
    client.authenticate()

    info = client.get_playlist_info(playlist_id)
    if info is None:
        print(f"Error: Playlist '{playlist_id}' not found or is private.")
        sys.exit(1)

    add_playlist(playlist_id, info["name"], info["owner_id"])
    print(f"Added: '{info['name']}' ({playlist_id})")


def cmd_remove(playlist_id: str) -> None:
    from src.database import deactivate_playlist

    deactivate_playlist(playlist_id)
    print(f"Removed playlist: {playlist_id}")


def cmd_list() -> None:
    from src.database import get_active_playlists

    playlists = get_active_playlists()
    if not playlists:
        print("No active playlists.")
        return

    print(f"\n{'ID':<25} Name")
    print("-" * 60)
    for p in playlists:
        print(f"{p['id']:<25} {p['name']}")
    print()


def main() -> None:
    usage = "Usage: python -m scripts.manage_playlists <add|remove|list> [playlist_id]"

    if len(sys.argv) < 2:
        print(usage)
        sys.exit(1)

    command = sys.argv[1]

    if command == "add":
        if len(sys.argv) != 3:
            print("Usage: python -m scripts.manage_playlists add <playlist_id>")
            sys.exit(1)
        cmd_add(sys.argv[2])

    elif command == "remove":
        if len(sys.argv) != 3:
            print("Usage: python -m scripts.manage_playlists remove <playlist_id>")
            sys.exit(1)
        cmd_remove(sys.argv[2])

    elif command == "list":
        cmd_list()

    else:
        print(f"Unknown command: '{command}'. Use add, remove, or list.")
        sys.exit(1)


if __name__ == "__main__":
    main()
