#!/bin/bash

# PsyNet Completion Installation Script
# This script installs tab completion for the psynet command

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHELL_NAME=$(basename "$SHELL")

echo "Installing PsyNet tab completion for $SHELL_NAME..."

case "$SHELL_NAME" in
    bash)
        COMPLETION_FILE="$SCRIPT_DIR/psynet-completion.bash"
        RC_FILE="$HOME/.bashrc"
        SOURCE_LINE="source $COMPLETION_FILE"
        ;;
    zsh)
        COMPLETION_FILE="$SCRIPT_DIR/psynet-completion.zsh"
        RC_FILE="$HOME/.zshrc"
        SOURCE_LINE="source $COMPLETION_FILE"
        ;;
    *)
        echo "Unsupported shell: $SHELL_NAME"
        echo "Please manually add one of these lines to your shell configuration:"
        echo "  For bash: source $SCRIPT_DIR/psynet-completion.bash"
        echo "  For zsh: source $SCRIPT_DIR/psynet-completion.zsh"
        exit 1
        ;;
esac

# Check if completion is already installed
if grep -q "_PSYNET_COMPLETE\|psynet-completion" "$RC_FILE" 2>/dev/null; then
    echo "Completion already installed in $RC_FILE"
    echo "To enable completion in current session, run:"
    echo "  source $COMPLETION_FILE"
    exit 0
else
    # Add completion to shell configuration
    echo "" >> "$RC_FILE"
    echo "# PsyNet tab completion" >> "$RC_FILE"
    echo "$SOURCE_LINE" >> "$RC_FILE"
    echo "Completion installed in $RC_FILE."
    echo "To enable completion in current session, run:"
    echo "  source $COMPLETION_FILE"
fi

echo ""
echo "Installation complete! Restart your terminal or run 'source $RC_FILE' (without quotes) to enable completion."
echo ""
echo "You can now use tab completion with psynet commands:"
echo "  psynet <TAB>             # Shows all commands"
echo "  psynet debug <TAB>       # Shows debug subcommands"
echo "  psynet debug local --<TAB>  # Shows options for debug local"
