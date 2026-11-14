cluster_authorization="Basic $(printf '%s' "${ADMIN_USERNAME}:${ADMIN_PASSWORD}" | base64 | tr -d '\n')"

relay_call() {
    method="$1"
    path="$2"
    shift 2
    curl --silent --max-time "${REQUEST_TIMEOUT_SECONDS}" --request POST "${RELAY_URL}" \
        --header "x-cluster-method: ${method}" \
        --header "x-cluster-url: ${NODE_API_URL}${path}" \
        --header "x-cluster-authorization: ${cluster_authorization}" \
        --header "content-type: application/json" \
        "$@"
}

fetch_bootstrap() {
    relay_call GET /v1/bootstrap "$@"
}

REFUSED_STATE="refused"

read_state() {
    answer="$(fetch_bootstrap --include)" || answer=""
    if printf '%s\n' "${answer}" | grep -qiE '^x-edge-error: *invalid_request|^HTTP/[0-9.]+ (401|403)'; then
        echo "the bootstrap request is refused, and waiting will not change that:" >&2
        printf '%s\n' "${answer}" >&2
        echo "${REFUSED_STATE}"
        return
    fi
    printf '%s\n' "${answer}" | sed -n 's/.*"state": *"\([a-z_]*\)".*/\1/p'
}

stop_if_refused() {
    if [ "$1" = "${REFUSED_STATE}" ]; then
        exit 1
    fi
}

require_relay() {
    if ! curl --silent --max-time "${REQUEST_TIMEOUT_SECONDS}" --output /dev/null "${RELAY_URL}"; then
        echo "cluster-relay is not reachable at ${RELAY_URL}, start it first" >&2
        exit 1
    fi
}

give_up_after_max_polls() {
    polls="$1"
    failure_message="$2"
    if [ "${polls}" -ge "${MAX_POLLS}" ]; then
        echo "${failure_message} after ${MAX_POLLS} polls; the last relay answer:" >&2
        fetch_bootstrap --include >&2
        exit 1
    fi
}

wait_for_first_state() {
    require_relay
    polls=0
    state="$(read_state)"
    while [ -z "${state}" ]; do
        polls=$((polls + 1))
        give_up_after_max_polls "${polls}" "No bootstrap state"
        sleep "${POLL_INTERVAL_SECONDS}"
        state="$(read_state)"
    done
    stop_if_refused "${state}"
    echo "${state}"
}

wait_until_completed() {
    failure_message="$1"
    state="$(read_state)"
    polls=0
    while [ "${state}" != "completed" ]; do
        stop_if_refused "${state}"
        if [ "${state}" = "error" ]; then
            echo "${failure_message}" >&2
            fetch_bootstrap >&2
            exit 1
        fi
        polls=$((polls + 1))
        give_up_after_max_polls "${polls}" "${failure_message}"
        sleep "${POLL_INTERVAL_SECONDS}"
        state="$(read_state)"
    done
}
