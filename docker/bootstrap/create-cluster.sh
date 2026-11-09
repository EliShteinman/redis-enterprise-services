#!/bin/sh
set -eu

. "$(dirname "$0")/bootstrap-state.sh"

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

install_license() {
    awk 'BEGIN { printf "{\"license\": \"" } { printf "%s\\n", $0 } END { printf "\"}" }' "${LICENSE_FILE}" \
        | curl --silent --insecure --fail-with-body --output /dev/null \
            --user "${ADMIN_USERNAME}:${ADMIN_PASSWORD}" \
            --request PUT "https://${NODE_HOST}:${API_PORT}/v1/license" \
            --header "Content-Type: application/json" \
            --data @-
}

echo "Waiting for ${NODE_HOST} to accept bootstrap requests"
state="$(wait_for_first_state)"

if [ "${state}" = "completed" ]; then
    echo "${CLUSTER_NAME} is already bootstrapped"
else
    echo "Creating cluster ${CLUSTER_NAME}"
    create_cluster
    wait_until_completed "Bootstrap of ${CLUSTER_NAME} failed"
fi

if [ -f "${LICENSE_FILE}" ]; then
    echo "Installing license on ${CLUSTER_NAME}"
    install_license
else
    echo "No license at ${LICENSE_FILE}, ${CLUSTER_NAME} stays on the trial license"
fi

echo "${CLUSTER_NAME} is ready"
