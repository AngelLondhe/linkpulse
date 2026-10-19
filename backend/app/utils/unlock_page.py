"""Minimal server-rendered page asking for a protected link's password.

Self-contained (inline CSS, no JS) so it works without the frontend. All dynamic values are
HTML-escaped, and the response carries a strict CSP.
"""

from html import escape

# No `form-action`: browsers apply it to the redirect that follows a form POST too, so
# `form-action 'self'` would block the 303 to the (external) destination after unlocking.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "private, no-store",
}

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Protected link</title>
<style>
  :root {{ color-scheme: light dark; --bg:#f9f9f7; --card:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e;
          --line:rgba(11,11,11,.1); --accent:#2a78d6; --danger:#d03b3b; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#0d0d0d; --card:#1a1a19; --ink:#f0efec;
          --ink2:#c3c2b7; --line:rgba(255,255,255,.1); --accent:#3987e5; --danger:#e66767; }} }}
  body {{ margin:0; min-height:100vh; display:grid; place-items:center; background:var(--bg);
         color:var(--ink); font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  main {{ width:min(92vw,22rem); background:var(--card); border:1px solid var(--line);
         border-radius:12px; padding:24px; }}
  h1 {{ font-size:1.15rem; margin:0 0 4px; }}
  p {{ margin:0 0 16px; color:var(--ink2); font-size:.9rem; }}
  input {{ width:100%; box-sizing:border-box; padding:10px 12px; border-radius:8px;
          border:1px solid var(--line); background:var(--bg); color:var(--ink); font-size:1rem; }}
  button {{ margin-top:12px; width:100%; padding:10px; border:0; border-radius:8px;
           background:var(--accent); color:#fff; font-weight:600; font-size:.95rem;
           cursor:pointer; }}
  .error {{ color:var(--danger); margin:8px 0 0; font-size:.85rem; }}
</style>
</head>
<body>
<main>
  <h1>This link is password protected</h1>
  <p>Enter the password to continue to <strong>/{code}</strong>.</p>
  <form method="post" autocomplete="off">
    <label for="password" style="position:absolute;left:-9999px">Password</label>
    <input id="password" name="password" type="password" required autofocus maxlength="128"
           placeholder="Password" aria-invalid="{invalid}"{describedby}>
    {error}
    <button type="submit">Continue</button>
  </form>
</main>
</body>
</html>
"""


def render_unlock_page(code: str, error: str | None = None) -> str:
    error_html = f'<p class="error" id="error" role="alert">{escape(error)}</p>' if error else ""
    return _TEMPLATE.format(
        code=escape(code),
        error=error_html,
        invalid="true" if error else "false",
        describedby=' aria-describedby="error"' if error else "",
    )
