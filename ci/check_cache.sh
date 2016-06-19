#!/usr/bin/env bash

ci_changes=$(git diff HEAD~1 --numstat | grep -E "ci/"| wc -l)

MINICONDA_DIR="$HOME/miniconda"
CACHE_DIR="$HOME/.cache"
CCACHE_DIR="$HOME/.ccache"

if [ $ci_changes -ne 0 ]
then
    echo "CI has been changed in the last commit deleting all caches"
    rm -rf "$MINICONDA_DIR"
    rm -rf "$CACHE_DIR"
    rm -rf "$CCACHE_DIR"
    if [ "$USE_CACHE" ]
    then
        unset USE_CACHE
    fi
fi