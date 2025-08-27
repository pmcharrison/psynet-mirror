#!/bin/bash

# PsyNet bash completion script
# Source this file in your ~/.bashrc to enable automatic tab completion

# Enable completion for bash
complete -o default -o nospace -F _psynet psynet

# Generate and eval the completion script from psynet, but only when available.
if command -v psynet >/dev/null 2>&1; then

  eval "$(_PSYNET_COMPLETE=bash_source psynet)"
else
  # Lazily register completion after psynet becomes available (e.g., after activating a virtualenv)
  _psynet_register_completion() {
    if command -v psynet >/dev/null 2>&1; then
      eval "$(_PSYNET_COMPLETE=bash_source psynet)"
      # Remove self from PROMPT_COMMAND once registered
      if [[ "${PROMPT_COMMAND:-}" == *"_psynet_register_completion"* ]]; then
        PROMPT_COMMAND="${PROMPT_COMMAND/_psynet_register_completion; /}"
        PROMPT_COMMAND="${PROMPT_COMMAND/_psynet_register_completion;/}"
        PROMPT_COMMAND="${PROMPT_COMMAND/_psynet_register_completion/}"
      fi
    fi
  }
  if [[ -n "${PROMPT_COMMAND:-}" ]]; then
    PROMPT_COMMAND="_psynet_register_completion; ${PROMPT_COMMAND}"
  else
    PROMPT_COMMAND="_psynet_register_completion"
  fi
fi
