#!/bin/bash
# Deploy robot or controller firmware to a connected ESP32.
#
# Usage:
#   ./deploy.sh robot      Deploy the robot firmware
#   ./deploy.sh controller Deploy the controller firmware
#
# Dependencies:
#   mpremote   pip install mpremote
#
# Before running:
#   - Edit src/<board>/config.json (copied from config.json.example)
#   - For the robot, also create mecanum.json on the device

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SHARED_DIR="${SCRIPT_DIR}/src/shared"

BOARD="$1"
if [[ "$BOARD" != "robot" && "$BOARD" != "controller" ]]; then
    echo "USAGE: $0 <robot|controller>"
    exit 1
fi

BOARD_DIR="${SCRIPT_DIR}/src/${BOARD}"

if ! command -v mpremote &>/dev/null; then
    echo "ERROR: mpremote not found. Install with: pip install mpremote"
    exit 1
fi

if [[ ! -f "${BOARD_DIR}/config.json" ]]; then
    echo "ERROR: ${BOARD_DIR}/config.json not found."
    echo "  Copy config.json.example to config.json and fill in your values."
    exit 1
fi

echo "Deploying ${BOARD} firmware..."

# Deploy shared files first, then board-specific files on top.
# lib/ is merged: shared lib files go first, then board-specific lib files.
pushd "${SHARED_DIR}" > /dev/null
mpremote resume cp boot.py config.py :/ + cp -r lib :/
popd > /dev/null

pushd "${BOARD_DIR}" > /dev/null
if [[ "$BOARD" == "robot" ]]; then
    mpremote resume cp main.py config.json : \
        + cp -r lib/ :lib/
else
    mpremote resume cp main.py config.json :
fi
popd > /dev/null

echo "Done. Reset the device to apply: mpremote reset"
