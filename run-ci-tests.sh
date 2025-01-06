CI_NODE_TOTAL=${CI_NODE_TOTAL:=1}
CI_NODE_INDEX=${CI_NODE_INDEX:=1}

echo "Running tests on node $CI_NODE_INDEX of $CI_NODE_TOTAL"

echo "Installing CI dependencies..."
bash install-ci-dependencies.sh || exit 1

for file in $(psynet list-experiment-dirs --for-ci-tests --ci-node-total $CI_NODE_TOTAL --ci-node-index $CI_NODE_INDEX); do
  echo "Testing experiment $file"
  pytest --junitxml=/public/$(basename $file)_junit.xml $file/test.py -q -o log_cli=False --chrome || exit 1
done

for file in $(psynet list-isolated-tests --ci-node-total $CI_NODE_TOTAL --ci-node-index $CI_NODE_INDEX); do
  echo "Testing isolated test $file"
  pytest $file -q -o log_cli=False --chrome || exit 1
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
