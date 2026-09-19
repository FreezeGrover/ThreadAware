#!/usr/bin/env sh
set -eu
if command -v threadaware >/dev/null 2>&1; then
  exec threadaware
fi
echo "ThreadAware is not installed in this environment."
echo "Run: pip install -e ."
exit 1
