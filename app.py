"""
EventHub - Final Event Management System
All 8 features fully implemented and tested.
Run: python app.py  →  http://localhost:5000
Admin: admin / Admin@2025
Email: set SMTP_USER and SMTP_PASS env vars (Gmail App Password)
"""
from flask import Flask, render_template, request, redirect, send_file, url_for, session, flash, jsonify
import sqlite3, os, re, io, base64, threading, time, uuid, functools
import qrcode
from datetime import datetime, date, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas as pdf_canvas
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'eventhub_2025_final_key')

DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'events.db')

# ─── SMTP CONFIG ─────────────────────────────────────────────────────────────
# Get Gmail App Password:
#   Google Account → Security → 2-Step Verification ON → App Passwords → Generate
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = os.getenv('SMTP_USER', '')   # set: export SMTP_USER=you@gmail.com
SMTP_PASS = os.getenv('SMTP_PASS', '')   # set: export SMTP_PASS=xxxx xxxx xxxx xxxx

ADMIN_USERNAME = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASS', 'Admin@2025')

# ─── EVENT VISUAL THEMES ─────────────────────────────────────────────────────
THEMES = {
    'Technology':  {'grad': '#667eea,#764ba2', 'icon': '🤖', 'hex': '#667eea'},
    'Workshop':    {'grad': '#11998e,#38ef7d', 'icon': '💻', 'hex': '#11998e'},
    'Business':    {'grad': '#f7971e,#ffd200', 'icon': '🚀', 'hex': '#f7971e'},
    'Competition': {'grad': '#f953c6,#b91d73', 'icon': '🏆', 'hex': '#f953c6'},
    'Arts':        {'grad': '#f093fb,#f5576c', 'icon': '🎨', 'hex': '#f093fb'},
    'Science':     {'grad': '#4facfe,#00f2fe', 'icon': '🔬', 'hex': '#4facfe'},
    'Health':      {'grad': '#43e97b,#38f9d7', 'icon': '❤️',  'hex': '#43e97b'},
    'General':     {'grad': '#a18cd1,#fbc2eb', 'icon': '🎫', 'hex': '#a18cd1'},
}

def get_theme(cat): return THEMES.get(cat, THEMES['General'])

# ════════════════════════════════════════════════════════════════════════════
# DATABASE
# ════════════════════════════════════════════════════════════════════════════
def get_db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    con = get_db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        venue TEXT NOT NULL,
        host TEXT NOT NULL,
        co_host TEXT,
        organizer TEXT NOT NULL,
        category TEXT DEFAULT 'General',
        is_paid INTEGER DEFAULT 0,
        fee REAL DEFAULT 0,
        capacity INTEGER DEFAULT 200,
        upi TEXT DEFAULT 'events@upi',
        status TEXT DEFAULT 'upcoming',
        created_at TEXT DEFAULT(datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS registrations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        reg_id TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        college TEXT,
        dept TEXT,
        year TEXT,
        reg_type TEXT DEFAULT 'free',
        pay_status TEXT DEFAULT 'na',
        txn_id TEXT,
        amount REAL DEFAULT 0,
        reg_at TEXT DEFAULT(datetime('now')),
        reminded INTEGER DEFAULT 0,
        pay_reminded INTEGER DEFAULT 0,
        FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        reg_id TEXT NOT NULL UNIQUE,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        feedback TEXT,
        task_completed INTEGER DEFAULT 0,
        task_description TEXT,
        att_time TEXT DEFAULT(datetime('now')),
        eligible INTEGER DEFAULT 0,
        FOREIGN KEY(event_id) REFERENCES events(id)
    );
    CREATE TABLE IF NOT EXISTS certificates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        reg_id TEXT NOT NULL UNIQUE,
        cert_id TEXT UNIQUE NOT NULL,
        issued_at TEXT DEFAULT(datetime('now')),
        FOREIGN KEY(event_id) REFERENCES events(id)
    );
    CREATE TABLE IF NOT EXISTS feedback(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        reg_id TEXT UNIQUE NOT NULL,
        rating INTEGER DEFAULT 5,
        comment TEXT,
        created_at TEXT DEFAULT(datetime('now'))
    );
    """)

    if con.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0:
        td = date.today()
        def d(n): return (td + timedelta(days=n)).isoformat()
        rows = [
            ("National AI & ML Summit",
             "Premier AI/ML conference with top researchers, live demos, and networking sessions.",
             d(15), "09:00 AM", "Chennai Trade Centre, Hall A",
             "Dr. Priya Sharma", "Prof. Rahul Mehta", "TechFusion Society",
             "Technology", 1, 999, 500, "techsummit@upi", "upcoming"),
            ("Web Development Bootcamp",
             "Intensive hands-on bootcamp: React, Node.js, databases, and cloud deployment.",
             d(0), "10:00 AM", "IIT Madras Research Park",
             "Arjun Nair", "Sneha Krishnan", "CodeCraft India",
             "Workshop", 0, 0, 200, "", "ongoing"),
            ("Startup Conclave 2025",
             "Connect with top entrepreneurs, pitch your idea, and learn startup secrets.",
             d(28), "11:00 AM", "ITC Grand Chola, Chennai",
             "Vikram Anand", "Meera Pillai", "StartupHub TN",
             "Business", 1, 1499, 300, "startuphub@upi", "upcoming"),
            ("Data Science Workshop",
             "Python-based data analysis, ML modelling, and real-world visualization projects.",
             d(7), "02:00 PM", "Anna University, Chennai",
             "Dr. Karthik Rajan", None, "DataMinds Club",
             "Workshop", 0, 0, 150, "", "upcoming"),
            ("Cybersecurity Hackathon",
             "24-hour ethical hacking hackathon: vulnerability assessment and security solutions.",
             d(21), "08:00 AM", "SRM Institute of Technology",
             "Ananya Subramanian", "Dev Patel", "CyberGuard Association",
             "Competition", 1, 599, 400, "cyberhack@upi", "upcoming"),
            ("Photography Fest",
             "Workshops, exhibitions and competitions led by award-winning photographers.",
             d(10), "09:30 AM", "Lalit Kala Akademi, Chennai",
             "Riya Thomas", "Suresh Kumar", "Lens & Light Society",
             "Arts", 0, 0, 250, "", "upcoming"),
            ("Healthcare Innovation Summit",
             "Explore health-tech with doctors, engineers and health-tech entrepreneurs.",
             d(35), "10:00 AM", "Apollo Hospitals Convention Centre",
             "Dr. Anand Kumar", "Dr. Preethi Rajan", "MedTech India",
             "Health", 1, 799, 300, "medtech@upi", "upcoming"),
        ]
        con.executemany("""INSERT INTO events(name,description,date,time,venue,host,co_host,
            organizer,category,is_paid,fee,capacity,upi,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    con.commit()
    con.close()

# ════════════════════════════════════════════════════════════════════════════
# VALIDATORS & HELPERS
# ════════════════════════════════════════════════════════════════════════════
def valid_gmail(e): return bool(re.match(r'^[\w._%+-]+@gmail\.com$', e))
def valid_phone(p): return bool(re.match(r'^\d{10}$', p))
def valid_future(ds):
    try: return datetime.strptime(ds,'%Y-%m-%d').date() >= date.today()
    except: return False

def is_event_day(ev):
    """Feature 1: True only when today == event date"""
    try: return datetime.strptime(ev['date'],'%Y-%m-%d').date() == date.today()
    except: return False

def is_future_or_today(ev):
    try: return datetime.strptime(ev['date'],'%Y-%m-%d').date() >= date.today()
    except: return False

def get_event(eid):
    c = get_db(); ev = c.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone(); c.close(); return ev

def get_reg(rid):
    c = get_db(); r = c.execute("SELECT * FROM registrations WHERE reg_id=?", (rid,)).fetchone(); c.close(); return r

def new_rid(): return f"REG-{uuid.uuid4().hex[:8].upper()}"

def make_qr(data):
    qr = qrcode.QRCode(version=1, box_size=7, border=4)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    buf = io.BytesIO(); img.save(buf,"PNG"); buf.seek(0)
    return base64.b64encode(buf.read()).decode()

def admin_only(f):
    @functools.wraps(f)
    def wrap(*a, **kw):
        if not session.get('admin'): return redirect(url_for('admin_login'))
        return f(*a, **kw)
    return wrap

# ════════════════════════════════════════════════════════════════════════════
# EMAIL SYSTEM  (Feature 5 – Gmail App Password)
# ════════════════════════════════════════════════════════════════════════════
def html_email(title, accent, body):
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f3ff;font-family:'Segoe UI',Arial,sans-serif;">
<div style="max-width:600px;margin:32px auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(108,92,231,.12);">
  <div style="background:{accent};padding:30px 32px;text-align:center;">
    <div style="font-size:30px;margin-bottom:6px;">⚡</div>
    <h1 style="color:#fff;margin:0;font-size:21px;font-weight:700;">{title}</h1>
    <p style="color:rgba(255,255,255,.8);margin:5px 0 0;font-size:12px;">EventHub — Event Management System</p>
  </div>
  <div style="padding:30px 32px;color:#333;line-height:1.75;font-size:15px;">{body}</div>
  <div style="background:#f8f7ff;padding:18px 32px;border-top:1px solid #ede9ff;text-align:center;font-size:11px;color:#999;">
    ⚡ EventHub Automated Notification — Do not reply to this email
  </div>
</div></body></html>"""

def send_email(to, subject, html_body, attach_bytes=None, attach_name=None):
    """Feature 5: Gmail App Password SMTP with full error handling"""
    # Validate email first
    if not re.match(r'^[\w._%+-]+@[\w.-]+\.[a-zA-Z]{2,}$', to):
        print(f"[EMAIL] Invalid address: {to}"); return False

    if not SMTP_USER:
        print(f"[EMAIL DEMO] To:{to} | {subject}"); return True

    try:
        msg = MIMEMultipart('mixed')
        msg['Subject'] = subject
        msg['From']    = f"EventHub <{SMTP_USER}>"
        msg['To']      = to
        alt = MIMEMultipart('alternative')
        alt.attach(MIMEText(html_body, 'html', 'utf-8'))
        msg.attach(alt)
        if attach_bytes and attach_name:
            part = MIMEBase('application','octet-stream')
            part.set_payload(attach_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{attach_name}"')
            msg.attach(part)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as srv:
            srv.ehlo(); srv.starttls(); srv.ehlo()
            srv.login(SMTP_USER, SMTP_PASS)   # ← Gmail App Password
            srv.sendmail(SMTP_USER, to, msg.as_string())
        print(f"[EMAIL OK] {to} | {subject}"); return True
    except smtplib.SMTPAuthenticationError:
        print("[EMAIL ERROR] Auth failed. Use Gmail App Password (Google Account → Security → App Passwords).")
        return False
    except smtplib.SMTPException as e:
        print(f"[EMAIL ERROR] SMTP: {e}"); return False
    except Exception as e:
        print(f"[EMAIL ERROR] {e}"); return False

def bg(fn, *a, **kw): threading.Thread(target=fn, args=a, kwargs=kw, daemon=True).start()

def mail_registration(name, email, ev_name, rid, ev_date, ev_time, venue, is_paid=False):
    body = f"""<p>Dear <strong>{name}</strong>,</p>
    <p>Your registration for <strong style="color:#6c5ce7">{ev_name}</strong> is confirmed! 🎉</p>
    <div style="background:#f8f7ff;border-left:4px solid #6c5ce7;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0;">
      <p><strong>📋 Reg ID:</strong> <span style="font-family:monospace;color:#6c5ce7;font-size:16px;font-weight:700;">{rid}</span></p>
      <p><strong>📅 Date:</strong> {ev_date} at {ev_time}</p>
      <p><strong>📍 Venue:</strong> {venue}</p>
    </div>
    {"<p><strong>⚠️ Note:</strong> Your seat is reserved — please complete payment to confirm.</p>" if is_paid else "<p>Carry your Registration ID on event day. A reminder will arrive 24 hours before!</p>"}
    <p style="color:#00b894;font-weight:600;">— EventHub Team</p>"""
    bg(send_email, email, f"Registration Confirmed – {ev_name}",
       html_email("✅ Registration Confirmed!", "linear-gradient(135deg,#6c5ce7,#a29bfe)", body))

def mail_payment(name, email, ev_name, rid, amount, txn, ev_date, venue):
    body = f"""<p>Dear <strong>{name}</strong>,</p>
    <p>Payment for <strong style="color:#e17055">{ev_name}</strong> received! 💳</p>
    <div style="background:#fff9f0;border-left:4px solid #e17055;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0;">
      <p><strong>📋 Reg ID:</strong> <span style="font-family:monospace;color:#6c5ce7;">{rid}</span></p>
      <p><strong>💰 Amount:</strong> <span style="color:#e17055;font-size:20px;font-weight:700;">₹{amount:.0f}</span></p>
      <p><strong>🔖 TXN:</strong> <span style="font-family:monospace;">{txn}</span></p>
      <p><strong>📅 Date:</strong> {ev_date} | <strong>📍</strong> {venue}</p>
    </div>
    <p style="color:#00b894;font-weight:600;">Seat confirmed! — EventHub Team</p>"""
    bg(send_email, email, f"Payment Confirmed – {ev_name}",
       html_email("💳 Payment Confirmed!", "linear-gradient(135deg,#e17055,#fdcb6e)", body))

def mail_reminder(name, email, ev_name, rid, ev_date, ev_time, venue):
    body = f"""<p>Dear <strong>{name}</strong>,</p>
    <p><strong style="color:#fdcb6e">{ev_name}</strong> is <strong>tomorrow!</strong> ⏰</p>
    <div style="background:#fff9f0;border-left:4px solid #fdcb6e;border-radius:0 8px 8px 0;padding:14px 18px;margin:18px 0;">
      <p>📅 <strong>{ev_date}</strong> at <strong>{ev_time}</strong></p>
      <p>📍 <strong>{venue}</strong></p>
      <p>📋 Reg ID: <span style="font-family:monospace;color:#6c5ce7;">{rid}</span></p>
    </div>
    <p>💡 On the event day, log in to mark attendance and complete tasks to earn your certificate!</p>
    <p style="color:#00b894;font-weight:600;">See you there! — EventHub Team</p>"""
    send_email(email, f"Reminder: {ev_name} is Tomorrow!",
               html_email("⏰ Event Tomorrow!", "linear-gradient(135deg,#fdcb6e,#e17055)", body))

def mail_certificate(name, email, ev_name, cert_id, pdf_bytes):
    """Feature 5: Send certificate PDF as email attachment"""
    body = f"""<p>Congratulations <strong>{name}</strong>! 🎉</p>
    <p>You have completed <strong style="color:#6c5ce7">{ev_name}</strong>!</p>
    <div style="background:#f8f7ff;border-radius:12px;padding:22px;text-align:center;margin:18px 0;">
      <div style="font-size:44px;margin-bottom:6px;">🏆</div>
      <p style="color:#888;font-size:12px;margin:0 0 4px;">Certificate ID</p>
      <p style="font-family:monospace;color:#6c5ce7;font-size:18px;font-weight:700;margin:0;">{cert_id}</p>
    </div>
    <p>Your Certificate of Participation PDF is <strong>attached</strong> to this email.</p>
    <p>Verify online: <strong>eventhub.app/verify?cid={cert_id}</strong></p>
    <p style="color:#00b894;font-weight:600;">Well done! — EventHub Team</p>"""
    bg(send_email, email, f"Your Certificate – {ev_name}",
       html_email("🏆 Certificate of Participation!", "linear-gradient(135deg,#fdcb6e,#6c5ce7)", body),
       pdf_bytes, f"Certificate_{name.replace(' ','_')}_{cert_id}.pdf")

# ════════════════════════════════════════════════════════════════════════════
# CERTIFICATE PDF  (Feature 4 – Advanced, light theme, event-specific)
# ════════════════════════════════════════════════════════════════════════════
def make_certificate_pdf(reg_name, ev_name, ev_date, organizer, cert_id, category='General'):
    """Feature 4: Professional light-theme certificate with event-specific colors"""
    buf = io.BytesIO()
    W, H = landscape(A4)   # 841.89 x 595.27 pt
    c = pdf_canvas.Canvas(buf, pagesize=(W, H))

    theme = THEMES.get(category, THEMES['General'])
    hx = theme['hex'].lstrip('#')
    try:
        R = int(hx[0:2], 16)/255; G = int(hx[2:4], 16)/255; B = int(hx[4:6], 16)/255
    except:
        R, G, B = 0.42, 0.36, 0.91

    # ── White background ──
    c.setFillColorRGB(0.99, 0.99, 1.0)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # ── Subtle corner triangles ──
    c.setFillColorRGB(R, G, B)
    c.setFillAlpha(0.08)
    c.rect(0, H-100, 100, 100, fill=1, stroke=0)
    c.rect(W-100, 0, 100, 100, fill=1, stroke=0)
    c.setFillAlpha(1)

    # ── Outer decorative border ──
    c.setStrokeColorRGB(R, G, B)
    c.setLineWidth(3)
    c.rect(18, 18, W-36, H-36, fill=0, stroke=1)
    c.setLineWidth(1)
    c.setStrokeColorRGB(R*0.7, G*0.7, B*0.7)
    c.rect(26, 26, W-52, H-52, fill=0, stroke=1)

    # ── Top colored header band ──
    c.setFillColorRGB(R, G, B)
    c.setFillAlpha(0.9)
    c.rect(18, H-105, W-36, 87, fill=1, stroke=0)
    c.setFillAlpha(1)

    # ── EventHub branding in header (left) ──
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(44, H-52, "⚡  EVENTHUB")
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.9, 0.9, 1.0)
    c.drawString(44, H-68, "Event Management System")

    # ── "Certificate of Participation" in header (center) ──
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(W/2, H-54, "CERTIFICATE OF PARTICIPATION")
    c.setFont("Helvetica", 11)
    c.setFillColorRGB(0.92, 0.92, 1.0)
    c.drawCentredString(W/2, H-74, "This document certifies successful event participation")

    # ── Category tag (top right) ──
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(W-44, H-52, f"{theme['icon']}  {category}")
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.9, 0.9, 1.0)
    c.drawRightString(W-44, H-68, "Category")

    # ── Divider line below header ──
    c.setStrokeColorRGB(R, G, B)
    c.setLineWidth(1.5)
    c.line(44, H-118, W-44, H-118)

    # ── "This is to certify that" ──
    c.setFillColorRGB(0.4, 0.4, 0.5)
    c.setFont("Helvetica-Oblique", 14)
    c.drawCentredString(W/2, H-155, "This is to proudly certify that")

    # ── Participant Name ──
    c.setFillColorRGB(R, G, B)
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(W/2, H-205, reg_name)

    # ── Underline below name ──
    name_w = c.stringWidth(reg_name, "Helvetica-Bold", 38)
    c.setStrokeColorRGB(R, G, B)
    c.setLineWidth(2)
    c.line(W/2 - name_w/2 - 10, H-213, W/2 + name_w/2 + 10, H-213)

    # ── "has successfully participated in" ──
    c.setFillColorRGB(0.45, 0.45, 0.55)
    c.setFont("Helvetica", 13)
    c.drawCentredString(W/2, H-245, "has successfully participated in and completed all requirements of")

    # ── Event Name ──
    c.setFillColorRGB(0.12, 0.08, 0.28)
    c.setFont("Helvetica-Bold", 20)
    if len(ev_name) > 52:
        words = ev_name.split(); mid = len(words)//2
        c.drawCentredString(W/2, H-274, ' '.join(words[:mid]))
        c.drawCentredString(W/2, H-298, ' '.join(words[mid:]))
        date_y = H-328
    else:
        c.drawCentredString(W/2, H-278, ev_name)
        date_y = H-312

    # ── Event date ──
    c.setFillColorRGB(0.5, 0.5, 0.6)
    c.setFont("Helvetica", 12)
    try:
        dt = datetime.strptime(ev_date, '%Y-%m-%d')
        dstr = dt.strftime('%B %d, %Y')
    except:
        dstr = ev_date
    c.drawCentredString(W/2, date_y, f"held on  {dstr}")

    # ── Bottom three info boxes ──
    BY = 58; BH = 62; BW = 190; GAP = (W - 2*44 - 3*BW) / 2

    for i, (title, val, sub) in enumerate([
        ("Organizer", organizer[:22] if len(organizer)>22 else organizer, "Official Signatory"),
        ("Certificate ID", cert_id, "Verify at eventhub.app/verify"),
        ("Issued On", date.today().strftime('%B %d, %Y'), "EventHub Verified"),
    ]):
        bx = 44 + i * (BW + GAP)
        c.setFillColorRGB(R, G, B)
        c.setFillAlpha(0.07)
        c.roundRect(bx, BY, BW, BH, 8, fill=1, stroke=0)
        c.setFillAlpha(1)
        c.setFillColorRGB(R, G, B)
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(bx + BW/2, BY + 40, val)
        c.setFillColorRGB(0.5, 0.5, 0.6)
        c.setFont("Helvetica", 9)
        c.drawCentredString(bx + BW/2, BY + 24, title)
        c.setFont("Helvetica", 8)
        c.drawCentredString(bx + BW/2, BY + 10, sub)

    # ── Bottom border line ──
    c.setStrokeColorRGB(R, G, B)
    c.setLineWidth(1)
    c.line(44, BY-8, W-44, BY-8)

    c.save(); buf.seek(0); return buf.read()

def auto_issue_certificate(reg_id, event_id):
    """Auto-generate, store, and email certificate"""
    try:
        con = get_db()
        existing = con.execute("SELECT cert_id FROM certificates WHERE reg_id=?", (reg_id,)).fetchone()
        if existing: con.close(); return existing['cert_id']

        reg = con.execute("SELECT * FROM registrations WHERE reg_id=?", (reg_id,)).fetchone()
        ev  = con.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if not reg or not ev: con.close(); return None

        cert_id = f"CERT-{uuid.uuid4().hex[:10].upper()}"
        con.execute("INSERT INTO certificates(event_id,reg_id,cert_id) VALUES(?,?,?)", (event_id, reg_id, cert_id))
        con.commit(); con.close()

        pdf = make_certificate_pdf(reg['full_name'], ev['name'], ev['date'], ev['organizer'], cert_id, ev['category'])
        mail_certificate(reg['full_name'], reg['email'], ev['name'], cert_id, pdf)
        return cert_id
    except Exception as e:
        print(f"[CERT ERROR] {e}"); return None

# ════════════════════════════════════════════════════════════════════════════
# BACKGROUND SCHEDULER
# ════════════════════════════════════════════════════════════════════════════
def scheduler():
    while True:
        try:
            con = get_db(); tmr = (date.today() + timedelta(days=1)).isoformat()
            # Event reminders
            for r in con.execute("SELECT r.*,e.name,e.date,e.time,e.venue FROM registrations r JOIN events e ON r.event_id=e.id WHERE e.date=? AND r.reminded=0 AND (r.reg_type='free' OR r.pay_status='completed')", (tmr,)).fetchall():
                mail_reminder(r['full_name'],r['email'],r['name'],r['reg_id'],r['date'],r['time'],r['venue'])
                con.execute("UPDATE registrations SET reminded=1 WHERE id=?", (r['id'],))
            # Payment reminders
            for r in con.execute("SELECT r.*,e.name FROM registrations r JOIN events e ON r.event_id=e.id WHERE r.reg_type='paid' AND r.pay_status='pending' AND r.pay_reminded=0 AND datetime(r.reg_at,'+2 hours')<datetime('now')").fetchall():
                body = f"<p>Hi {r['full_name']}, your payment for <strong>{r['name']}</strong> is still pending.<br>Reg ID: <strong>{r['reg_id']}</strong></p><p style='color:#e17055'>Please complete payment to secure your seat.</p>"
                bg(send_email, r['email'], f"Payment Pending – {r['name']}", html_email("⚠️ Payment Reminder", "#e17055", body))
                con.execute("UPDATE registrations SET pay_reminded=1 WHERE id=?", (r['id'],))
            con.commit(); con.close()
        except Exception as e: print(f"[SCHEDULER] {e}")
        time.sleep(3600)

# ════════════════════════════════════════════════════════════════════════════
# PUBLIC ROUTES
# ════════════════════════════════════════════════════════════════════════════
@app.route('/')
def home():
    con = get_db()
    q = request.args.get('q',''); cat = request.args.get('cat',''); st = request.args.get('st','')
    today = date.today().isoformat()
    sql = "SELECT * FROM events WHERE date >= ?"; p = [today]
    if q: sql += " AND (name LIKE ? OR organizer LIKE ? OR venue LIKE ?)"; p += [f'%{q}%']*3
    if cat: sql += " AND category=?"; p.append(cat)
    if st: sql += " AND status=?"; p.append(st)
    sql += " ORDER BY date ASC"
    events = con.execute(sql, p).fetchall()
    cats   = con.execute("SELECT DISTINCT category FROM events WHERE date>=?", (today,)).fetchall()
    stats  = {'total': con.execute("SELECT COUNT(*) FROM events WHERE date>=?", (today,)).fetchone()[0],
              'ongoing': con.execute("SELECT COUNT(*) FROM events WHERE date>=? AND status='ongoing'", (today,)).fetchone()[0],
              'upcoming': con.execute("SELECT COUNT(*) FROM events WHERE date>=? AND status='upcoming'", (today,)).fetchone()[0]}
    con.close()
    return render_template('home.html', events=events, cats=cats, q=q, sel_cat=cat, sel_st=st, stats=stats, themes=THEMES)

@app.route('/event/<int:eid>')
def event_detail(eid):
    ev = get_event(eid)
    if not ev or not is_future_or_today(ev): flash('Event not found or has passed.','error'); return redirect(url_for('home'))
    con = get_db()
    rc = con.execute("SELECT COUNT(*) FROM registrations WHERE event_id=?", (eid,)).fetchone()[0]
    con.close()
    return render_template('event_detail.html', ev=ev, spots=ev['capacity']-rc, rc=rc, theme=get_theme(ev['category']))

@app.route('/register/<int:eid>', methods=['GET','POST'])
def register(eid):
    ev = get_event(eid)
    if not ev or not is_future_or_today(ev): flash('Registration closed.','error'); return redirect(url_for('home'))
    err = None
    if request.method == 'POST':
        name = request.form.get('full_name','').strip()
        email = request.form.get('email','').strip()
        phone = request.form.get('phone','').strip()
        col = request.form.get('college','').strip()
        dept = request.form.get('dept','').strip()
        yr = request.form.get('year','').strip()
        if not all([name,email,phone]): err = "Please fill all required fields."
        elif not valid_gmail(email): err = "Please enter a valid Gmail address (@gmail.com only)."
        elif not valid_phone(phone): err = "Enter a valid 10-digit phone number."
        else:
            rid = new_rid(); rtype = 'paid' if ev['is_paid'] else 'free'
            pay_status = 'pending' if ev['is_paid'] else 'na'
            con = get_db()
            try:
                con.execute("INSERT INTO registrations(event_id,reg_id,full_name,email,phone,college,dept,year,reg_type,pay_status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (eid,rid,name,email,phone,col,dept,yr,rtype,pay_status))
                con.commit(); con.close()
                if ev['is_paid']:
                    mail_registration(name,email,ev['name'],rid,ev['date'],ev['time'],ev['venue'],True)
                    return redirect(url_for('payment', rid=rid))
                else:
                    mail_registration(name,email,ev['name'],rid,ev['date'],ev['time'],ev['venue'])
                    return redirect(url_for('success', rid=rid))
            except sqlite3.IntegrityError: con.close(); err = "Registration failed. Please try again."
    return render_template('register.html', ev=ev, err=err, theme=get_theme(ev['category']))

@app.route('/payment/<rid>', methods=['GET','POST'])
def payment(rid):
    con = get_db()
    r = con.execute("SELECT rg.*,e.name ev_name,e.fee,e.upi,e.date,e.time,e.venue,e.category FROM registrations rg JOIN events e ON rg.event_id=e.id WHERE rg.reg_id=?", (rid,)).fetchone()
    con.close()
    if not r: return redirect(url_for('home'))
    qr = make_qr(f"upi://pay?pa={r['upi']}&pn=EventHub&am={r['fee']}&tn={r['ev_name']}-{rid}")
    if request.method == 'POST':
        txn = request.form.get('txn','').strip()
        if txn:
            con = get_db()
            con.execute("UPDATE registrations SET pay_status='completed',txn_id=?,amount=? WHERE reg_id=?", (txn,r['fee'],rid))
            con.commit(); con.close()
            mail_payment(r['full_name'],r['email'],r['ev_name'],rid,r['fee'],txn,r['date'],r['venue'])
            return redirect(url_for('success', rid=rid))
    return render_template('payment.html', r=r, qr=qr, theme=get_theme(r['category']))

@app.route('/success/<rid>')
def success(rid):
    reg = get_reg(rid)
    if not reg: return redirect(url_for('home'))
    ev = get_event(reg['event_id'])
    return render_template('success.html', reg=reg, ev=ev, theme=get_theme(ev['category']))

@app.route('/attendance', methods=['GET','POST'])
def attendance():
    """Feature 1: form visible only on event day | Feature 2: enhanced form"""
    err = ok = cert_id = ev_info = reg_data = None
    show_form = False; looked_up = False
    rid = (request.args.get('rid') or request.form.get('rid_lookup','')).strip().upper()

    if rid and request.method == 'GET' or (rid and 'rid_lookup' in request.form):
        looked_up = True
        con = get_db()
        reg = con.execute("SELECT r.*,e.name ev_name,e.date ev_date,e.time ev_time,e.venue ev_venue FROM registrations r JOIN events e ON r.event_id=e.id WHERE r.reg_id=? AND (r.reg_type='free' OR r.pay_status='completed')", (rid,)).fetchone()
        con.close()
        if not reg:
            err = "Registration ID not found or payment not completed."
        else:
            reg_data = dict(reg)
            ev_info  = {'name': reg['ev_name'], 'date': reg['ev_date'], 'time': reg['ev_time'], 'venue': reg['ev_venue']}
            # Feature 1: Check event date
            try:
                ev_date = datetime.strptime(reg['ev_date'], '%Y-%m-%d').date()
                today   = date.today()
                if ev_date == today:
                    already = get_db().execute("SELECT id FROM attendance WHERE reg_id=?", (rid,)).fetchone()
                    get_db().close()
                    if already: ok = "✅ You have already submitted attendance for this event!"
                    else: show_form = True
                elif ev_date > today:
                    days = (ev_date - today).days
                    err = f"LOCKED|{reg['ev_date']}|{days}"
                else:
                    err = "This event has already passed."
            except: err = "Invalid event date."

    if request.method == 'POST' and 'submit_att' in request.form:
        rid     = request.form.get('reg_id','').strip().upper()
        name    = request.form.get('full_name','').strip()
        email   = request.form.get('email','').strip()
        phone   = request.form.get('phone','').strip()
        fb      = request.form.get('feedback','').strip()
        task_ok = request.form.get('task_done') == '1'
        task_ds = request.form.get('task_desc','').strip()
        if not all([rid,name,email,phone]):
            err = "Please fill all required fields."
        elif not valid_gmail(email):
            err = "Enter a valid Gmail address."
        elif not valid_phone(phone):
            err = "Enter a valid 10-digit phone number."
        else:
            con = get_db()
            reg = con.execute("SELECT r.*,e.date ev_date FROM registrations r JOIN events e ON r.event_id=e.id WHERE r.reg_id=? AND (r.reg_type='free' OR r.pay_status='completed')", (rid,)).fetchone()
            if not reg: con.close(); err = "Registration not found."
            else:
                ev_d = datetime.strptime(reg['ev_date'], '%Y-%m-%d').date()
                if ev_d != date.today():
                    con.close(); err = "Attendance can only be submitted on the event day."
                else:
                    already = con.execute("SELECT id FROM attendance WHERE reg_id=?", (rid,)).fetchone()
                    if already: con.close(); ok = "You have already submitted attendance!"
                    else:
                        eligible = 1 if task_ok else 0
                        con.execute("""INSERT INTO attendance(event_id,reg_id,full_name,email,phone,feedback,task_completed,task_description,eligible)
                            VALUES(?,?,?,?,?,?,?,?,?)""", (reg['event_id'],rid,name,email,phone,fb,int(task_ok),task_ds,eligible))
                        con.commit(); eid = reg['event_id']; con.close()
                        if eligible:
                            cert_id = auto_issue_certificate(rid, eid)
                            ok = "✅ Attendance submitted! Certificate generated and emailed to you! 🏆"
                        else:
                            ok = "📋 Attendance submitted. Check the task box and re-submit to earn your certificate."

    return render_template('attendance.html', err=err, ok=ok, cert_id=cert_id,
                           show_form=show_form, looked_up=looked_up, rid=rid,
                           ev_info=ev_info, reg_data=reg_data)

@app.route('/certificate/<rid>')
def certificate(rid):
    con = get_db()
    att = con.execute("SELECT * FROM attendance WHERE reg_id=? AND eligible=1", (rid,)).fetchone()
    if not att:
        con.close()
        flash("You are not eligible for certificate yet. Mark attendance and complete the task.", "error")
        return redirect(url_for('attendance'))

    reg = con.execute("SELECT * FROM registrations WHERE reg_id=?", (rid,)).fetchone()
    ev  = con.execute("SELECT * FROM events WHERE id=?", (att['event_id'],)).fetchone()
    cert = con.execute("SELECT * FROM certificates WHERE reg_id=?", (rid,)).fetchone()
    con.close()

    cid = cert['cert_id'] if cert else auto_issue_certificate(rid, att['event_id'])

    if not cid:
        flash("Error generating certificate.", "error")
        return redirect(url_for('home'))

    # Generate PDF
    pdf_bytes = make_certificate_pdf(
        reg['full_name'], 
        ev['name'], 
        ev['date'], 
        ev['organizer'], 
        cid, 
        ev['category']
    )

    return render_template('cert.html', 
                           reg=reg, 
                           ev=ev, 
                           cid=cid,
                           pdf_b64=base64.b64encode(pdf_bytes).decode(),
                           theme=get_theme(ev['category']),
                           allow_download=True)   # New flag

@app.route('/download-certificate/<rid>')
def download_certificate(rid):
    """Allow users to download certificate as PDF"""
    con = get_db()
    att = con.execute("SELECT * FROM attendance WHERE reg_id=? AND eligible=1", (rid,)).fetchone()
    if not att:
        con.close()
        flash("Certificate not available.", "error")
        return redirect(url_for('home'))

    reg = con.execute("SELECT * FROM registrations WHERE reg_id=?", (rid,)).fetchone()
    ev  = con.execute("SELECT * FROM events WHERE id=?", (att['event_id'],)).fetchone()
    cert = con.execute("SELECT * FROM certificates WHERE reg_id=?", (rid,)).fetchone()
    con.close()

    cid = cert['cert_id'] if cert else auto_issue_certificate(rid, att['event_id'])

    pdf_bytes = make_certificate_pdf(
        reg['full_name'], ev['name'], ev['date'], 
        ev['organizer'], cid, ev['category']
    )

    # Send as downloadable file
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"Certificate_{reg['full_name'].replace(' ', '_')}_{cid}.pdf"
    )

@app.route('/verify')
def verify():
    cid = request.args.get('cid','').strip(); res = None
    if cid:
        con = get_db()
        cert = con.execute("""SELECT c.*,e.name ev_name,e.date,e.venue,e.organizer,e.category,r.full_name holder
            FROM certificates c JOIN events e ON c.event_id=e.id JOIN registrations r ON c.reg_id=r.reg_id
            WHERE c.cert_id=?""", (cid,)).fetchone()
        con.close(); res = dict(cert) if cert else 'nf'
    return render_template('verify.html', res=res, cid=cid)

@app.route('/my-tickets', methods=['GET','POST'])
def my_tickets():
    results = None; email = ''; err = None
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        if not valid_gmail(email): err = "Enter a valid Gmail address."
        else:
            con = get_db()
            regs = [dict(r) for r in con.execute("SELECT r.*,e.name ev_name,e.date,e.venue,e.status,e.category FROM registrations r JOIN events e ON r.event_id=e.id WHERE r.email=? ORDER BY r.reg_at DESC", (email,)).fetchall()]
            for r in regs:
                a = con.execute("SELECT * FROM attendance WHERE reg_id=?", (r['reg_id'],)).fetchone()
                c = con.execute("SELECT * FROM certificates WHERE reg_id=?", (r['reg_id'],)).fetchone()
                r['att'] = dict(a) if a else None; r['cert'] = dict(c) if c else None
                r['theme'] = get_theme(r['category'])
            con.close(); results = regs
    return render_template('my_tickets.html', results=results, email=email, err=err)

@app.route('/feedback/<rid>', methods=['GET','POST'])
def feedback(rid):
    reg = get_reg(rid)
    if not reg: return redirect(url_for('home'))
    con = get_db()
    ev  = con.execute("SELECT * FROM events WHERE id=?", (reg['event_id'],)).fetchone()
    ex  = con.execute("SELECT * FROM feedback WHERE reg_id=?", (rid,)).fetchone()
    con.close()
    if request.method == 'POST' and not ex:
        rating = int(request.form.get('rating',5)); comment = request.form.get('comment','').strip()
        con = get_db()
        con.execute("INSERT INTO feedback(event_id,reg_id,rating,comment) VALUES(?,?,?,?)", (reg['event_id'],rid,rating,comment))
        con.commit(); con.close(); flash('Thanks for your feedback! 🙏','success')
        return redirect(url_for('home'))
    return render_template('feedback.html', reg=reg, ev=ev, ex=ex)

# ════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTES  (Feature 8)
# ════════════════════════════════════════════════════════════════════════════
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    err = None
    if request.method == 'POST':
        if request.form.get('u') == ADMIN_USERNAME and request.form.get('p') == ADMIN_PASSWORD:
            session['admin'] = True; flash('Welcome, Admin!','success')
            return redirect(url_for('admin_dash'))
        err = "Invalid username or password."
    return render_template('admin_login.html', err=err)

@app.route('/admin/logout')
def admin_logout(): session.clear(); return redirect(url_for('admin_login'))

@app.route('/admin')
@admin_only
def admin_dash():
    con = get_db()
    evs  = con.execute("SELECT * FROM events ORDER BY date DESC").fetchall()
    st   = {
        'regs':    con.execute("SELECT COUNT(*) FROM registrations").fetchone()[0],
        'paid':    con.execute("SELECT COUNT(*) FROM registrations WHERE pay_status='completed'").fetchone()[0],
        'revenue': con.execute("SELECT COALESCE(SUM(amount),0) FROM registrations WHERE pay_status='completed'").fetchone()[0],
        'certs':   con.execute("SELECT COUNT(*) FROM certificates").fetchone()[0],
        'att':     con.execute("SELECT COUNT(*) FROM attendance").fetchone()[0],
    }
    con.close()
    return render_template('admin_dash.html', evs=evs, st=st, themes=THEMES)

def parse_form(f):
    name=f.get('name','').strip(); desc=f.get('desc','').strip()
    ds=f.get('date','').strip(); ts=f.get('time','').strip()
    venue=f.get('venue','').strip(); host=f.get('host','').strip()
    co=f.get('co_host','').strip() or None; org=f.get('organizer','').strip()
    cat=f.get('category','General'); paid=1 if f.get('is_paid')=='1' else 0
    fee=float(f.get('fee',0) or 0); cap=int(f.get('capacity',200) or 200)
    upi=f.get('upi','').strip(); stat=f.get('status','upcoming')
    if not all([name,ds,ts,venue,host,org]): return None,"Fill all required fields."
    if not valid_future(ds): return None,"Event date must be today or future."
    return (name,desc,ds,ts,venue,host,co,org,cat,paid,fee,cap,upi,stat), None

@app.route('/admin/new', methods=['GET','POST'])
@admin_only
def admin_new():
    err = None; today = date.today().isoformat()
    if request.method == 'POST':
        row,err = parse_form(request.form)
        if not err:
            con = get_db()
            con.execute("INSERT INTO events(name,description,date,time,venue,host,co_host,organizer,category,is_paid,fee,capacity,upi,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
            con.commit(); con.close(); flash(f'Event "{row[0]}" created!','success')
            return redirect(url_for('admin_dash'))
    return render_template('admin_form.html', ev=None, err=err, mode='new', today=today, cats=list(THEMES.keys()))

@app.route('/admin/edit/<int:eid>', methods=['GET','POST'])
@admin_only
def admin_edit(eid):
    ev = get_event(eid)
    if not ev: return redirect(url_for('admin_dash'))
    err = None; today = date.today().isoformat()
    if request.method == 'POST':
        row,err = parse_form(request.form)
        if not err:
            con = get_db()
            con.execute("UPDATE events SET name=?,description=?,date=?,time=?,venue=?,host=?,co_host=?,organizer=?,category=?,is_paid=?,fee=?,capacity=?,upi=?,status=? WHERE id=?", row+(eid,))
            con.commit(); con.close(); flash('Event updated!','success')
            return redirect(url_for('admin_dash'))
    return render_template('admin_form.html', ev=dict(ev), err=err, mode='edit', today=today, cats=list(THEMES.keys()))

@app.route('/admin/delete/<int:eid>', methods=['POST'])
@admin_only
def admin_delete(eid):
    con = get_db(); ev = con.execute("SELECT name FROM events WHERE id=?", (eid,)).fetchone()
    if ev: con.execute("DELETE FROM events WHERE id=?", (eid,)); con.commit(); flash(f'Deleted "{ev["name"]}"','success')
    con.close(); return redirect(url_for('admin_dash'))

@app.route('/admin/event/<int:eid>')
@admin_only
def admin_event(eid):
    con = get_db()
    ev   = con.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()
    regs = con.execute("SELECT * FROM registrations WHERE event_id=? ORDER BY reg_at DESC", (eid,)).fetchall()
    att  = con.execute("SELECT * FROM attendance WHERE event_id=? ORDER BY att_time DESC", (eid,)).fetchall()
    con.close()
    return render_template('admin_event.html', ev=ev, regs=regs, att=att, theme=get_theme(ev['category']))

@app.route('/admin/analytics')
@admin_only
def admin_analytics():
    con = get_db()
    reg_d  = [dict(r) for r in con.execute("SELECT e.name,e.category,COUNT(r.id) total,(SELECT COUNT(*) FROM registrations r2 WHERE r2.event_id=e.id AND r2.pay_status='completed') paid FROM events e LEFT JOIN registrations r ON r.event_id=e.id GROUP BY e.id ORDER BY total DESC").fetchall()]
    rev_d  = [dict(r) for r in con.execute("SELECT e.name,COALESCE(SUM(r.amount),0) rev FROM events e LEFT JOIN registrations r ON r.event_id=e.id AND r.pay_status='completed' GROUP BY e.id HAVING rev>0 ORDER BY rev DESC").fetchall()]
    cat_d  = [dict(r) for r in con.execute("SELECT category,COUNT(*) cnt FROM events GROUP BY category").fetchall()]
    day_d  = [dict(r) for r in con.execute("SELECT date(reg_at) day,COUNT(*) cnt FROM registrations GROUP BY day ORDER BY day DESC LIMIT 14").fetchall()]
    att_d  = [dict(r) for r in con.execute("SELECT e.name,COUNT(a.id) att,SUM(a.eligible) eli,(SELECT COUNT(*) FROM certificates c WHERE c.event_id=e.id) certs FROM events e LEFT JOIN attendance a ON a.event_id=e.id GROUP BY e.id").fetchall()]
    tot_rev = con.execute("SELECT COALESCE(SUM(amount),0) FROM registrations WHERE pay_status='completed'").fetchone()[0]
    tot_reg = con.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
    con.close()
    return render_template('analytics.html', reg_d=reg_d, rev_d=rev_d, cat_d=cat_d,
        day_d=day_d, att_d=att_d, tot_rev=tot_rev, tot_reg=tot_reg)

if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
    threading.Thread(target=scheduler, daemon=True).start()
    print("\n🚀 EventHub is running!")
    print("   → http://localhost:5000")
    print("   → Admin: http://localhost:5000/admin/login")
    print("   → Credentials: admin / Admin@2025")
    print("   → Email: set SMTP_USER and SMTP_PASS env vars\n")
    app.run(debug=True, port=5000)
