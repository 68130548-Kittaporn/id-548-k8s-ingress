#!/usr/bin/env bash
# Deploy the id-548 assignment: NGINX Ingress Controller + 3 apps + 2 Ingress rules.
# Run on the control-plane node (or any machine whose kubectl points at the cluster):
#   ./scripts/deploy.sh                 # bare metal / kubeadm: controller on hostNetwork (port 80)
#   INGRESS_MODE=nodeport ./scripts/deploy.sh   # bare metal, expose on NodePort 30080 instead
# On Docker Desktop / minikube the script picks the right controller manifest itself.
set -euo pipefail
cd "$(dirname "$0")/.."

NS=id-548
INGRESS_VERSION=${INGRESS_VERSION:-controller-v1.11.3}
INGRESS_MODE=${INGRESS_MODE:-hostnetwork}
CTX=$(kubectl config current-context 2>/dev/null || echo unknown)
step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

step "Cluster: context=$CTX"
kubectl get nodes -o wide

# ---------------------------------------------------------------- 1. ingress controller
step "1. Install NGINX Ingress Controller ($INGRESS_VERSION)"
if [[ "$CTX" == minikube* ]]; then
  minikube addons enable ingress
elif [[ "$CTX" == docker-desktop ]]; then
  # Docker Desktop publishes LoadBalancer services on localhost:80
  kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/${INGRESS_VERSION}/deploy/static/provider/cloud/deploy.yaml"
else
  kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/${INGRESS_VERSION}/deploy/static/provider/baremetal/deploy.yaml"
  if [[ "$INGRESS_MODE" == hostnetwork ]]; then
    # Bind the controller straight to port 80/443 of the node it runs on,
    # so the URL is http://www.id-548.com with no :port
    kubectl -n ingress-nginx patch deployment ingress-nginx-controller --type=json -p='[
      {"op":"add","path":"/spec/template/spec/hostNetwork","value":true},
      {"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'
  else
    # Fixed NodePort so /etc/hosts + URL stay predictable: http://www.id-548.com:30080
    kubectl -n ingress-nginx patch svc ingress-nginx-controller --type=json -p='[
      {"op":"replace","path":"/spec/ports/0/nodePort","value":30080},
      {"op":"replace","path":"/spec/ports/1/nodePort","value":30443}]'
  fi
fi

step "Wait for the controller to be Ready"
NS_ING=ingress-nginx
kubectl -n "$NS_ING" rollout status deployment/ingress-nginx-controller --timeout=300s
kubectl -n "$NS_ING" wait --for=condition=complete job --all --timeout=120s 2>/dev/null || true
kubectl get ingressclass

# ---------------------------------------------------------------- 2. apps + ingress
step "2. Apply manifests (kubectl apply -k .)"
# The admission webhook can need a few seconds after the controller is Ready
for i in 1 2 3 4 5 6; do
  kubectl apply -k . && break
  echo "apply failed (webhook not ready yet?), retry $i/6 in 10s"; sleep 10
done

step "3. Wait for the apps"
for d in app-about app-research app-api; do
  kubectl -n "$NS" rollout status "deployment/$d" --timeout=180s
done

# ---------------------------------------------------------------- 3. what to put in /etc/hosts
step "4. Status"
kubectl -n "$NS" get deploy,rs,pods,svc,ingress,pvc -o wide
kubectl get pv id-548-research-pv

IP=$(kubectl -n "$NS_ING" get pod -l app.kubernetes.io/component=controller \
      -o jsonpath='{.items[0].status.hostIP}')
PORT=""
if [[ "$CTX" == docker-desktop ]]; then IP=127.0.0.1
elif [[ "$CTX" == minikube* ]]; then IP=$(minikube ip)
elif [[ "$INGRESS_MODE" != hostnetwork ]]; then PORT=":30080"
fi

cat <<EOF

Add this line to /etc/hosts (Linux) or C:\\Windows\\System32\\drivers\\etc\\hosts (Windows):

    $IP  www.id-548.com admin.id-548.com

Then open:
    http://www.id-548.com${PORT}/about
    http://www.id-548.com${PORT}/research
    http://www.id-548.com${PORT}/api/Hello%20I%27m%20June
    http://admin.id-548.com${PORT}/

Run ./scripts/verify.sh to check every route with curl.
EOF
