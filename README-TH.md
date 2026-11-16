# arthur-endpoints — ที่อยู่เว็บ panel ของแอป Arthur VPN

แอป Arthur VPN (ตั้งแต่ build 103) อ่านไฟล์ `endpoints.json` ใน repo นี้ เพื่อรู้ว่าจะคุยกับเว็บ panel ที่โดเมนไหน
ย้ายเว็บไปโดเมนใหม่ได้โดยไม่ต้องออกแอปใหม่

ไฟล์นี้เปิดสาธารณะได้ (มีแค่ชื่อโดเมน) แอปเชื่อเฉพาะไฟล์ที่ **เซ็นด้วยกุญแจ k1 หรือ k2** ที่ฝังอยู่ในแอปเท่านั้น
ใครแก้ไฟล์โดยไม่มีกุญแจ แอปจะไม่ใช้

## ตั้งค่าครั้งแรก (ทำครั้งเดียว)
1. สร้าง repo **สาธารณะ** ชื่อ `TspKchn/arthur-endpoints` (ชื่อต้องตรงนี้ เพราะฝังในแอปแล้ว)
2. อัปโหลดไฟล์ทั้งหมดในโฟลเดอร์นี้ขึ้น branch `main` (รวม `.github/workflows/sign.yml`, `keys/`, `panel.json`, `endpoints.json`, `sign.py`)
3. Settings → Secrets and variables → Actions → New repository secret
   - Name: `ENDPOINTS_K1`
   - Value: เปิดไฟล์ `D:\Project\PrivateKeys\Arthur-Endpoints\k1-private.pem` ด้วย Notepad แล้ววางทั้งไฟล์ (รวมบรรทัด BEGIN/END)
4. Actions → "Sign panel endpoints" → Run workflow เพื่อทดสอบว่าเซ็นผ่าน
5. หลังวาง Secret แล้ว ย้ายไฟล์กุญแจทั้งสองออกจากเครื่อง:
   - `k1-private.pem` ลบได้ (อยู่ใน GitHub Secret แล้ว) หรือเก็บสำรองใน USB
   - `k2-private.pem` **ห้ามหาย** เก็บใน USB/ที่เก็บ offline เท่านั้น (ใช้ตอนต้องเปลี่ยนกุญแจ ถ้า k1 หลุด) ห้ามใส่ GitHub

## ย้ายเว็บไปโดเมนใหม่
1. เตรียมเว็บที่โดเมนใหม่ให้ใช้งานได้ก่อน (HTTPS ถูกต้อง, `/index.php` และ `/arthur.json` ตอบปกติ)
2. แก้ `panel.json` บน GitHub ให้โดเมนใหม่อยู่ **บรรทัดแรก** เช่น
   ```json
   {
     "panels": ["https://panel.vpnover.top", "https://panel.xq-vpn.com"],
     "revoked_keys": []
   }
   ```
3. กด Commit → ระบบเซ็น `endpoints.json` ให้เองภายใน 1–2 นาที (เลขรุ่น seq เพิ่มอัตโนมัติ)
4. แอปจะเช็กไฟล์ทุก 12 ชั่วโมง และเช็กทันทีเมื่อติดต่อเว็บเดิมไม่ได้ (ไม่เกินทุก 10 นาที)

ไฟล์เซ็นใหม่อัตโนมัติทุกต้นเดือน (ไฟล์มีอายุ 90 วัน) ไม่ต้องทำอะไรเอง

## ปล่อยอัปเดตโปรแกรม Windows (ตั้งแต่ r12)
1. อัปโหลดไฟล์ติดตั้ง (เช่น `Arthur-VPN-1.0.0-Install-r13.exe`) ขึ้นที่ใดก็ได้ที่เป็น https และดาวน์โหลดได้ตรง ๆ เช่น GitHub Releases ของ repo นี้
2. แก้/สร้าง `windows.json`:
   ```json
   {
     "version": "1.0.0.12",
     "label": "r13",
     "url": "https://github.com/TspKchn/arthur-endpoints/releases/download/r13/Arthur-VPN-1.0.0-Install-r13.exe",
     "min_version": "",
     "notes": "สิ่งที่เปลี่ยนในรุ่นนี้ (ไม่เกิน 600 ตัวอักษร)"
   }
   ```
   - `version` ต้องตรงกับ FileVersion ของโปรแกรมใหม่ (4 ส่วน)
   - `min_version` ว่าง = แค่แจ้งเตือน; ใส่เลขรุ่น = เครื่องที่ต่ำกว่านั้น **ต้องอัปเดตก่อนใช้งาน**
3. Commit → GitHub ดาวน์โหลดไฟล์ติดตั้ง คำนวณ SHA-256 และขนาดเอง แล้วเซ็นเป็น `windows-update.json`
4. โปรแกรมเช็กตอนเปิดและทุก 6 ชั่วโมง: ขึ้นหน้าต่างอัปเดต → ดาวน์โหลดให้ครบและตรวจก่อน (VPN ยังใช้ได้) → ตัดการเชื่อมต่อ → เปิดตัวติดตั้งที่มีแถบความคืบหน้า → เปิดโปรแกรมใหม่ให้เอง
   ระหว่างติดตั้งถ้าผู้ใช้เปิดโปรแกรมเอง จะขึ้นข้อความให้รอ

## ถ้ากุญแจ k1 หลุด
1. ใส่ `"revoked_keys": ["k1"]` ใน `panel.json`
2. เซ็นบนเครื่องด้วย k2 จาก USB:
   `python sign.py --key-id k2 --key-file <ที่อยู่ไฟล์ k2-private.pem>` แล้ว commit `endpoints.json`
3. แอปที่เห็นไฟล์นี้จะไม่เชื่อ k1 อีก จากนั้นออกแอปรุ่นใหม่พร้อมกุญแจชุดใหม่

## สิ่งที่ไฟล์นี้เปลี่ยนไม่ได้ (ต้องทำเองเมื่อย้ายโดเมน)
- ลิงก์นโยบายความเป็นส่วนตัวใน Play Console และ app-ads.txt ของ AdMob
- URL รับยืนยันรางวัลโฆษณา (AdMob SSV) ที่ตั้งใน AdMob
- `api_url` ของ VPS แต่ละเครื่อง และรายชื่อโดเมนที่อนุญาตในอุโมงค์ FREE (ตั้งในเว็บแอดมิน)
- แอปเวอร์ชันก่อน build 103 ยังใช้ panel.xq-vpn.com ตายตัว
