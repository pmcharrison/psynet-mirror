#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 <base_image_tag> [timeout_seconds]" >&2
}

rewrite_psynet_dependency_file() {
  dependency_file="$1"
  if [ ! -f "$dependency_file" ]; then
    return 0
  fi

  rewritten_file="$(mktemp)"
  while IFS= read -r line || [ -n "$line" ]; do
    trimmed="$(printf '%s' "$line" | sed 's/^[[:space:]]*//')"
    normalized="$(printf '%s' "$trimmed" | tr -d ' ')"

    case "$normalized" in
      ""|\#*)
        printf '%s\n' "$line" >> "$rewritten_file"
        continue
        ;;
      psynet@git+https://gitlab.com/PsyNetDev/PsyNet@*)
        psynet_dependency_found=1
        ref_and_suffix="${normalized#psynet@git+https://gitlab.com/PsyNetDev/PsyNet@}"
        ref="${ref_and_suffix%%#*}"
        if [ "$ref" != "master" ]; then
          echo "Invalid PsyNet pin in $dependency_file: $line" >&2
          echo "Custom Docker experiments must reference PsyNet@master." >&2
          rm -f "$rewritten_file"
          exit 1
        fi

        rewritten_line="$(printf '%s\n' "$line" | sed "s#git+https://gitlab.com/PsyNetDev/PsyNet@master#git+https://gitlab.com/PsyNetDev/PsyNet@${ci_commit_sha}#")"
        printf '%s\n' "$rewritten_line" >> "$rewritten_file"
        ;;
      psynet@git+*)
        echo "Invalid PsyNet source in $dependency_file: $line" >&2
        echo "Custom Docker experiments must use gitlab.com/PsyNetDev/PsyNet." >&2
        rm -f "$rewritten_file"
        exit 1
        ;;
      psynet*)
        echo "Invalid PsyNet dependency in $dependency_file: $line" >&2
        echo "Custom Docker experiments must use PsyNet@master." >&2
        rm -f "$rewritten_file"
        exit 1
        ;;
      *)
        printf '%s\n' "$line" >> "$rewritten_file"
        ;;
    esac
  done < "$dependency_file"

  mv "$rewritten_file" "$dependency_file"
}

prepare_build_context() {
  build_experiment_dir="$(mktemp -d "${build_context_root}/${experiment_name}.XXXXXX")"
  cp -R "$experiment_dir"/. "$build_experiment_dir"/

  psynet_dependency_found=0
  rewrite_psynet_dependency_file "$build_experiment_dir/requirements.txt"
  rewrite_psynet_dependency_file "$build_experiment_dir/constraints.txt"

  if [ "$psynet_dependency_found" -eq 0 ]; then
    echo "No PsyNet dependency found for $experiment_dir." >&2
    echo "Custom Docker experiments must pin PsyNet@master in requirements.txt or constraints.txt." >&2
    exit 1
  fi
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
  echo "Building Docker image for $experiment_dir with PsyNet@$ci_commit_sha"
  docker build --tag "$image_tag" "$build_experiment_dir"
}

run_empty_log_diagnostic() {
  diagnostic_log="public/${experiment_name}_diagnostic.log"
  warning_filter="ignore:color, on_color and attrs are not supported when output stream is not a TTY:UserWarning:yaspin.core"
  diagnostic_cmd="pytest --junitxml=/public/${experiment_name}_junit.xml test.py -Werror -W \"$warning_filter\" -o log_cli=True --chrome --timeout=${timeout_seconds} -vv -s"

  echo "Collecting fallback diagnostics in $diagnostic_log"
  if sh ci/run-ci-docker-command.sh "$image_tag" "/workspace" "/workspace/$experiment_dir" \
    bash -c "$diagnostic_cmd" > "$diagnostic_log" 2>&1; then
    echo "Diagnostic rerun unexpectedly succeeded."
  else
    diagnostic_status=$?
    echo "Diagnostic rerun failed with exit code $diagnostic_status"
  fi

  if [ -s "$diagnostic_log" ]; then
    echo "Last 200 lines from $diagnostic_log:"
    tail -n 200 "$diagnostic_log" || true
  else
    echo "Diagnostic log is also empty: $diagnostic_log"
  fi
}

show_failure_log_tail() {
  if [ -s "$log_file" ]; then
    echo "Last 200 lines from $log_file:"
    tail -n 200 "$log_file" || true
  elif [ -f "$log_file" ]; then
    echo "Log file exists but is empty: $log_file"
    run_empty_log_diagnostic
  else
    echo "No log file was created for $experiment_dir."
  fi
}

run_experiment_tests() {
  echo "Running tests for $experiment_dir"
  log_file="public/${experiment_name}.log"
  echo "Writing test output to $log_file"

  pytest_cmd="sh /workspace/ci/run-pytest-with-common-flags.sh ${timeout_seconds} --junitxml=/public/${experiment_name}_junit.xml test.py"

  if sh ci/run-ci-docker-command.sh "$image_tag" "/workspace" "/workspace/$experiment_dir" \
    bash -c "$pytest_cmd" > "$log_file" 2>&1; then
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
ci_commit_sha="${CI_COMMIT_SHA:-}"
if [ -z "$ci_commit_sha" ]; then
  echo "CI_COMMIT_SHA is required for docker experiment builds." >&2
  exit 1
fi

experiment_list_file="$(mktemp)"
build_context_root="$(mktemp -d)"
trap '[ -n "${experiment_list_file:-}" ] && rm -f "$experiment_list_file"; [ -n "${build_context_root:-}" ] && rm -rf "$build_context_root"' EXIT INT TERM

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

  prepare_build_context
  build_experiment_image
  run_experiment_tests
done < "$experiment_list_file"

exit "$exit_code"
