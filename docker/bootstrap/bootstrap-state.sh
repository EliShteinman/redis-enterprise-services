#!/bin/sh

bootstrap_url="https://${NODE_HOST}:${API_PORT}/v1/bootstrap"

fetch_bootstrap() {
    curl --silent --insecure --user "${ADMIN_USERNAME}:${ADMIN_PASSWORD}" "${bootstrap_url}"
}

read_state() {
    fetch_bootstrap \
        | sed -n 's/.*"state": *"\([a-z_]*\)".*/\1/p'
}

wait_for_first_state() {
    until state="$(read_state)" && [ -n "${state}" ]; do
        sleep "${POLL_INTERVAL_SECONDS}"
    done
    echo "${state}"
}

wait_until_completed() {
    failure_message="$1"
    state="$(read_state)"
    while [ "${state}" != "completed" ]; do
        if [ "${state}" = "error" ]; then
            echo "${failure_message}" >&2
            fetch_bootstrap >&2
            exit 1
        fi
        sleep "${POLL_INTERVAL_SECONDS}"
        state="$(read_state)"
    done
}
