# PsyNet zsh completion script
# Source this file in your ~/.zshrc to enable automatic tab completion

# Enable completion for zsh
autoload -Uz compinit && compinit

# Generate and eval the completion script from psynet, but only when available.
if command -v psynet >/dev/null 2>&1; then
  # Direct eval if psynet is available
  eval "$(_PSYNET_COMPLETE=zsh_source psynet)"
else
  # Lazily register completion after psynet becomes available (e.g., after activating a virtualenv)
  autoload -U add-zsh-hook
  _psynet_register_completion() {
    if command -v psynet >/dev/null 2>&1; then
      eval "$(_PSYNET_COMPLETE=zsh_source psynet)"
      add-zsh-hook -d precmd _psynet_register_completion
    fi
  }
  add-zsh-hook precmd _psynet_register_completion
fi
