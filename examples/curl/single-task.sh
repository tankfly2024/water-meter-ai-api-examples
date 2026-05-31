#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

API_BASE="${WATERMETER_API_BASE:-https://meter.smartwebpark.com}"
API_KEY="${WATERMETER_API_KEY:-}"
IMAGE_PATH="${IMAGE_PATH:-${ROOT_DIR}/sample-images/example.jpg}"
if [[ "${IMAGE_PATH}" != /* && ! "${IMAGE_PATH}" =~ ^[A-Za-z]:[\\/].* ]]; then
  IMAGE_PATH="${ROOT_DIR}/${IMAGE_PATH#./}"
fi
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-2}"
POLL_TIMEOUT_SECONDS="${POLL_TIMEOUT_SECONDS:-120}"

if [[ -z "${API_KEY}" ]]; then
  echo "Set WATERMETER_API_KEY in .env or the environment." >&2
  exit 1
fi

if [[ ! -f "${IMAGE_PATH}" ]]; then
  echo "Image not found: ${IMAGE_PATH}" >&2
  exit 1
fi

echo "Checking API status..."
curl -fsS "${API_BASE}/api/open/ai-status" \
  -H "Authorization: Bearer ${API_KEY}" | jq .

echo "Checking quota..."
curl -fsS "${API_BASE}/api/open/quota" \
  -H "Authorization: Bearer ${API_KEY}" | jq .

echo "Uploading image..."
CREATE_RESPONSE="$(curl -fsS -X POST "${API_BASE}/api/open/tasks" \
  -H "Authorization: Bearer ${API_KEY}" \
  -F "file=@${IMAGE_PATH}")"
echo "${CREATE_RESPONSE}" | jq .

TASK_ID="$(echo "${CREATE_RESPONSE}" | jq -r '.task_id // empty')"
if [[ -z "${TASK_ID}" ]]; then
  echo "No task_id returned." >&2
  exit 1
fi

deadline=$((SECONDS + POLL_TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  RESPONSE="$(curl -fsS "${API_BASE}/api/open/tasks/${TASK_ID}" \
    -H "Authorization: Bearer ${API_KEY}")"
  STATUS="$(echo "${RESPONSE}" | jq -r '.status // empty')"
  echo "${RESPONSE}" | jq .

  if [[ "${STATUS}" == "done" || "${STATUS}" == "failed" ]]; then
    exit 0
  fi

  sleep "${POLL_INTERVAL_SECONDS}"
done

echo "Timed out waiting for task ${TASK_ID}." >&2
exit 1
