#!/bin/bash
# Deploy robot or controller firmware to a connected ESP32.
#
# Usage:
#   ./deploy.sh robot      Deploy the robot firmware
#   ./deploy.sh controller Deploy the controller firmware
#   ./deploy.sh robot -u /dev/ttyUSB1   Specify port when multiple devices connected
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
USB_PORT=""

BOARD="$1"
if [[ "$BOARD" != "robot" && "$BOARD" != "controller" ]]; then
    echo "USAGE: $0 <robot|controller> [-u PORT]"
    echo "  -u PORT   Serial port (e.g. /dev/ttyUSB1, /dev/ttyACM0)"
    exit 1
fi
shift

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -u|--usb)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "ERROR: -u requires a port argument (e.g. -u /dev/ttyUSB1)"
                exit 1
            fi
            USB_PORT="$2"
            shift 2
            ;;
        *)
            echo "USAGE: $0 <robot|controller> [-u PORT]"
            exit 1
            ;;
    esac
done

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

# Warn if multiple USB devices are connected and no port was specified
if [[ -z "${USB_PORT}" ]]; then
    USB_COUNT=$(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | wc -l)
    if [[ $USB_COUNT -gt 1 ]]; then
        echo "WARNING: ${USB_COUNT} USB serial devices detected and no -u port specified."
        echo "  mpremote may target the wrong device. Use -u to select one explicitly."
        echo "  Available ports: $(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | tr '\n' ' ')"
    fi
fi

MPREMOTE="mpremote"
if [[ -n "${USB_PORT}" ]]; then
    MPREMOTE="mpremote connect ${USB_PORT}"
fi

echo "Deploying ${BOARD} firmware..."
[[ -n "${USB_PORT}" ]] && echo "  Port: ${USB_PORT}"

# Deploy shared files first, then board-specific files on top.
# lib/ is merged: shared lib files go first, then board-specific lib files.
pushd "${SHARED_DIR}" > /dev/null
${MPREMOTE} resume cp boot.py config.py :/ + cp -r lib :/
popd > /dev/null

pushd "${BOARD_DIR}" > /dev/null
if [[ "$BOARD" == "robot" ]]; then
    ${MPREMOTE} resume cp main.py config.json : \
        + cp -r lib/ :lib/
else
    ${MPREMOTE} resume cp main.py config.json :
fi
popd > /dev/null

echo "Done. Reset the device to apply: ${MPREMOTE} reset"
