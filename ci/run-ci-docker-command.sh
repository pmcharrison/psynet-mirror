#!/bin/sh
set -eu

if [ "$#" -lt 4 ]; then
  echo "Usage: $0 <image_tag> <workspace_path> <workdir> <command> [args...]" >&2
  exit 1
fi

image_tag="$1"
workspace_path="$2"
workdir="$3"
shift 3

docker run \
  --add-host="postgres:${POSTGRES_IP}" \
  --add-host="redis:${REDIS_IP}" \
  -e HEADLESS=TRUE \
  -e REDIS_URL \
  -e DATABASE_URL \
  -e POSTGRES_DB \
  -e POSTGRES_USER \
  -e POSTGRES_PASSWORD \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_DEFAULT_REGION \
  -e AWS_SECRET_ACCESS_KEY \
  -e CI \
  -e CI_NODE_TOTAL \
  -e CI_NODE_INDEX \
  -e CI_COMMIT_REF_NAME \
  -e "PSYNET_WORKSPACE=${workspace_path}" \
  -v "${PWD}:${workspace_path}" \
  -v "${PWD}/public:/public" \
  -w "${workdir}" \
  "${image_tag}" "$@"
