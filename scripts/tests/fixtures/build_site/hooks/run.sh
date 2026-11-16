#!/usr/bin/env bash
# Runs the fixture hook.
# Calls the helper.
set -e
bash "$HERE/helper.sh"
bash scripts/tool.sh
