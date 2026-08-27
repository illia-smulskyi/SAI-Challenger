#!/usr/bin/env bash
#
# Start syncd from supervisord. Redis sync is the default; ZMQ is selected
# when SAI_INTERFACE=zmq is set in the container environment (run.sh -s zmq).
#

set -e

PROFILE="${SYNCD_PROFILE:-/etc/sai.d/sai.profile}"
CTX="${SYNCD_CONTEXT_CONFIG:-/etc/sai.d/context_config.json}"
ARGS=()

if [ "${SAI_INTERFACE}" = "zmq" ]; then
    ARGS+=(-z zmq_sync)
    if [ -f "${CTX}" ]; then
        ARGS+=(-x "${CTX}")
    fi
else
    ARGS+=(-s)
fi

if [ -f "${PROFILE}" ]; then
    ARGS+=(-p "${PROFILE}")
fi

exec /usr/bin/syncd "${ARGS[@]}" "$@"
