#!/bin/bash

# PsyNet bash completion script
# Source this file in your ~/.bashrc to enable automatic tab completion

# Generate and eval the completion script from psynet
eval "$(_PSYNET_COMPLETE=bash_source psynet)"
