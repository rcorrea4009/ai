"""Shared UI theme — call ui.inject() at the top of any page for a modern look."""
import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root{
  --bg:#0a0d13; --card:#141a24; --card2:#1a2130; --border:#242e40;
  --text:#e7edf5; --muted:#8a96a8; --accent:#5c9eff; --accent2:#8b5cf6;
  --green:#26d0a5; --red:#ff5c72; --amber:#ffb02e;
}
html, body, .stApp, section.main, [class*="css"]{
  font-family:'Inter',system-ui,-apple-system,sans-serif !important;
}
.stApp{
  background:
    radial-gradient(1100px 520px at 15% -10%, rgba(92,158,255,.10), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(139,92,246,.10), transparent 55%),
    #0a0d13 !important;
}
h1,h2,h3{ letter-spacing:-.02em; font-weight:800; }
section.main > div{ font-size:16px; }

/* Hero banner */
.hero{
  position:relative; border:1px solid var(--border); border-radius:20px;
  padding:26px 30px; margin:2px 0 20px;
  background:linear-gradient(135deg, rgba(92,158,255,.16), rgba(139,92,246,.12));
  box-shadow:0 12px 40px rgba(0,0,0,.40);
  overflow:hidden;
}
.hero:after{
  content:""; position:absolute; right:-60px; top:-60px; width:220px; height:220px;
  background:radial-gradient(circle, rgba(139,92,246,.35), transparent 70%); filter:blur(10px);
}
.hero h1{
  font-size:33px; margin:0; font-weight:900;
  background:linear-gradient(90deg,#ffffff,#a9c7ff 70%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.hero p{ color:var(--muted); margin:8px 0 0; font-size:15px; max-width:760px; }
.hero .pills{ margin-top:14px; }
.hero .pill{
  display:inline-block; margin-right:8px; padding:5px 12px; border-radius:999px;
  font-size:12px; font-weight:700; background:rgba(38,208,165,.14); color:var(--green);
  border:1px solid rgba(38,208,165,.25);
}

/* Buttons */
.stButton > button{
  border-radius:12px !important; border:1px solid var(--border) !important;
  font-weight:600 !important; transition:transform .12s ease, border-color .12s ease !important;
}
.stButton > button:hover{ transform:translateY(-1px); border-color:var(--accent) !important; }
.stButton > button[kind="primary"]{
  background:linear-gradient(135deg,var(--accent),var(--accent2)) !important;
  border:none !important; box-shadow:0 6px 20px rgba(92,158,255,.30) !important;
}

/* Metrics as cards */
[data-testid="stMetric"]{
  background:var(--card); border:1px solid var(--border); border-radius:14px;
  padding:14px 16px; box-shadow:0 4px 16px rgba(0,0,0,.25);
}
[data-testid="stMetricValue"]{ font-weight:800; }

/* Tables + inputs */
[data-testid="stDataFrame"]{ border-radius:12px; overflow:hidden; border:1px solid var(--border); }
[data-baseweb="input"], [data-baseweb="select"]{ border-radius:10px !important; }

/* Nav page-links */
[data-testid="stPageLink"] a{
  border:1px solid var(--border); border-radius:12px; padding:11px 14px;
  transition:all .14s ease; font-weight:600;
}
[data-testid="stPageLink"] a:hover{ border-color:var(--accent); background:rgba(92,158,255,.08); transform:translateY(-1px); }

/* Dividers a touch softer */
hr{ border-color:var(--border) !important; opacity:.6; }
</style>
"""


def inject():
    st.markdown(_CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str = "", pills: list[str] | None = None):
    pill_html = ""
    if pills:
        pill_html = '<div class="pills">' + "".join(f'<span class="pill">{p}</span>' for p in pills) + "</div>"
    st.markdown(
        f'<div class="hero"><h1>{title}</h1>'
        f'{f"<p>{subtitle}</p>" if subtitle else ""}{pill_html}</div>',
        unsafe_allow_html=True,
    )
