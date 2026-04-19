#!/bin/bash
# Provision an ESP32 with baseline MicroPython firmware and skeleton scripts.
#
# Usage:
#   ./provision.sh [-p | --program] [-u | --usb PORT] [-d | --debug]
#
#   -p | --program       Erase flash and write MicroPython firmware before deploying files
#   -u | --usb PORT      Serial port to use (e.g. /dev/ttyUSB1). If omitted, esptool
#                        auto-detects — unreliable when multiple USB devices are connected.
#   -d | --debug         Enable bash -x tracing and exit-on-error
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
FIRMWARE="$(ls -t "${SCRIPT_DIR}"/*.bin 2>/dev/null | head -1)"
PROGRAM=0
DEBUG=0
USB_PORT=""

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -p|--program)
            PROGRAM=1
            shift
            ;;
        -u|--usb)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "ERROR: --usb requires a port argument (e.g. --usb /dev/ttyUSB1)"
                exit 1
            fi
            USB_PORT="$2"
            shift 2
            ;;
        -d|--debug)
            DEBUG=1
            shift
            ;;
        *)
            echo "USAGE: $0 [-p | --program] [-u | --usb PORT] [-d | --debug]"
            echo "  -p | --program       Flash MicroPython firmware before deploying"
            echo "  -u | --usb PORT      Serial port (e.g. /dev/ttyUSB1, /dev/ttyACM0)"
            echo "  -d | --debug         Enable bash -x tracing"
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
    if [[ -z "${FIRMWARE}" ]]; then
        echo "ERROR: no *.bin firmware file found in ${SCRIPT_DIR}"
        echo ""
        echo "  Download the correct MicroPython firmware for your ESP32 variant from:"
        echo "    https://micropython.org/download/ESP32_GENERIC/"
        echo ""
        echo "  Common variants:"
        echo "    ESP32_GENERIC          — standard ESP32 (most dev boards)"
        echo "    ESP32_GENERIC_S2       — ESP32-S2"
        echo "    ESP32_GENERIC_S3       — ESP32-S3"
        echo "    ESP32_GENERIC_C3       — ESP32-C3"
        echo ""
        echo "  Place the downloaded .bin file in: ${SCRIPT_DIR}"
        exit 1
    fi

    # Build port flag; warn if not specified and multiple USB devices are present
    PORT_FLAG=""
    if [[ -n "${USB_PORT}" ]]; then
        PORT_FLAG="--port ${USB_PORT}"
    else
        USB_COUNT=$(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | wc -l)
        if [[ $USB_COUNT -gt 1 ]]; then
            echo "WARNING: ${USB_COUNT} USB serial devices detected and no --usb port specified."
            echo "  esptool may target the wrong device. Use -u to select one explicitly."
            echo "  Available ports: $(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | tr '\n' ' ')"
        fi
    fi

    echo "Flashing MicroPython to device: $(basename "${FIRMWARE}")"
    [[ -n "${USB_PORT}" ]] && echo "  Port: ${USB_PORT}"
    read -p "Press Enter to proceed (Ctrl+C to abort)..." -r

    # shellcheck disable=SC2086
    esptool.py ${PORT_FLAG} erase_flash
    # shellcheck disable=SC2086
    esptool.py ${PORT_FLAG} --baud 460800 write_flash 0x1000 "${FIRMWARE}"

    echo "Waiting for device to reboot..."
    sleep 10
fi

echo "Deploying skeleton files..."
pushd "${SKEL_DIR}" > /dev/null
mpremote resume cp boot.py config.py config.json webrepl_cfg.py :/ + cp -r lib :/
popd > /dev/null

echo "Done. Reset the device to apply: mpremote reset"
