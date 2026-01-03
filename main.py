# main.py chay
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, time, timedelta
import pytz
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Import danh sách đài từ file stations.py
from stations import stations

# --- Config / env ---
vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
today_str = datetime.now(vn_tz).strftime("%Y-%m-%d")
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, f"chuong_trinh_truc_tiep_{today_str}.txt")

EMAIL_USER = os.environ.get("EMAIL_USER")      # Gmail address (set trong GitHub Secrets)
EMAIL_PASS = os.environ.get("EMAIL_PASS")      # Gmail app password 16 ký tự (set trong GitHub Secrets)

if not EMAIL_USER or not EMAIL_PASS:
    raise SystemExit("Thiếu EMAIL_USER hoặc EMAIL_PASS trong environment variables.")

# parse recipients    
recipients = ["nguyenthithanhtam7382@gmail.com", "thanhtam2a@yahoo.com", "Fromtrawithlove@gmail.com", "Camvu86@gmail.com", "Uanvq1982@gmail.com", "duyenhuynh1907@gmail.com"]

print(f"Đã nạp {len(stations)} đài. ")

# --- Thu thập lịch phát sóng ---
collected = []

for name, url in stations.items():
    try:
        r = requests.get(url, timeout=12)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "lxml")

        date_tag = soup.select_one(".date") or soup.select_one(".schedule-date")
        date_text_raw = date_tag.get_text(strip=True) if date_tag else today_str

        def normalize_date(dt_raw):
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
                try:
                    dt = datetime.strptime(dt_raw, fmt)
                    dt_vn = dt.replace(tzinfo=pytz.utc).astimezone(vn_tz)
                    return dt_vn.strftime("%Y-%m-%d"), dt_vn.strftime("%d/%m/%Y")
                except:
                    continue
            return dt_raw, dt_raw

        date_text, date_fmt = normalize_date(date_text_raw)

        station_rows = []
        for row in soup.select("table tr"):
            cols = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cols) == 2:
                station_rows.append((cols[0], cols[1]))

        for idx, (time_text, program) in enumerate(station_rows):
            prog_lower = program.lower()
            if time_text == "00:55":
                continue
            if not ("trực tiếp" in prog_lower or "tường thuật trực tiếp" in prog_lower or "truc tiep" in prog_lower or "thtt" in prog_lower):
                continue
            if any(x in prog_lower for x in ["sông vàm ngày mới", "xổ số", "thể thao", "thời sự", "tiếp sóng trực tiếp"]):
                continue

            try:
                t1 = datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M")
            except:
                try:
                    time_fixed = time_text.replace("h", ":")
                    t1 = datetime.strptime(f"{date_text} {time_fixed}", "%Y-%m-%d %H:%M")
                except:
                    continue

            t2 = None
            if idx + 1 < len(station_rows):
                next_time_text, _ = station_rows[idx + 1]
                try:
                    t2 = datetime.strptime(f"{date_text} {next_time_text}", "%Y-%m-%d %H:%M")
                except:
                    try:
                        next_time_fixed = next_time_text.replace("h", ":")
                        t2 = datetime.strptime(f"{date_text} {next_time_fixed}", "%Y-%m-%d %H:%M")
                    except:
                        t2 = None

            if t2 is None:
                t2 = datetime.combine(t1.date(), time(23, 59, 59))

            delta = t2 - t1
            if delta.total_seconds() < 0:
                delta = delta + timedelta(days=1)

            total_seconds = int(delta.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60

            line = f"{date_fmt} {time_text} {name} {program} → thời lượng {hours}h{minutes}m"
            collected.append((t1, line))
            stt = stt + 1

    except Exception as e:
        print("Lỗi khi xử lý:", name, e)

collected.sort(key=lambda x: x[0])
lines = []
# --- đánh số thứ tự sau khi sort ---
lines = [f"{idx}. {line}" for idx, (_, line) in enumerate(collected, start=1)]

body_text = "\n".join(lines) if lines else "Không tìm thấy chương trình trực tiếp nào hôm nay."

# Save to txt
with open(output_path, "w", encoding="utf-8") as f:
    f.write(body_text)

print(f"Đã lưu {len(lines)} dòng vào {output_path}")

# --- Gửi email ---
subject = f"Lịch trực tiếp {today_str} ({len(lines)} mục)"

msg = MIMEMultipart()
msg["From"] = EMAIL_USER
msg["To"] = ", ".join(recipients)
msg["Subject"] = subject
msg.attach(MIMEText(body_text, "plain", "utf-8"))

# attach file
with open(output_path, "rb") as f:
    part = MIMEBase("application", "octet-stream")
    part.set_payload(f.read())
encoders.encode_base64(part)
part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(output_path)}"')
msg.attach(part)

context = ssl.create_default_context()
try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, recipients, msg.as_string())
    print("✅ Email đã gửi tới:", recipients)
except Exception as e:
    print("❌ Lỗi khi gửi email:", e)
    raise
