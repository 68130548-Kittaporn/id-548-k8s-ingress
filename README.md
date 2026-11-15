# CT665 งาน K8s Ingress (id-548)

งานนี้เป็นการทำเว็บขึ้นบน Kubernetes แล้วใช้ NGINX Ingress แยกเส้นทางไปยังแต่ละแอป
รหัสนักศึกษา 68130548 เลยใช้โดเมน `www.id-548.com` กับ `admin.id-548.com`

เว็บที่ทำมีทั้งหมด 4 ส่วนตามโจทย์

- `www.id-548.com/about` แสดงรูป ชื่อ และรหัสนักศึกษา ทำงานด้วย **app-about**
- `www.id-548.com/research` แสดงสรุปงานวิจัยที่นำเสนอในวิชาสัมมนา ทำงานด้วย **app-research**
- `www.id-548.com/api/<ข้อความ>` เอาข้อความที่พิมพ์มาแสดงตัวใหญ่กลางจอ ทำงานด้วย **app-api**
- `admin.id-548.com` หน้าแก้ไขสรุปงานวิจัยแล้วกดบันทึก ใช้ **app-research** path `/edit`

ถ้าเข้า `www.id-548.com` เฉยๆ จะเด้งไปหน้า `/about` ให้ และทุกหน้ามีเมนูด้านบนให้กดไปหน้าอื่นได้

## แนวคิดที่ใช้

ตอนแรกคิดว่าจะ build Docker image ของแต่ละแอปแล้ว push ขึ้น Docker Hub แต่ cluster ที่ใช้เป็น kubeadm บน VMware
ถ้าต้อง build ใหม่ทุกครั้งที่แก้โค้ดจะเสียเวลามาก เลยเปลี่ยนมาเขียนแอปด้วย Python ที่ใช้แค่ standard library
แล้วเอาไฟล์โค้ดใส่ใน ConfigMap แทน จากนั้น mount เข้าไปใน container ที่ใช้ image `python:3.12-alpine` ธรรมดา
วิธีนี้ไม่ต้อง build image และไม่ต้องมี registry

ส่วนการสร้าง ConfigMap จากไฟล์ ใช้ `configMapGenerator` ของ kustomize ซึ่งมีอยู่ใน kubectl อยู่แล้ว
สั่ง `kubectl apply -k .` ทีเดียวได้ครบทุกอย่าง และถ้าแก้โค้ดแล้ว apply ใหม่ ชื่อ ConfigMap จะเปลี่ยนตาม hash
ทำให้ Deployment rollout ใหม่ให้เอง

ภาพรวมการเชื่อมต่อ

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
│   ├── deploy.sh               สคริปต์ deploy ทั้งหมด
│   ├── verify.sh               สคริปต์ตรวจสอบ
│   └── cleanup.sh              สคริปต์ลบ
└── docs/screenshots/           ภาพหน้าจอผลการทดสอบ
```

## ขั้นตอนที่ทำ

### 1. เตรียมข้อมูลของตัวเอง

- ใส่ชื่อและรหัสใน `k8s/00-namespace.yaml` (ConfigMap `student-info`) แอปจะอ่านค่าพวกนี้เป็น environment variable
- ใส่รูปไว้ที่ `apps/app-about/photo.jpg` รูปต้องไม่ใหญ่เกินไปเพราะ ConfigMap รับได้ไม่เกิน 1 MiB
- เขียนสรุปงานวิจัยลงใน `apps/app-research/summary.json` สรุปมาจากบทความที่นำเสนอในวิชาสัมมนา
  เรื่อง "ระบบอัจฉริยะแนะนำอุปกรณ์แหล่งจ่ายไฟทดแทนด้วยการค้นหาเชิงความหมายและการตรวจสอบความเข้ากันได้ทางไฟฟ้า"

### 2. เขียน manifest

**app-about และ app-api** เป็น Deployment 2 replicas มี Service แบบ ClusterIP คู่กัน
ใส่ readinessProbe กับ livenessProbe ที่ `/healthz` ไว้ด้วย จะได้รู้ว่า pod พร้อมรับ request จริงหรือยัง

**app-research** ต้องเก็บข้อมูลที่แก้จากหน้า admin ไว้ได้ ถ้าเก็บไว้ใน container เฉยๆ พอ pod ถูกสร้างใหม่ข้อมูลจะหาย
เลยทำ PersistentVolume แบบ hostPath (`/mnt/data/id-548-research`) กับ PVC ไว้
เพราะ kubeadm ไม่มี StorageClass ให้ตั้งแต่แรก ต้องสร้าง PV เอง

- ใช้ replicas 1 กับ strategy `Recreate` เพราะ volume เป็น ReadWriteOnce ให้ pod เก่าปล่อย volume ก่อน pod ใหม่จะขึ้น
- ใส่ initContainer (busybox) คอยเช็กว่ามีไฟล์ `summary.json` ใน volume หรือยัง ถ้ายังไม่มีจะ copy ตัวตั้งต้นจาก ConfigMap มาให้
  ถ้ามีอยู่แล้วก็ไม่ทับ ข้อมูลที่เคยแก้ไว้จะไม่หาย

**Ingress** แยกเป็น 2 ตัว

- `www-ingress` ใช้ path routing ธรรมดา `/about`, `/research`, `/api` ไปแต่ละ Service ส่วน `/` ไปที่ app-about
- `admin-ingress` ใส่ annotation `nginx.ingress.kubernetes.io/rewrite-target: /edit`
  ทำให้เข้า `admin.id-548.com` แล้วไปเจอหน้า `/edit` ของ app-research เลย
  ที่ต้องแยกออกมาเป็นอีกตัวเพราะ annotation rewrite มีผลกับทั้ง Ingress ถ้ารวมกับ www จะทำให้ path อื่นเพี้ยน

ตั้งใจไม่เปิด `/edit` บน `www.id-548.com` ถ้าลองเข้า `www.id-548.com/edit` จะได้ 404
คนทั่วไปเลยแก้ข้อมูลไม่ได้ ต้องเข้าทาง admin เท่านั้น

### 3. ติดตั้ง NGINX Ingress Controller

ทำบนเครื่อง `k8s-control`

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3/deploy/static/provider/baremetal/deploy.yaml
```

แบบ baremetal จะเปิด controller เป็น NodePort ซึ่งต้องพิมพ์ port ต่อท้าย URL
เลย patch ให้ controller ใช้ hostNetwork จะได้รับ request ที่ port 80 ของ node ได้โดยตรง

```bash
kubectl -n ingress-nginx patch deployment ingress-nginx-controller --type=json -p='[
  {"op":"add","path":"/spec/template/spec/hostNetwork","value":true},
  {"op":"replace","path":"/spec/template/spec/dnsPolicy","value":"ClusterFirstWithHostNet"}]'
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller
kubectl get ingressclass
```

### 4. Deploy แอป

```bash
git clone https://github.com/<github-user>/<repo>.git
cd <repo>
kubectl kustomize .        # ดู manifest ที่จะถูกสร้างก่อน
kubectl apply -k .
kubectl -n id-548 rollout status deployment/app-about
kubectl -n id-548 rollout status deployment/app-research
kubectl -n id-548 rollout status deployment/app-api
```

ขั้นตอนที่ 3 กับ 4 รวมไว้ใน `scripts/deploy.sh` แล้ว รัน `bash scripts/deploy.sh` ครั้งเดียวก็ได้
(ถ้าไม่อยากใช้ hostNetwork สั่ง `INGRESS_MODE=nodeport bash scripts/deploy.sh` แล้วเข้าที่ port 30080 แทน)

### 5. แก้ /etc/hosts

ดูก่อนว่า controller รันอยู่ที่ node ไหน

```bash
kubectl -n ingress-nginx get pod -o wide
```

แล้วเอา IP ของ node นั้นไปใส่ใน `/etc/hosts` (ถ้าเปิดเว็บจาก Windows แก้ที่ `C:\Windows\System32\drivers\etc\hosts` ต้องเปิด Notepad แบบ Administrator)

```
192.168.1.11    www.id-548.com admin.id-548.com
```

IP ข้างบนเป็นตัวอย่าง ต้องเปลี่ยนตาม IP ของ node จริง ไฟล์เต็มดูได้ที่ `hosts/hosts.example`

### 6. ตรวจสอบการทำงาน

ดูสถานะ object ต่างๆ

```bash
kubectl get nodes -o wide
kubectl -n ingress-nginx get pods,svc -o wide
kubectl -n id-548 get all -o wide
kubectl -n id-548 get configmap,pvc
kubectl get pv
kubectl -n id-548 get ingress
kubectl -n id-548 describe ingress www-ingress
kubectl -n id-548 describe ingress admin-ingress
kubectl -n id-548 get endpoints
kubectl -n id-548 logs deploy/app-research
```

ลองเรียกแต่ละหน้าด้วย curl

```bash
curl http://www.id-548.com/about
curl http://www.id-548.com/research
curl http://www.id-548.com/api/Hello%20I%27m%20June
curl http://admin.id-548.com/
```

จากนั้นเปิดในเบราว์เซอร์ทีละหน้า ลองแก้สรุปที่ `admin.id-548.com` กด Save แล้วกลับไปดูที่ `/research` ว่าข้อความเปลี่ยนจริง

เพื่อเช็กว่าข้อมูลไม่หายเมื่อ pod ถูกสร้างใหม่ ลอง restart แล้วเปิดดูอีกรอบ

```bash
kubectl -n id-548 rollout restart deployment/app-research
```

ทั้งหมดนี้รวมไว้ใน `scripts/verify.sh` ด้วย สคริปต์จะลองบันทึกข้อมูลทดสอบ restart pod แล้วเช็กว่ายังอยู่
เสร็จแล้วจะคืนสรุปเดิมให้ และเช็กว่า `www.id-548.com/edit` ได้ 404

ภาพหน้าจอผลการทดสอบอยู่ใน `docs/screenshots/`

## ปัญหาที่เจอระหว่างทำ

- **ไฟล์รูปชื่อ `photo.jpg.jpg`** Windows ซ่อนนามสกุลไฟล์ไว้ ตั้งชื่อว่า photo.jpg แต่จริงๆ ได้ .jpg ซ้อนสองรอบ
  ทำให้ kustomize หาไฟล์ไม่เจอ ต้องเปลี่ยนชื่อใหม่
- **เครื่องหมาย `'` ใน URL** ตอนเปลี่ยนลิงก์ตัวอย่างเป็น `Hello I'm June` เครื่องหมาย `'` ไปทำให้สตริงใน Python ปิดก่อน
  แอป app-api เลยรันไม่ขึ้น และคำสั่ง curl ใน bash ก็พังด้วย แก้โดยเขียนเป็น `%27` แทน (`Hello%20I%27m%20June`)
- **ลิงก์เมนูบนหน้า admin** หน้า admin อยู่คนละโดเมน และทุก path ถูก rewrite ไป `/edit`
  ถ้าใช้ลิงก์แบบ `/about` จะวนกลับมาหน้าแก้ไขตลอด เลยต้องใช้ URL เต็ม (`WWW_URL`, `ADMIN_URL` ใน ConfigMap)
- **PV แบบ hostPath** ข้อมูลจะอยู่บน node ที่ pod รันอยู่ ถ้า pod ย้ายไป node อื่นจะไม่เห็นข้อมูลที่แก้ไว้
  สำหรับงานนี้ใช้ได้ แต่ถ้าใช้งานจริงควรใช้ NFS หรือ storage ที่แชร์กันได้ทุก node

## ลบออก

```bash
bash scripts/cleanup.sh          # ลบเฉพาะแอป
bash scripts/cleanup.sh --all    # ลบ ingress-nginx ด้วย
```
