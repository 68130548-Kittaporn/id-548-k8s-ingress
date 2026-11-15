# CT665 งาน K8s Ingress (id-548)

ให้บริการเว็บบน Kubernetes โดยใช้ NGINX Ingress Controller แยกเส้นทางไปยังแต่ละแอป
รหัสนักศึกษา 68130548 จึงใช้โดเมน `www.id-548.com` และ `admin.id-548.com`

| URL | แอป | หน้าที่ |
|---|---|---|
| `www.id-548.com/about` | app-about | แสดงรูป ชื่อ และรหัสนักศึกษา |
| `www.id-548.com/research` | app-research | แสดงสรุปงานวิจัยที่นำเสนอในวิชาสัมมนา |
| `www.id-548.com/api/<ข้อความ>` | app-api | แสดงข้อความที่ส่งมาเป็นตัวใหญ่กลางจอ |
| `admin.id-548.com` | app-research (path `/edit`) | หน้าแก้ไขสรุปงานวิจัยและบันทึกกลับ |

เข้า `www.id-548.com` จะถูกส่งต่อไปที่ `/about` และทุกหน้ามีเมนูด้านบนสำหรับไปหน้าอื่น

## การทำงานของระบบ

```
Browser
  │  (/etc/hosts ชี้ www.id-548.com, admin.id-548.com ไปที่ IP ของ node)
  ▼
NGINX Ingress Controller
  ├─ www-ingress   host: www.id-548.com
  │     /about, /  → Service app-about    → Deployment app-about (2 pods)
  │     /research  → Service app-research → Deployment app-research (1 pod) → PVC → PV
  │     /api       → Service app-api      → Deployment app-api (2 pods)
  └─ admin-ingress host: admin.id-548.com
        /  (rewrite เป็น /edit) → Service app-research
```

1. เบราว์เซอร์แปลงชื่อโดเมนเป็น IP ของ node ผ่านไฟล์ `/etc/hosts`
2. NGINX Ingress Controller รับ request ที่ port 80 แล้วดูชื่อ host และ path เพื่อเลือก Service ปลายทาง
3. Service (ClusterIP) กระจาย request ไปยัง pod ของแอปนั้น
4. ถ้าเข้า `admin.id-548.com` Ingress จะ rewrite ทุก path เป็น `/edit` ของ app-research

แอปทั้ง 3 ตัวเขียนด้วย Python (ใช้แค่ standard library) รันบน image `python:3.12-alpine`
โค้ดของแต่ละแอปถูกเก็บใน ConfigMap แล้ว mount เข้าไปใน container ที่ `/app` ไม่ต้อง build image และไม่ต้องใช้ registry
ConfigMap สร้างจากไฟล์โค้ดด้วย `configMapGenerator` ของ kustomize (มีอยู่ใน kubectl)
เมื่อแก้โค้ดแล้วสั่ง `kubectl apply -k .` ใหม่ ชื่อ ConfigMap จะเปลี่ยนตาม hash และ Deployment จะ rollout ให้อัตโนมัติ

### การทำงานของแต่ละแอป

- **app-about** อ่านชื่อ รหัส และรายวิชาจาก ConfigMap `student-info` (ผ่าน environment variable) และอ่านรูปจาก ConfigMap `app-about-photo`
- **app-research** อ่านสรุปงานวิจัยจากไฟล์ `/data/summary.json` ซึ่งอยู่บน PersistentVolume
  - `GET /research` แสดงสรุป
  - `GET /edit` แสดงฟอร์มแก้ไข
  - `POST /edit` บันทึกข้อความใหม่ลงไฟล์ ข้อมูลจึงยังอยู่แม้ pod ถูกสร้างใหม่
- **app-api** นำข้อความหลัง `/api/` มาถอดรหัส URL แล้วแสดงเป็นตัวใหญ่กลางจอ มีช่องให้พิมพ์ข้อความใหม่ด้านล่าง

ทุกแอปมี endpoint `/healthz` สำหรับ readinessProbe และ livenessProbe

## ไฟล์ในโปรเจกต์

```
.
├── kustomization.yaml          รวม manifest ทั้งหมด และสร้าง ConfigMap จากไฟล์โค้ด
├── k8s/
│   ├── 00-namespace.yaml       Namespace id-548 และ ConfigMap student-info (ชื่อ รหัส URL)
│   ├── 10-app-about.yaml       Deployment + Service ของ app-about
│   ├── 20-app-research.yaml    PV + PVC + Deployment + Service ของ app-research
│   ├── 30-app-api.yaml         Deployment + Service ของ app-api
│   └── 40-ingress.yaml         Ingress ของ www และ admin
├── apps/
│   ├── app-about/              app.py, photo.jpg
│   ├── app-research/           app.py, summary.json (สรุปงานวิจัยตั้งต้น)
│   └── app-api/                app.py
├── hosts/hosts.example         ตัวอย่างไฟล์ /etc/hosts
├── scripts/
│   ├── deploy.sh               ติดตั้ง ingress-nginx และ deploy ทั้งหมด
│   ├── verify.sh               ตรวจสอบสถานะและทดสอบทุก route
│   └── cleanup.sh              ลบทั้งหมด
└── docs/                       ภาพหน้าจอและรายงาน
```

## รายละเอียด manifest

**app-about และ app-api**
- Deployment 2 replicas คู่กับ Service แบบ ClusterIP
- มี readinessProbe และ livenessProbe ที่ `/healthz`

**app-research**
- เก็บข้อมูลบน PersistentVolume แบบ hostPath (`/mnt/data/id-548-research`) ผูกกับ PVC `research-data`
  ต้องสร้าง PV เองเพราะ cluster ที่ติดตั้งด้วย kubeadm ไม่มี StorageClass ให้ตั้งแต่แรก
- ใช้ 1 replica กับ strategy `Recreate` เพราะ volume เป็นแบบ ReadWriteOnce
- initContainer (busybox) คัดลอก `summary.json` จาก ConfigMap ไปไว้บน volume เฉพาะครั้งแรกที่ยังไม่มีไฟล์
  ถ้ามีไฟล์อยู่แล้วจะไม่เขียนทับ

**Ingress** แยกเป็น 2 ตัว
- `www-ingress` ส่ง `/about`, `/research`, `/api` ไปยัง Service ของแต่ละแอป ส่วน `/` ไปที่ app-about
- `admin-ingress` ใช้ annotation `nginx.ingress.kubernetes.io/rewrite-target: /edit`
  เข้า `admin.id-548.com` แล้วจะไปที่หน้า `/edit` ของ app-research
  ต้องแยกเป็นอีก Ingress เพราะ annotation มีผลกับทุก path ใน Ingress นั้น
- `/edit` ไม่ได้เปิดบน `www.id-548.com` (เข้าแล้วได้ 404) แก้ไขข้อมูลได้ทาง `admin.id-548.com` เท่านั้น

## ขั้นตอนการ deploy

ทำทุกขั้นตอนบนเครื่อง `k8s-control`

### 1. Clone repository

```bash
git clone https://github.com/68130548-Kittaporn/id-548-k8s-ingress.git
cd id-548-k8s-ingress
```

### 2. ติดตั้ง NGINX Ingress Controller

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3/deploy/static/provider/baremetal/deploy.yaml
```

patch ให้ controller ใช้ hostNetwork เพื่อรับ request ที่ port 80 ของ node โดยตรง (URL ไม่ต้องมีเลข port)

```bash
kubectl -n ingress-nginx patch deployment ingress-nginx-controller --type=json -p='[
  {"op":"add","path":"/spec/template/spec/hostNetwork","value":true},
  {"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller
kubectl get ingressclass
```

### 3. Deploy แอป

```bash
kubectl kustomize .        # ดู manifest ที่จะถูกสร้าง
kubectl apply -k .
kubectl -n id-548 rollout status deployment/app-about
kubectl -n id-548 rollout status deployment/app-research
kubectl -n id-548 rollout status deployment/app-api
```

ขั้นตอนที่ 2 และ 3 รันรวมกันได้ด้วยสคริปต์

```bash
bash scripts/deploy.sh
```

ถ้าต้องการเปิดผ่าน NodePort แทน hostNetwork ใช้ `INGRESS_MODE=nodeport bash scripts/deploy.sh` แล้วเข้าที่ port 30080

### 4. แก้ /etc/hosts

ดูว่า controller รันอยู่ที่ node ไหน

```bash
kubectl -n ingress-nginx get pod -o wide
```

เพิ่ม IP ของ node นั้นใน `/etc/hosts` ของเครื่องที่ใช้เปิดเว็บ
(บน Windows แก้ที่ `C:\Windows\System32\drivers\etc\hosts` โดยเปิด Notepad แบบ Administrator)

```bash
echo "192.168.88.130  www.id-548.com admin.id-548.com" | sudo tee -a /etc/hosts
```

controller รันอยู่ที่ k8s-worker2 จึงใช้ IP 192.168.88.130 ตัวอย่างไฟล์เต็มอยู่ที่ `hosts/hosts.example`

### 5. ตรวจสอบการทำงาน

ดูสถานะของ object

```bash
kubectl get nodes -o wide
kubectl -n ingress-nginx get pods,svc -o wide
kubectl -n id-548 get all -o wide
kubectl -n id-548 get ingress,configmap,pvc
kubectl get pv
kubectl -n id-548 describe ingress www-ingress admin-ingress
kubectl -n id-548 get endpoints
kubectl -n id-548 logs deploy/app-research
```

เรียกแต่ละหน้าด้วย curl

```bash
curl http://www.id-548.com/about
curl http://www.id-548.com/research
curl http://www.id-548.com/api/Hello%20I%27m%20June
curl http://admin.id-548.com/
```

เปิดในเบราว์เซอร์ แก้สรุปที่ `admin.id-548.com` กด Save แล้วดูผลที่ `www.id-548.com/research`
จากนั้น restart pod เพื่อตรวจว่าข้อมูลยังอยู่บน PersistentVolume

```bash
kubectl -n id-548 rollout restart deployment/app-research
```

การตรวจสอบทั้งหมดรันรวมได้ด้วยสคริปต์

```bash
bash scripts/verify.sh
```

สคริปต์จะทำสิ่งต่อไปนี้ แล้วสรุปจำนวนข้อที่ผ่าน
- แสดงผล kubectl get และ describe
- ทดสอบทุก route ผ่าน Ingress
- บันทึกข้อมูลทดสอบผ่าน admin แล้ว restart pod เพื่อตรวจว่าข้อมูลยังอยู่ จากนั้นคืนสรุปเดิม
- ตรวจว่า `www.id-548.com/edit` ได้ 404

ภาพหน้าจอผลการทดสอบอยู่ใน `docs/screenshots/`

## ลบออก

```bash
bash scripts/cleanup.sh          # ลบเฉพาะแอป
bash scripts/cleanup.sh --all    # ลบ ingress-nginx ด้วย
```
