#!/bin/sh
set -eu

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <timeout_seconds> <pytest args...>" >&2
  exit 1
fi

timeout_seconds="$1"
shift

warning_filter="ignore:color, on_color and attrs are not supported when output stream is not a TTY:UserWarning:yaspin.core"

pytest "$@" \
  -Werror \
  -W "$warning_filter" \
  -q \
  -o log_cli=False \
  --chrome \
  --timeout="$timeout_seconds"
