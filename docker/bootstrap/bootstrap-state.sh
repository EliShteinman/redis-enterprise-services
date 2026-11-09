cluster_authorization="Basic $(printf '%s' "${ADMIN_USERNAME}:${ADMIN_PASSWORD}" | base64 | tr -d '\n')"

relay_call() {
    method="$1"
    path="$2"
    shift 2
    curl --silent --request POST "${RELAY_URL}" \
        --header "x-cluster-method: ${method}" \
        --header "x-cluster-url: ${NODE_API_URL}${path}" \
        --header "x-cluster-authorization: ${cluster_authorization}" \
        --header "content-type: application/json" \
        "$@"
}

fetch_bootstrap() {
    relay_call GET /v1/bootstrap
}

read_state() {
    fetch_bootstrap \
        | sed -n 's/.*"state": *"\([a-z_]*\)".*/\1/p'
}

require_relay() {
    if ! curl --silent --output /dev/null "${RELAY_URL}"; then
        echo "cluster-relay is not reachable at ${RELAY_URL}, start it first" >&2
        exit 1
    fi
}

wait_for_first_state() {
    require_relay
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
