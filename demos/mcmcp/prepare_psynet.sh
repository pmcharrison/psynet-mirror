#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# psynet is currently unreleased, so specifying a url for pip is harder than usual.
# We can point it to the gitlab repository, but this means we always need to clone
# a 100+ Mb repository.
# To speed up deployment this script creates a (small) wheel from the currently
# checked out psynet, in the grandparent directory.

cd ${DIR}/../..
python setup.py bdist_wheel
cp dist/$(ls -tr dist/|egrep ^psynet.*whl$) ${DIR}/

cd ${DIR}
dallinger generate-constraints
