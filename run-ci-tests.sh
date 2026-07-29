CI_NODE_TOTAL=${CI_NODE_TOTAL:=1}
CI_NODE_INDEX=${CI_NODE_INDEX:=1}

TIMEOUT_SECONDS=300

echo "Running tests on node $CI_NODE_INDEX of $CI_NODE_TOTAL"

echo "Installing CI dependencies..."
bash install-ci-dependencies.sh || exit 1

echo "Checking if translation is needed..."
echo "CI_COMMIT_REF_NAME = $CI_COMMIT_REF_NAME"
if [[ ! "$CI_COMMIT_REF_NAME" =~ ^release- ]]; then
    echo "Not a release branch - will use the null translator to populate any missing translations."
    psynet translate --translator null || exit 1
else
    echo "Release branch detected - will require all translations to be present."
fi

# Fail the build if any of the tests fail
EXIT_CODE=0

for file in $(psynet list-experiment-dirs --for-ci-tests --ci-node-total $CI_NODE_TOTAL --ci-node-index $CI_NODE_INDEX); do
  echo "Testing experiment $file"
  # Materialize ignored boilerplate (including test.py) so pytest can collect.
  # The in_experiment_directory fixture also scaffolds, then restores the
  # authored-only tree on teardown; the explicit restore below is a backstop
  # when collection fails before fixtures run.
  if ! (cd "$file" && psynet scripts scaffold --skip-constraints); then
    EXIT_CODE=1
    continue
  fi
  # We use -Werror to ensure that we see all warnings as errors, but ignore yaspin color warnings
  pytest \
    --junitxml=/public/$(basename $file)_junit.xml \
    $file/test.py \
    -Werror \
    -W "ignore:color, on_color and attrs are not supported when output stream is not a TTY:UserWarning:yaspin.core" \
    -q \
    -o log_cli=False \
    --chrome \
    --timeout=$TIMEOUT_SECONDS
  status=$?
  if ! (cd "$file" && python -c "from psynet.experiment_scaffold import restore_in_repo_experiment_directory as r; r()"); then
    echo "Failed to restore authored-only layout for $file"
    EXIT_CODE=1
  fi
  if [ $status -ne 0 ]; then
    EXIT_CODE=1
  fi
done

for file in $(psynet list-isolated-tests --ci-node-total $CI_NODE_TOTAL --ci-node-index $CI_NODE_INDEX); do
  echo "Testing isolated test $file"
  # We use -Werror to ensure that we see all warnings as errors, but ignore yaspin color warnings
  pytest \
    $file \
    -Werror \
    -W "ignore:color, on_color and attrs are not supported when output stream is not a TTY:UserWarning:yaspin.core" \
    -q \
    -o log_cli=False \
    --chrome \
    --timeout=$TIMEOUT_SECONDS
  if [ $? -ne 0 ]; then
    EXIT_CODE=1
  fi
done

# At the moment we don't have any other tests to run, but here's some template code to do so
# if we decide to add some.
#pytest \
#  --test-group-count=$CI_NODE_TOTAL \
#  --test-group=$CI_NODE_INDEX \
#  --test-group-random-seed=12345 \
#  --ignore=tests/local_only \
#  --ignore=tests/isolated \
#  --ignore=tests/test_run_all_demos.py \
#  --ignore=tests/test_run_isolated_tests.py \
#  --chrome \
#  tests \
#  || exit 1

exit $EXIT_CODE
