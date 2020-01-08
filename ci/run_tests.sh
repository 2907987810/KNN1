#!/bin/bash -e

# Workaround for pytest-xdist (it collects different tests in the workers if PYTHONHASHSEED is not set)
# https://github.com/pytest-dev/pytest/issues/920
# https://github.com/pytest-dev/pytest/issues/1075
export PYTHONHASHSEED=$(python -c 'import random; print(random.randint(1, 4294967295))')

if [[ "not network" == *"$PATTERN"* ]]; then
    export http_proxy=http://1.2.3.4 https_proxy=http://1.2.3.4;
fi

if [ "$COVERAGE" ]; then
    COVERAGE_FNAME="/tmp/test_coverage.xml"
    COVERAGE="-s --cov=pandas --cov-report=xml:$COVERAGE_FNAME"
fi

# An X server has to exit, and DISPLAY set, for the clipboard (and its tests) to work
export DISPLAY=":99.0"

PYTEST_CMD="pytest -m \"$PATTERN\" -n auto --dist=loadfile -s --strict --durations=10 --junitxml=test-data.xml $TEST_ARGS $COVERAGE pandas/tests/io/test_clipboard.py"

# Travis does not have have an X server
if [[ "$TRAVIS_OS_NAME" == "linux" ]]; then
    PYTEST_CMD="xvfb-run -e /dev/stdout $PYTEST_CMD"
fi

set +e
echo "Is xsel installed?"
set -x
dpkg -l
echo $PATH
python -c "import subprocess; print(subprocess.call(['which', 'xsel'], stdout=subprocess.PIPE, stderr=subprocess.PIPE))"
which xsel
set -e

echo $PYTEST_CMD
sh -c "$PYTEST_CMD"

if [[ "$COVERAGE" && $? == 0 && "$TRAVIS_BRANCH" == "master" ]]; then
    echo "uploading coverage"
    echo "bash <(curl -s https://codecov.io/bash) -Z -c -f $COVERAGE_FNAME"
          bash <(curl -s https://codecov.io/bash) -Z -c -f $COVERAGE_FNAME
fi
