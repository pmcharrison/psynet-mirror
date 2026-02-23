#!/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <base_image_tag> [timeout_seconds]" >&2
  exit 1
fi

base_image_tag="$1"
timeout_seconds="${2:-300}"
experiment_list_file="/tmp/docker-build-experiments.txt"

mkdir -p public

docker run --rm -v "$PWD:/workspace" -w /workspace "$base_image_tag" sh -lc '
PYTHONPATH=/workspace python - <<'"'"'PY'"'"'
from pathlib import Path
from psynet.utils import get_psynet_root, list_docker_build_experiment_dirs

root = get_psynet_root()
for directory in list_docker_build_experiment_dirs():
    print(Path(directory).relative_to(root))
PY
' > "$experiment_list_file"

if [ ! -s "$experiment_list_file" ]; then
  echo "No docker-build experiments configured."
  exit 0
fi

exit_code=0
while IFS= read -r experiment_dir; do
  [ -z "$experiment_dir" ] && continue

  experiment_name="$(basename "$experiment_dir")"
  image_tag="custom-${experiment_name}"

  echo "Building Docker image for $experiment_dir"
  docker build --tag "$image_tag" "$experiment_dir"

  echo "Running tests for $experiment_dir"
  log_file="public/${experiment_name}.log"
  echo "Writing test output to $log_file"

  pytest_cmd="pytest --junitxml=/public/${experiment_name}_junit.xml test.py -Werror -W \"ignore:color, on_color and attrs are not supported when output stream is not a TTY:UserWarning:yaspin.core\" -q -o log_cli=False --chrome --timeout=${timeout_seconds}"

  if sh ci/run-ci-docker-command.sh "$image_tag" "/workspace" "/workspace/$experiment_dir" \
    bash -c "$pytest_cmd" > "$log_file" 2>&1; then
    :
  else
    status=$?
    echo "Tests failed for $experiment_dir with exit code $status"
    if [ -f "$log_file" ]; then
      echo "Last 200 lines from $log_file:"
      tail -n 200 "$log_file" || true
    fi
    exit_code=1
  fi
done < "$experiment_list_file"

exit "$exit_code"
