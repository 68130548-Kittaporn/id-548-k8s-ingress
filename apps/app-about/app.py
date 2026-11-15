"""app-about: shows the student's photo, name and ID.

Routes
  /          landing page with links to every service
  /about     photo + name + student ID
  /photo     the photo file (mounted from a ConfigMap)
  /healthz   probe endpoint

Pure Python standard library, so it runs on the stock python image
with the code mounted from a ConfigMap (no image build needed).
"""
import html
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8080"))
NAME = os.environ.get("STUDENT_NAME", "Student Name")
NAME_EN = os.environ.get("STUDENT_NAME_EN", "")
SID = os.environ.get("STUDENT_ID", "00000000")
COURSE = os.environ.get("COURSE", "CT665")
DOMAIN = os.environ.get("DOMAIN", "www.id-xxx.com")
PHOTO_DIR = os.environ.get("PHOTO_DIR", "/photo")
ADMIN_URL = os.environ.get("ADMIN_URL", "http://admin.id-xxx.com").rstrip("/")

NAV_CSS = """
.nav{position:fixed;top:0;left:0;right:0;display:flex;gap:6px;justify-content:center;
flex-wrap:wrap;padding:10px 12px;background:rgba(15,23,42,.88);backdrop-filter:blur(6px);
z-index:10;font-family:'Segoe UI',Tahoma,sans-serif}
.nav a{color:#e2e8f0;text-decoration:none;padding:6px 16px;border-radius:999px;font-size:.95rem}
.nav a:hover{background:rgba(56,189,248,.25)}.nav a.on{background:#38bdf8;color:#0f172a;font-weight:600}
"""


def nav(active):
    """Menu bar linking every service (relative links stay on www.*, admin is absolute)."""
    items = [("about", "/about", "About"),
             ("research", "/research", "Research"), ("api", "/api/Hello%20I%27m%20June", "API"),
             ("admin", ADMIN_URL + "/", "Admin &#9998;")]
    return '<nav class="nav">' + "".join(
        f'<a href="{h}" class="{"on" if k == active else ""}">{t}</a>' for k, h, t in items) + "</nav>"

STYLE = """
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Tahoma,sans-serif;
background:linear-gradient(135deg,#1e3c72,#2a5298);min-height:100vh;display:flex;
align-items:center;justify-content:center;color:#1f2937;padding:76px 16px 16px}
.card{background:#fff;border-radius:18px;box-shadow:0 20px 50px rgba(0,0,0,.3);
padding:40px;max-width:520px;width:100%;text-align:center}
img{width:200px;height:200px;object-fit:cover;border-radius:50%;border:6px solid #2a5298}
h1{margin:20px 0 6px;font-size:1.8rem}h2{margin:0;color:#6b7280;font-weight:500;font-size:1.1rem}
.id{display:inline-block;margin-top:16px;background:#2a5298;color:#fff;padding:8px 22px;
border-radius:999px;font-size:1.3rem;letter-spacing:2px}
a{color:#2a5298}ul{text-align:left;line-height:2}
"""


def find_photo():
    if not os.path.isdir(PHOTO_DIR):
        return None
    for f in sorted(os.listdir(PHOTO_DIR)):
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".svg", ".webp")):
            return os.path.join(PHOTO_DIR, f)
    return None


def page(title, body, active=""):
    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{STYLE}{NAV_CSS}</style></head>
<body>{nav(active)}<div class="card">{body}
</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/healthz":
            return self.send(200, "ok", "text/plain")
        if path in ("/about/photo", "/photo"):
            p = find_photo()
            if not p:
                return self.send(404, "no photo", "text/plain")
            with open(p, "rb") as fh:
                ctype = mimetypes.guess_type(p)[0] or "application/octet-stream"
                return self.send(200, fh.read(), ctype)
        if path == "/about":
            en = f"<h2>{html.escape(NAME_EN)}</h2>" if NAME_EN else ""
            body = (f'<img src="/about/photo" alt="photo">'
                    f"<h1>{html.escape(NAME)}</h1>{en}"
                    f'<div class="id">{html.escape(SID)}</div>'
                    f"<p>{html.escape(COURSE)}</p>")
            return self.send(200, page("About - " + SID, body, "about"))
        if path == "/":
            # No separate home page: the site root goes straight to /about
            self.send_response(302)
            self.send_header("Location", "/about")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        return self.send(404, page("404", "<h1>404</h1><p>Not found</p>"))

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    print(f"app-about listening on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
