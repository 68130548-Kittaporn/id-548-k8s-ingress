#!/usr/bin/env bash
# Show the state of every object and test every route through the Ingress.
#   ./scripts/verify.sh                   # uses /etc/hosts
#   IP=192.168.1.11 ./scripts/verify.sh   # bypass /etc/hosts with curl --resolve
#   PORT=30080 ./scripts/verify.sh        # NodePort mode
set -uo pipefail
NS=id-548
PORT=${PORT:-80}
step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

step "kubectl get (namespace $NS)"
kubectl -n $NS get all -o wide
kubectl -n $NS get configmap,pvc
kubectl get pv id-548-research-pv
kubectl -n $NS get ingress

step "kubectl describe ingress"
kubectl -n $NS describe ingress www-ingress admin-ingress

step "Service endpoints (pods behind each Service)"
kubectl -n $NS get endpoints app-about app-research app-api

RESOLVE=()
if [[ -n "${IP:-}" ]]; then
  RESOLVE=(--resolve "www.id-548.com:$PORT:$IP" --resolve "admin.id-548.com:$PORT:$IP")
fi

pass=0; fail=0
check() { # url  expected-text
  local body code
  body=$(curl -s -m 10 "${RESOLVE[@]}" -w '\n%{http_code}' "$1")
  code=${body##*$'\n'}; body=${body%$'\n'*}
  if [[ "$code" == 200 && "$body" == *"$2"* ]]; then
    printf '  \033[32mPASS\033[0m %-48s %s  (contains "%s")\n' "$1" "$code" "$2"; pass=$((pass+1))
  else
    printf '  \033[31mFAIL\033[0m %-48s %s\n' "$1" "$code"; fail=$((fail+1))
  fi
}

step "HTTP checks through the Ingress"
B="http://www.id-548.com:$PORT"; A="http://admin.id-548.com:$PORT"
code=$(curl -s -o /dev/null -w "%{http_code} %{redirect_url}" "${RESOLVE[@]}" "$B/"); echo "  www.id-548.com/ -> $code (redirect to /about)"
check "$B/about"                 "68130548"
check "$B/research"              "Last updated"
check "$B/api/Hello%20I%27m%20June"  "Hello I&#x27;m June"
check "$A/"                      "Edit research summary"

step "Edit round-trip: POST on admin.id-548.com, read back on www.id-548.com/research"
STAMP="verify-$(date +%s)"
BACKUP=$(mktemp)
kubectl -n $NS exec deploy/app-research -c app-research -- cat /data/summary.json > "$BACKUP"   # keep the real summary
curl -s -o /dev/null "${RESOLVE[@]}" -X POST --data-urlencode "title=$STAMP" \
     --data-urlencode "body=round trip test" "$A/"
check "$B/research" "$STAMP"
step "Restart app-research and confirm the edit is still there (PersistentVolume)"
kubectl -n $NS rollout restart deployment/app-research
kubectl -n $NS rollout status deployment/app-research --timeout=120s
# The Ingress controller needs a few seconds to switch to the new pod's IP
# (until then it answers 503), so wait for a 200 before checking.
for i in $(seq 1 30); do
  [[ $(curl -s -o /dev/null -w '%{http_code}' "${RESOLVE[@]}" "$B/research") == 200 ]] && break
  sleep 1
done
echo "  new pod reachable through the Ingress after ${i}s"
check "$B/research" "$STAMP"
kubectl -n $NS exec -i deploy/app-research -c app-research -- sh -c 'cat > /data/summary.json' < "$BACKUP"
rm -f "$BACKUP"
echo "  original summary restored"

step "/edit must not be reachable on www (only via admin.*)"
code=$(curl -s -o /dev/null -w '%{http_code}' "${RESOLVE[@]}" "$B/edit")
if [[ "$code" == 404 ]]; then echo "  PASS www.id-548.com/edit -> 404"; pass=$((pass+1));
else echo "  FAIL www.id-548.com/edit -> $code"; fail=$((fail+1)); fi

printf '\nResult: %d passed, %d failed\n' "$pass" "$fail"
[[ $fail -eq 0 ]]
