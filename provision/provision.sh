#!/bin/bash
# Provision an ESP32 with baseline MicroPython firmware and skeleton scripts.
#
# Usage:
#   ./provision.sh [-p | --program] [-d | --debug]
#
#   -p | --program  Erase flash and write MicroPython firmware before deploying files
#   -d | --debug    Enable bash -x tracing and exit-on-error
#
# Dependencies:
#   mpremote   pip install mpremote
#   esptool    pip install esptool   (only needed with -p)
#
# Before running:
#   - Copy skel/config.json.example to skel/config.json and fill in your values
#   - Run 'mpremote exec "import webrepl_setup"' on the device to create webrepl_cfg.py
#     OR copy your own skel/webrepl_cfg.py (gitignored)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKEL_DIR="${SCRIPT_DIR}/skel"
FIRMWARE="${SCRIPT_DIR}/ESP32_GENERIC-20250911-v1.26.1.bin"
PROGRAM=0
DEBUG=0

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -p|--program)
            PROGRAM=1
            shift
            ;;
        -d|--debug)
            DEBUG=1
            shift
            ;;
        *)
            echo "USAGE: $0 [-p | --program] [-d | --debug]"
            echo "  -p | --program  Flash MicroPython firmware before deploying"
            echo "  -d | --debug    Enable bash -x tracing"
            exit 1
            ;;
    esac
done

if [[ $DEBUG -gt 0 ]]; then
    set -x
fi

# Check required tools
if ! command -v mpremote &>/dev/null; then
    echo "ERROR: mpremote not found. Install with: pip install mpremote"
    exit 1
fi

# Check required skel files
if [[ ! -f "${SKEL_DIR}/config.json" ]]; then
    echo "ERROR: skel/config.json not found."
    echo "  Copy skel/config.json.example to skel/config.json and fill in your values."
    exit 1
fi

if [[ ! -f "${SKEL_DIR}/webrepl_cfg.py" ]]; then
    echo "ERROR: skel/webrepl_cfg.py not found."
    echo "  Run 'mpremote exec \"import webrepl_setup\"' on the device first,"
    echo "  or create skel/webrepl_cfg.py with: PASS = 'your-password'"
    exit 1
fi

if [[ $PROGRAM -gt 0 ]]; then
    if ! command -v esptool.py &>/dev/null; then
        echo "ERROR: esptool.py not found. Install with: pip install esptool"
        exit 1
    fi
    if [[ ! -f "${FIRMWARE}" ]]; then
        echo "ERROR: firmware not found: ${FIRMWARE}"
        exit 1
    fi

    echo "Flashing MicroPython to device: $(basename "${FIRMWARE}")"
    read -p "Press Enter to proceed (Ctrl+C to abort)..." -r

    esptool.py erase_flash
    esptool.py --baud 460800 write_flash 0x1000 "${FIRMWARE}"

    echo "Waiting for device to reboot..."
    sleep 10
fi

echo "Deploying skeleton files..."
pushd "${SKEL_DIR}" > /dev/null
mpremote resume cp boot.py config.py config.json webrepl_cfg.py :/ + cp -r lib :/
popd > /dev/null

echo "Done. Reset the device to apply: mpremote reset"
