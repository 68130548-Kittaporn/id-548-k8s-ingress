"""app-research: seminar research summary, with an edit page.

Routes
  GET  /research   read-only summary (public, via www.id-xxx.com/research)
  GET  /edit       edit form          (admin.id-xxx.com is rewritten to /edit by the Ingress)
  POST /edit       save the summary back to the PersistentVolume
  GET  /healthz    probe endpoint

The summary lives in DATA_FILE (JSON: {"title": ..., "body": ...}) on a PVC,
so edits survive pod restarts. An initContainer seeds it from a ConfigMap
the first time.
"""
import html
import json
import os
import time
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8080"))
DATA_FILE = os.environ.get("DATA_FILE", "/data/summary.json")
MAX_BODY = 200_000
WWW_URL = os.environ.get("WWW_URL", "http://www.id-xxx.com").rstrip("/")
ADMIN_URL = os.environ.get("ADMIN_URL", "http://admin.id-xxx.com").rstrip("/")

NAV_CSS = """
.nav{position:fixed;top:0;left:0;right:0;display:flex;gap:6px;justify-content:center;
flex-wrap:wrap;padding:10px 12px;background:rgba(15,23,42,.88);backdrop-filter:blur(6px);
z-index:10;font-family:'Segoe UI',Tahoma,sans-serif}
.nav a{color:#e2e8f0;text-decoration:none;padding:6px 16px;border-radius:999px;font-size:.95rem}
.nav a:hover{background:rgba(56,189,248,.25)}.nav a.on{background:#38bdf8;color:#0f172a;font-weight:600}
"""


def nav(active):
    # Absolute URLs: the edit page is served on admin.*, where any relative
    # link would be rewritten to /edit again by the admin Ingress.
    items = [("about", WWW_URL + "/about", "About"),
             ("research", WWW_URL + "/research", "Research"),
             ("api", WWW_URL + "/api/Hello%20I%27m%20June", "API"), ("admin", ADMIN_URL + "/", "Admin &#9998;")]
    return '<nav class="nav">' + "".join(
        f'<a href="{html.escape(h)}" class="{"on" if k == active else ""}">{t}</a>' for k, h, t in items) + "</nav>"

STYLE = """
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',Tahoma,sans-serif;
background:#f1f5f9;color:#1e293b;padding:64px 16px 16px}
.wrap{max-width:860px;margin:24px auto;background:#fff;border-radius:14px;
box-shadow:0 10px 30px rgba(0,0,0,.08);padding:36px}
h1{margin-top:0;color:#0f766e;line-height:1.35}
p{line-height:1.9;font-size:1.05rem;text-align:justify}
.meta{color:#64748b;font-size:.85rem;border-top:1px solid #e2e8f0;padding-top:12px;margin-top:28px}
label{font-weight:600;display:block;margin:14px 0 6px}
input,textarea{width:100%;font:inherit;padding:10px;border:1px solid #cbd5e1;border-radius:8px}
textarea{min-height:420px;line-height:1.7}
button{margin-top:16px;background:#0f766e;color:#fff;border:0;padding:12px 28px;
border-radius:8px;font-size:1rem;cursor:pointer}
.ok{background:#dcfce7;color:#166534;padding:10px 14px;border-radius:8px}
.badge{display:inline-block;background:#fef3c7;color:#92400e;padding:2px 10px;border-radius:999px;font-size:.8rem}
"""


def load():
    try:
        with open(DATA_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"title": "Research summary", "body": "(empty)", "updated": None}


def save(title, body):
    data = {"title": title, "body": body, "updated": time.strftime("%Y-%m-%d %H:%M:%S %Z")}
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)  # atomic swap, no half-written file
    return data


def paragraphs(text):
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return "".join(f"<p>{html.escape(b).replace(chr(10), '<br>')}</p>" for b in blocks)


def page(title, inner, active=""):
    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{STYLE}{NAV_CSS}</style></head>
<body>{nav(active)}<div class="wrap">{inner}
</div></body></html>"""


def edit_form(d, saved=False):
    note = '<p class="ok">&#10004; Saved</p>' if saved else ""
    # action="" posts back to the URL the browser is on (admin.id-xxx.com/),
    # which the Ingress rewrites to /edit again.
    return page("Edit research summary", f"""
<span class="badge">ADMIN</span><h1>Edit research summary</h1>{note}
<form method="post" action="">
<label for="title">Title</label>
<input id="title" name="title" value="{html.escape(d.get('title', ''))}">
<label for="body">Summary (300-500 words; blank line = new paragraph)</label>
<textarea id="body" name="body">{html.escape(d.get('body', ''))}</textarea>
<button type="submit">Save</button></form>
<p class="meta">Last updated: {html.escape(str(d.get('updated') or '-'))}</p>""", "admin")


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def route(self):
        return self.path.split("?", 1)[0].rstrip("/") or "/"

    def do_GET(self):
        p = self.route()
        if p == "/healthz":
            return self.send(200, "ok", "text/plain")
        if p == "/research":
            d = load()
            return self.send(200, page(d["title"], f"<h1>{html.escape(d['title'])}</h1>"
                                       f"{paragraphs(d['body'])}"
                                       f"<p class='meta'>Last updated: {html.escape(str(d.get('updated') or '-'))}</p>",
                                       "research"))
        if p == "/edit":
            return self.send(200, edit_form(load()))
        return self.send(404, page("404", "<h1>404</h1>"))

    def do_POST(self):
        if self.route() != "/edit":
            return self.send(404, "not found", "text/plain")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self.send(413, "too large", "text/plain")
        form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        title = form.get("title", [""])[0].strip() or "Research summary"
        body = form.get("body", [""])[0].strip()
        return self.send(200, edit_form(save(title, body), saved=True))

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    print(f"app-research listening on :{PORT}, data={DATA_FILE}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
