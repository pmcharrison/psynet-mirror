#!/bin/bash

# PsyNet Completion Installation Script
# This script installs tab completion for the psynet command

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHELL_NAME=$(basename "$SHELL")
USER_BIN_DIR="$HOME/.local/bin"

echo "Installing PsyNet tab completion for $SHELL_NAME..."
mkdir -p "$USER_BIN_DIR"

case "$SHELL_NAME" in
    bash)
        COMPLETION_FILE="$USER_BIN_DIR/.psynet-completion.bash"
        RC_FILE="$HOME/.bashrc"
        SOURCE_LINE="source $COMPLETION_FILE"
        COMPLETION_INIT="complete -o default -o nospace -F _psynet psynet"
        ;;
    zsh)
        COMPLETION_FILE="$USER_BIN_DIR/.psynet-completion.zsh"
        RC_FILE="$HOME/.zshrc"
        SOURCE_LINE="source $COMPLETION_FILE"
        COMPLETION_INIT="autoload -Uz compinit && compinit"
        ;;
    *)
        echo "Unsupported shell: $SHELL_NAME"
        echo "Please manually add one of these lines to your shell configuration:"
        echo "  For bash: source $USER_BIN_DIR/.psynet-completion.bash"
        echo "  For zsh: source $USER_BIN_DIR/.psynet-completion.zsh"
        exit 1
        ;;
esac

# Generate completion files (always overwrite to ensure they're up-to-date)
echo "$COMPLETION_INIT" > "$COMPLETION_FILE"
echo "" >> "$COMPLETION_FILE"
case "$SHELL_NAME" in
    bash)
        _PSYNET_COMPLETE=bash_source psynet >> "$COMPLETION_FILE" 2>/dev/null || {
            echo "Failed to generate bash completion file. Please ensure psynet is installed and accessible."
            exit 1
        }
        ;;
    zsh)
        _PSYNET_COMPLETE=zsh_source psynet >> "$COMPLETION_FILE" 2>/dev/null || {
            echo "Failed to generate zsh completion file. Please ensure psynet is installed and accessible."
            exit 1
        }
        ;;
esac
echo "Generated completion file for $SHELL_NAME: $COMPLETION_FILE"

# Check if completion is already installed
if grep -q "\.psynet-completion" "$RC_FILE" 2>/dev/null; then
    echo "Completion already installed in $RC_FILE."
else
    # Add completion to shell configuration
    echo "" >> "$RC_FILE"
    echo "# PsyNet tab completion" >> "$RC_FILE"
    echo "$SOURCE_LINE" >> "$RC_FILE"
    echo "Completion installed in $RC_FILE."
    echo "Installation complete!"
fi

echo ""
echo "Tab completion will be available in new terminal sessions."
echo "To enable completion in your current session, run:"
echo "  source $COMPLETION_FILE"
echo ""
echo "You can then use tab completion with psynet commands:"
echo "  psynet <TAB>                # Shows all commands"
echo "  psynet debug <TAB>          # Shows debug subcommands"
echo "  psynet debug local --<TAB>  # Shows options for debug local"
