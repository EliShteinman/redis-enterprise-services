#!/bin/sh
set -eu

bootstrap_url="https://${CLUSTER_HOST}:${API_PORT}/v1/bootstrap"

read_state() {
    curl --silent --insecure --user "${ADMIN_USERNAME}:${ADMIN_PASSWORD}" "${bootstrap_url}" \
        | sed -n 's/.*"state": *"\([a-z_]*\)".*/\1/p'
}

wait_for_state() {
    until state="$(read_state)" && [ -n "${state}" ] && [ "${state}" != "$1" ]; do
        sleep "${POLL_INTERVAL_SECONDS}"
    done
    echo "${state}"
}

create_cluster() {
    curl --silent --insecure --fail-with-body \
        --request POST "${bootstrap_url}/create_cluster" \
        --header "Content-Type: application/json" \
        --data @- <<EOF
{
  "action": "create_cluster",
  "cluster": {"name": "${CLUSTER_NAME}"},
  "node": {"paths": {"persistent_path": "${PERSISTENT_PATH}", "ephemeral_path": "${EPHEMERAL_PATH}"}},
  "credentials": {"username": "${ADMIN_USERNAME}", "password": "${ADMIN_PASSWORD}"}
}
EOF
}

echo "Waiting for ${CLUSTER_HOST} to accept bootstrap requests"
state="$(wait_for_state "")"

if [ "${state}" = "completed" ]; then
    echo "${CLUSTER_NAME} is already bootstrapped"
    exit 0
fi

echo "Creating cluster ${CLUSTER_NAME}"
create_cluster

state="$(read_state)"
while [ "${state}" != "completed" ]; do
    if [ "${state}" = "error" ]; then
        echo "Bootstrap of ${CLUSTER_NAME} failed" >&2
        curl --silent --insecure "${bootstrap_url}" >&2
        exit 1
    fi
    sleep "${POLL_INTERVAL_SECONDS}"
    state="$(read_state)"
done

echo "${CLUSTER_NAME} is ready"
