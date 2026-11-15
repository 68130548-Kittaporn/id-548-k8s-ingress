#!/usr/bin/env bash
# Remove the assignment. Add --all to also remove the NGINX Ingress Controller.
set -euo pipefail
cd "$(dirname "$0")/.."
kubectl delete -k . --ignore-not-found
# PV uses Retain, so the summary file stays in /mnt/data/id-548-research on the node.
if [[ "${1:-}" == --all ]]; then
  kubectl delete namespace ingress-nginx --ignore-not-found
fi
