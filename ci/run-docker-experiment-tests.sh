#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 <base_image_tag> [timeout_seconds]" >&2
}

discover_experiments() {
  docker run --rm -v "$PWD:/workspace" -w /workspace "$base_image_tag" sh -lc '
PYTHONPATH=/workspace python - <<'"'"'PY'"'"'
from pathlib import Path
from psynet.utils import get_psynet_root, list_docker_build_experiment_dirs

root = get_psynet_root()
for directory in list_docker_build_experiment_dirs():
    print(Path(directory).relative_to(root))
PY
' > "$experiment_list_file"
}

build_experiment_image() {
  echo "Building Docker image for $experiment_dir"
  docker build --tag "$image_tag" "$experiment_dir"
}

show_failure_log_tail() {
  if [ -s "$log_file" ]; then
    echo "Last 200 lines from $log_file:"
    tail -n 200 "$log_file" || true
  elif [ -f "$log_file" ]; then
    echo "Log file exists but is empty: $log_file"
  else
    echo "No log file was created for $experiment_dir."
  fi
}

run_experiment_tests() {
  echo "Running tests for $experiment_dir"
  log_file="public/${experiment_name}.log"
  echo "Writing test output to $log_file"

  if sh ci/run-ci-docker-command.sh "$image_tag" "/workspace" "/workspace/$experiment_dir" \
    sh "/workspace/ci/run-pytest-with-common-flags.sh" "$timeout_seconds" \
    "--junitxml=/public/${experiment_name}_junit.xml" "test.py" > "$log_file" 2>&1; then
    :
  else
    status=$?
    echo "Tests failed for $experiment_dir with exit code $status"
    show_failure_log_tail
    exit_code=1
  fi
}

if [ "$#" -lt 1 ]; then
  usage
  exit 1
fi

base_image_tag="$1"
timeout_seconds="${2:-300}"
experiment_list_file="$(mktemp)"
trap '[ -n "${experiment_list_file:-}" ] && rm -f "$experiment_list_file"' EXIT INT TERM

mkdir -p public
discover_experiments

if [ ! -s "$experiment_list_file" ]; then
  echo "No docker-build experiments configured."
  exit 0
fi

exit_code=0
while IFS= read -r experiment_dir; do
  [ -z "$experiment_dir" ] && continue

  experiment_name="$(basename "$experiment_dir")"
  image_tag="custom-${experiment_name}"

  build_experiment_image
  run_experiment_tests
done < "$experiment_list_file"

exit "$exit_code"
