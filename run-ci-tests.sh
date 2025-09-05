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
  # We use -Werror to ensure that we see all warnings as errors
  pytest --junitxml=/public/$(basename $file)_junit.xml $file/test.py -Werror -q -o log_cli=False --chrome --timeout=$TIMEOUT_SECONDS
  if [ $? -ne 0 ]; then
    EXIT_CODE=1
  fi
done

for file in $(psynet list-isolated-tests --ci-node-total $CI_NODE_TOTAL --ci-node-index $CI_NODE_INDEX); do
  echo "Testing isolated test $file"
  # We use -Werror to ensure that we see all warnings as errors
  pytest $file -Werror -q -o log_cli=False --chrome --timeout=$TIMEOUT_SECONDS
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
