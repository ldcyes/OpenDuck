#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Run from the delivered rk_runtime directory on a provisioned 64-bit Radxa Debian system.
test "$(uname -m)" = aarch64 || { echo 'This deployment script is for aarch64 RK3566.' >&2; exit 2; }
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
echo 'Installed. Verify I2C4 device mapping and U2D2 by-id path; then perform torque-off commissioning.'
