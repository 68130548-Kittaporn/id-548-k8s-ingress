"""app-api: /api/<message> shows <message> in large text, centred on screen.

Routes
  /api/<message>   big centred message (URL-decoded, HTML-escaped)
  /api             usage hint
  /healthz         probe endpoint
"""
import html
import os
from urllib.parse import unquote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8080"))
ADMIN_URL = os.environ.get("ADMIN_URL", "http://admin.id-xxx.com").rstrip("/")

NAV = ('<nav class="nav"><a href="/about">About</a>'
       '<a href="/research">Research</a><a href="/api/Hello%20I%27m%20June" class="on">API</a>'
       f'<a href="{html.escape(ADMIN_URL)}/">Admin &#9998;</a></nav>')

PAGE = """<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>
html,body{{margin:0;height:100%}}
body{{display:flex;align-items:center;justify-content:center;flex-direction:column;
background:#0f172a;color:#f8fafc;font-family:'Segoe UI',Tahoma,sans-serif;padding:70px 16px 90px;
box-sizing:border-box;text-align:center}}
h1{{margin:0;font-size:clamp(2.5rem,10vw,9rem);line-height:1.1;word-break:break-word;
background:linear-gradient(90deg,#38bdf8,#a78bfa,#f472b6);-webkit-background-clip:text;
background-clip:text;color:transparent}}
.nav{{position:fixed;top:0;left:0;right:0;display:flex;gap:6px;justify-content:center;
flex-wrap:wrap;padding:10px 12px;background:rgba(30,41,59,.9);z-index:10}}
.nav a{{color:#e2e8f0;text-decoration:none;padding:6px 16px;border-radius:999px;font-size:.95rem}}
.nav a:hover{{background:rgba(56,189,248,.25)}}.nav a.on{{background:#38bdf8;color:#0f172a;font-weight:600}}
form{{position:fixed;bottom:24px;display:flex;gap:8px;width:min(480px,calc(100% - 32px))}}
form input{{flex:1;padding:10px 14px;border-radius:999px;border:1px solid #334155;
background:#1e293b;color:#f8fafc;font:inherit}}
form button{{padding:10px 20px;border-radius:999px;border:0;background:#a78bfa;color:#0f172a;
font-weight:600;cursor:pointer}}
</style></head><body>{nav}<h1>{msg}</h1>
<form onsubmit="var v=this.m.value.trim();if(v)location.href='/api/'+encodeURIComponent(v);return false">
<input name="m" placeholder="&#3614;&#3636;&#3617;&#3614;&#3660;&#3586;&#3657;&#3629;&#3588;&#3623;&#3634;&#3617;..." autocomplete="off"><button>Show</button></form>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            return self.send(200, "ok", "text/plain")
        if path == "/api" or path.startswith("/api/"):
            raw = path[len("/api/"):] if path.startswith("/api/") else ""
            msg = unquote(raw).strip() or "Usage: /api/&lt;message&gt;"
            safe = html.escape(msg) if raw.strip() else msg
            return self.send(200, PAGE.format(title=html.escape(msg[:60]), msg=safe, nav=NAV))
        return self.send(404, "not found", "text/plain")

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


if __name__ == "__main__":
    print(f"app-api listening on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
