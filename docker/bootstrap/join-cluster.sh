#!/bin/sh
set -eu

. "$(dirname "$0")/bootstrap-state.sh"

join_cluster() {
    curl --silent --insecure --fail-with-body \
        --request POST "${bootstrap_url}/join_cluster" \
        --header "Content-Type: application/json" \
        --data @- <<EOF
{
  "action": "join_cluster",
  "cluster": {"nodes": ["${CLUSTER_NODE_IP}"]},
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

echo "Joining ${NODE_HOST} to ${CLUSTER_NODE_HOST} (${CLUSTER_NODE_IP})"
join_cluster

wait_until_completed "Join of ${NODE_HOST} failed"

echo "${NODE_HOST} joined ${CLUSTER_NODE_HOST}"
