#!/bin/sh
set -eu

repository="ftnick/tugyt"
install_directory="${HOME}/.local/bin"
path_line='case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) export PATH="$HOME/.local/bin:$PATH" ;; esac'
legacy_path_line='export PATH="$HOME/.local/bin:$PATH"'

case "${1:-}" in
    "") ;;
    --uninstall)
        rm -f "${install_directory}/tugyt"
        for profile in "${HOME}/.profile" "${HOME}/.bashrc" "${HOME}/.bash_profile" "${HOME}/.zshrc"; do
            if [ -f "$profile" ]; then
                temporary_profile="$(mktemp)"
                awk -v path_line="$path_line" -v legacy_path_line="$legacy_path_line" \
                    '$0 != path_line && $0 != legacy_path_line' "$profile" > "$temporary_profile"
                cat "$temporary_profile" > "$profile"
                rm -f "$temporary_profile"
            fi
        done
        rmdir "$install_directory" 2>/dev/null || :
        printf '%s\n' "Uninstalled tugyt and removed its PATH entry from shell profiles."
        exit 0
        ;;
    --help|-h)
        printf '%s\n' "Usage: install.sh [--uninstall]"
        exit 0
        ;;
    *)
        printf 'Unknown option: %s\nUsage: install.sh [--uninstall]\n' "$1" >&2
        exit 2
        ;;
esac

case "$(uname -s)" in
    Darwin) platform="macos" ;;
    Linux) platform="ubuntu" ;;
    *)
        printf '%s\n' "Unsupported operating system. Use install.ps1 on Windows." >&2
        exit 1
        ;;
esac

for command_name in curl unzip; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        printf 'Required command not found: %s\n' "$command_name" >&2
        exit 1
    fi
done

latest_url="$(curl -fsSL -o /dev/null -w '%{url_effective}' "https://github.com/${repository}/releases/latest")"
tag="${latest_url##*/}"
case "$tag" in
    v[0-9]*) ;;
    *)
        printf 'Could not determine the latest release tag from: %s\n' "$latest_url" >&2
        exit 1
        ;;
esac

archive="tugyt-${platform}-latest-${tag}.zip"
archive_url="https://github.com/${repository}/releases/download/${tag}/${archive}"
temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT HUP INT TERM

curl -fL --retry 3 --output "${temporary_directory}/${archive}" "$archive_url"
unzip -q "${temporary_directory}/${archive}" -d "$temporary_directory/extracted"
if [ ! -f "${temporary_directory}/extracted/tugyt" ]; then
    printf 'The release archive did not contain the expected tugyt executable.\n' >&2
    exit 1
fi

mkdir -p "$install_directory"
cp "${temporary_directory}/extracted/tugyt" "${install_directory}/tugyt"
chmod 755 "${install_directory}/tugyt"

case "${SHELL:-}" in
    */zsh) profile="${HOME}/.zshrc" ;;
    */bash)
        if [ "$(uname -s)" = "Darwin" ]; then
            profile="${HOME}/.bash_profile"
        else
            profile="${HOME}/.bashrc"
        fi
        ;;
    *) profile="${HOME}/.profile" ;;
esac

for existing_profile in "${HOME}/.profile" "${HOME}/.bashrc" "${HOME}/.bash_profile" "${HOME}/.zshrc"; do
    if [ -f "$existing_profile" ] && grep -Fqx "$legacy_path_line" "$existing_profile"; then
        temporary_profile="$(mktemp)"
        awk -v legacy_path_line="$legacy_path_line" '$0 != legacy_path_line' \
            "$existing_profile" > "$temporary_profile"
        cat "$temporary_profile" > "$existing_profile"
        rm -f "$temporary_profile"
    fi
done

if ! grep -Fqx "$path_line" "$profile" 2>/dev/null; then
    printf '\n%s\n' "$path_line" >> "$profile"
fi

printf 'Installed tugyt %s to %s/tugyt\n' "$tag" "$install_directory"
printf 'Restart your terminal or run: . %s\n' "$profile"