#!/bin/sh
set -eu

bootstrap_url="https://${NODE_HOST}:${API_PORT}/v1/bootstrap"

read_state() {
    curl --silent --insecure --user "${ADMIN_USERNAME}:${ADMIN_PASSWORD}" "${bootstrap_url}" \
        | sed -n 's/.*"state": *"\([a-z_]*\)".*/\1/p'
}

wait_for_first_state() {
    until state="$(read_state)" && [ -n "${state}" ]; do
        sleep "${POLL_INTERVAL_SECONDS}"
    done
    echo "${state}"
}

join_cluster() {
    curl --silent --insecure --fail-with-body \
        --request POST "${bootstrap_url}/join_cluster" \
        --header "Content-Type: application/json" \
        --data @- <<EOF
{
  "action": "join_cluster",
  "cluster": {"nodes": ["${cluster_node_ip}"]},
  "node": {"paths": {"persistent_path": "${PERSISTENT_PATH}", "ephemeral_path": "${EPHEMERAL_PATH}"}},
  "credentials": {"username": "${ADMIN_USERNAME}", "password": "${ADMIN_PASSWORD}"}
}
EOF
}

echo "Waiting for ${NODE_HOST} to accept bootstrap requests"
state="$(wait_for_first_state)"

if [ "${state}" = "completed" ]; then
    echo "${NODE_HOST} already belongs to a cluster"
    exit 0
fi

cluster_node_ip="$(getent hosts "${CLUSTER_NODE_HOST}" | cut -d ' ' -f 1)"
echo "Joining ${NODE_HOST} to ${CLUSTER_NODE_HOST} (${cluster_node_ip})"
join_cluster

state="$(read_state)"
while [ "${state}" != "completed" ]; do
    if [ "${state}" = "error" ]; then
        echo "Join of ${NODE_HOST} failed" >&2
        curl --silent --insecure --user "${ADMIN_USERNAME}:${ADMIN_PASSWORD}" "${bootstrap_url}" >&2
        exit 1
    fi
    sleep "${POLL_INTERVAL_SECONDS}"
    state="$(read_state)"
done

echo "${NODE_HOST} joined ${CLUSTER_NODE_HOST}"
