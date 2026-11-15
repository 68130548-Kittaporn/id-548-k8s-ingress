# CT665 – K8s Ingress Assignment (id-548)

ให้บริการเว็บด้วย Kubernetes + NGINX Ingress Controller ผ่านโดเมน `www.id-548.com` และ `admin.id-548.com`
(รหัสนักศึกษา 68130548 → 3 ตัวท้าย **548**)

| URL | Service / Pod | หน้าที่ |
|---|---|---|
| `www.id-548.com/about` | `app-about` | แสดงรูป ชื่อ และรหัสนักศึกษา |
| `www.id-548.com/research` | `app-research` | แสดงสรุปงานวิจัยที่นำเสนอในวิชาสัมมนา (300–500 คำ) |
| `www.id-548.com/api/<ข้อความ>` | `app-api` | แสดง `<ข้อความ>` ตัวใหญ่กลางจอ |
| `admin.id-548.com` | `app-research` (path `/edit`) | หน้าแก้ไขสรุปงานวิจัยและบันทึกกลับ |
| `www.id-548.com/` | `app-about` | redirect ไปที่ `/about` |

## สถาปัตยกรรม

```
 Browser ──(/etc/hosts: www/admin.id-548.com → Node IP)──▶ NGINX Ingress Controller (ns: ingress-nginx)
                                                                 │
        ┌──────────────── www-ingress (host www.id-548.com) ─────┼──── admin-ingress (host admin.id-548.com)
        │ /about  /      │ /research            │ /api           │   rewrite-target: /edit
        ▼                ▼                      ▼                ▼
  Service app-about  Service app-research   Service app-api   Service app-research
  (ClusterIP)        (ClusterIP)            (ClusterIP)
        │                │                      │
  Deployment x2      Deployment x1 ── PVC research-data ── PV hostPath /mnt/data/id-548-research
                     (initContainer seed summary.json จาก ConfigMap)
                                        Deployment x2
```

* ทุกแอปเขียนด้วย Python standard library รันบน image `python:3.12-alpine` โดย mount โค้ดเข้ามาจาก **ConfigMap**
  (สร้างด้วย `configMapGenerator` ของ kustomize ที่มีใน kubectl อยู่แล้ว) จึง **ไม่ต้อง build image และไม่ต้องมี registry**
* `app-research` เก็บสรุปงานวิจัยใน PersistentVolume ทำให้ข้อมูลที่แก้จาก `admin.id-548.com` ยังอยู่แม้ pod ถูกสร้างใหม่
* `/edit` ไม่ถูกเปิดบน `www.id-548.com` (ได้ 404) แก้ไขได้ผ่าน `admin.id-548.com` เท่านั้น

## โครงสร้างไฟล์

```
.
├── kustomization.yaml          # รวม manifest + สร้าง ConfigMap จากไฟล์โค้ด  → kubectl apply -k .
├── k8s/
│   ├── 00-namespace.yaml       # Namespace id-548 + ConfigMap student-info (ชื่อ/รหัส)
│   ├── 10-app-about.yaml       # Deployment + Service app-about
│   ├── 20-app-research.yaml    # PV + PVC + Deployment (initContainer) + Service app-research
│   ├── 30-app-api.yaml         # Deployment + Service app-api
│   └── 40-ingress.yaml         # www-ingress (path routing) + admin-ingress (rewrite → /edit)
├── apps/
│   ├── app-about/   app.py, photo.svg   (เปลี่ยนเป็นรูปจริงของตนเอง)
│   ├── app-research/ app.py, summary.json (สรุปงานวิจัยเริ่มต้น)
│   └── app-api/     app.py
├── hosts/hosts.example         # ตัวอย่าง /etc/hosts
├── scripts/
│   ├── deploy.sh               # ติดตั้ง ingress-nginx + deploy ทั้งหมด + บอกบรรทัดที่ต้องใส่ใน /etc/hosts
│   ├── verify.sh               # kubectl get/describe + ทดสอบทุก route ด้วย curl
│   └── cleanup.sh              # ลบทั้งหมด
└── docs/screenshots/           # ภาพหน้าจอผลการทดสอบ
```

## ก่อน deploy: แก้ข้อมูลของตนเอง

1. `k8s/00-namespace.yaml` → แก้ `STUDENT_NAME`, `STUDENT_NAME_EN`
2. ใส่รูปตนเองเป็น `apps/app-about/photo.jpg` แล้วแก้บรรทัด `photo.svg` → `photo.jpg` ใน `kustomization.yaml` (ขนาดไม่เกิน ~700 KB เพราะ ConfigMap จำกัด 1 MiB)
3. ตรวจ/แก้สรุปงานวิจัยใน `apps/app-research/summary.json` (หรือแก้ทีหลังผ่าน `admin.id-548.com`)

## ขั้นตอนการ deploy (kubeadm cluster บน Ubuntu 24.04)

ทำบน `k8s-control`:

```bash
git clone https://github.com/<github-user>/<repo>.git
cd <repo>
chmod +x scripts/*.sh
./scripts/deploy.sh
```

หรือทำทีละคำสั่ง (สิ่งที่ `deploy.sh` ทำ):

```bash
# 1) ติดตั้ง NGINX Ingress Controller (bare metal)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3/deploy/static/provider/baremetal/deploy.yaml

# 2) ให้ controller ฟังพอร์ต 80 ของ node โดยตรง (URL ไม่ต้องมี :port)
kubectl -n ingress-nginx patch deployment ingress-nginx-controller --type=json -p='[
  {"op":"add","path":"/spec/template/spec/hostNetwork","value":true},
  {"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller

# 3) deploy แอปทั้งหมด
kubectl kustomize .            # (ดู manifest ทั้งหมดที่จะถูก apply)
kubectl apply -k .

# 4) รอให้พร้อม
kubectl -n id-548 rollout status deployment/app-about
kubectl -n id-548 rollout status deployment/app-research
kubectl -n id-548 rollout status deployment/app-api

# 5) ดู IP ของ node ที่ controller รันอยู่
kubectl -n ingress-nginx get pod -o wide
```

> ถ้าไม่อยากใช้ hostNetwork: `INGRESS_MODE=nodeport ./scripts/deploy.sh` แล้วเข้าที่ `http://www.id-548.com:30080`

## /etc/hosts

บนเครื่องที่ใช้เปิดเว็บ (Linux: `/etc/hosts`, Windows: `C:\Windows\System32\drivers\etc\hosts`) เพิ่ม:

```
192.168.1.11    www.id-548.com admin.id-548.com
```

(เปลี่ยน `192.168.1.11` เป็น IP ที่ `deploy.sh` แสดง ดูตัวอย่างเต็มที่ `hosts/hosts.example`)

## การตรวจสอบ

```bash
./scripts/verify.sh
```

หรือด้วยมือ:

```bash
kubectl get nodes -o wide
kubectl -n ingress-nginx get pods,svc -o wide
kubectl get ingressclass
kubectl -n id-548 get all -o wide
kubectl -n id-548 get configmap,pvc
kubectl get pv
kubectl -n id-548 get ingress
kubectl -n id-548 describe ingress www-ingress
kubectl -n id-548 describe ingress admin-ingress
kubectl -n id-548 get endpoints
kubectl -n id-548 describe deployment app-research
kubectl -n id-548 logs deploy/app-research

curl http://www.id-548.com/about
curl http://www.id-548.com/research
curl http://www.id-548.com/api/Hello%20I%27m%20June
curl http://admin.id-548.com/
curl -X POST --data-urlencode "title=ทดสอบ" --data-urlencode "body=แก้ไขจาก curl" http://admin.id-548.com/
```

`verify.sh` จะทดสอบด้วยว่า: แก้ไขผ่าน admin แล้วเห็นผลที่ `/research` และหลัง `rollout restart` ข้อมูลยังอยู่ (PV)
จากนั้นคืนค่าสรุปเดิมให้

## ลบทั้งหมด

```bash
./scripts/cleanup.sh          # ลบแอป
./scripts/cleanup.sh --all    # ลบ ingress-nginx ด้วย
```

## ภาพหน้าจอที่ควรเก็บสำหรับรายงาน (docs/screenshots/)

1. `kubectl get nodes -o wide` และ `kubectl -n ingress-nginx get pods -o wide`
2. `kubectl apply -k .` (ผลการสร้าง object)
3. `kubectl -n id-548 get all,ingress,pvc -o wide` และ `kubectl get pv`
4. `kubectl -n id-548 describe ingress www-ingress admin-ingress`
5. `cat /etc/hosts`
6. เบราว์เซอร์: `/about`, `/research`, `/api/<ข้อความ>`, `admin.id-548.com` (ก่อน/หลังกด Save) และ `/research` ที่เห็นข้อความที่แก้แล้ว
7. ผล `./scripts/verify.sh` (PASS ทั้งหมด)
