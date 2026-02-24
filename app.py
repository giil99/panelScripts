"""
Naturgy Data Scripts Dashboard
Main application entry point.
"""
import streamlit as st
import sys
from pathlib import Path

# Ensure dashboard directory is in path
dashboard_dir = Path(__file__).parent
if str(dashboard_dir) not in sys.path:
    sys.path.insert(0, str(dashboard_dir))

from config import APP_TITLE, APP_ICON, PAGE_LAYOUT

# Page configuration
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout=PAGE_LAYOUT,
    initial_sidebar_state="expanded"
)

# ── Premium Light Theme CSS ─────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Import Google Fonts ─────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* ── CSS Variables ───────────────────────────────── */
    :root {
        --bg-primary: #F8FAFC;
        --bg-card: #FFFFFF;
        --bg-card-hover: #F1F5F9;
        --bg-sidebar: linear-gradient(180deg, #1E3A5F 0%, #1A2E4A 100%);
        --border-card: #E2E8F0;
        --border-hover: #2563EB;
        --accent-blue: #2563EB;
        --accent-sky: #0EA5E9;
        --accent-amber: #F59E0B;
        --accent-green: #10B981;
        --accent-red: #EF4444;
        --text-primary: #1E293B;
        --text-secondary: #475569;
        --text-muted: #94A3B8;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.07);
        --shadow-lg: 0 8px 24px rgba(0,0,0,0.08);
        --radius: 12px;
    }

    /* ── Global Typography ───────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
        font-feature-settings: "cv02", "cv03", "cv04", "cv11";
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    /* ── Hide Default Streamlit Nav & Chrome ──────────── */
    [data-testid="stSidebarNav"] { display: none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: var(--bg-primary) !important; }

    /* ── Sidebar ─────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: var(--bg-sidebar) !important;
    }

    [data-testid="stSidebar"] * {
        color: #CBD5E1 !important;
    }

    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3,
    [data-testid="stSidebar"] .stMarkdown strong {
        color: #F1F5F9 !important;
        font-weight: 700 !important;
    }

    /* ── Sidebar Nav Buttons ─────────────────────────── */
    [data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        text-align: left !important;
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 10px !important;
        padding: 0.65rem 1rem !important;
        color: #CBD5E1 !important;
        font-weight: 500 !important;
        font-size: 0.88rem !important;
        transition: all 0.2s ease !important;
        margin-bottom: 3px !important;
    }

    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.12) !important;
        color: #FFFFFF !important;
        transform: translateX(3px);
    }

    [data-testid="stSidebar"] .stButton > button[kind="primary"],
    [data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"] {
        background: rgba(37,99,235,0.35) !important;
        border: 1px solid rgba(37,99,235,0.5) !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        border-left: 3px solid #60A5FA !important;
    }

    /* ── Sidebar Divider ─────────────────────────────── */
    [data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.1) !important;
    }

    /* ── Metrics ─────────────────────────────────────── */
    [data-testid="stMetric"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-card) !important;
        border-radius: var(--radius) !important;
        padding: 1rem 1.2rem !important;
        box-shadow: var(--shadow-sm) !important;
        transition: all 0.25s ease !important;
    }

    [data-testid="stMetric"]:hover {
        box-shadow: var(--shadow-md) !important;
        border-color: var(--border-hover) !important;
        transform: translateY(-2px);
    }

    [data-testid="stMetricLabel"] {
        color: var(--text-secondary) !important;
        font-weight: 600 !important;
        font-size: 0.78rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
    }

    [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-weight: 700 !important;
    }

    /* ── Primary Buttons (main content) ──────────────── */
    div[data-testid="stMainBlockContainer"] .stButton > button[kind="primary"],
    div[data-testid="stMainBlockContainer"] .stButton > button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #2563EB, #0EA5E9) !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        color: #FFFFFF !important;
        letter-spacing: 0.02em !important;
        transition: all 0.25s ease !important;
        box-shadow: 0 3px 12px rgba(37,99,235,0.25) !important;
    }

    div[data-testid="stMainBlockContainer"] .stButton > button[kind="primary"]:hover,
    div[data-testid="stMainBlockContainer"] .stButton > button[data-testid="stBaseButton-primary"]:hover {
        box-shadow: 0 5px 20px rgba(37,99,235,0.35) !important;
        transform: translateY(-1px) !important;
    }

    div[data-testid="stMainBlockContainer"] .stButton > button[kind="secondary"],
    div[data-testid="stMainBlockContainer"] .stButton > button[data-testid="stBaseButton-secondary"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-card) !important;
        border-radius: 10px !important;
        color: var(--text-primary) !important;
        font-weight: 500 !important;
        transition: all 0.25s ease !important;
    }

    div[data-testid="stMainBlockContainer"] .stButton > button[kind="secondary"]:hover,
    div[data-testid="stMainBlockContainer"] .stButton > button[data-testid="stBaseButton-secondary"]:hover {
        border-color: var(--accent-blue) !important;
        color: var(--accent-blue) !important;
        box-shadow: var(--shadow-sm) !important;
    }

    /* ── Inputs / Selects ────────────────────────────── */
    .stSelectbox > div > div,
    .stMultiSelect > div > div,
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-card) !important;
        border-radius: 10px !important;
        color: var(--text-primary) !important;
        transition: border-color 0.2s ease !important;
    }

    .stSelectbox > div > div:focus-within,
    .stMultiSelect > div > div:focus-within,
    .stTextInput > div > div > input:focus {
        border-color: var(--accent-blue) !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
    }

    /* ── Tabs ─────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px !important;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        padding: 0.5rem 1rem !important;
        background: transparent !important;
        border: none !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #2563EB, #0EA5E9) !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
    }

    /* ── Expander ─────────────────────────────────────── */
    [data-testid="stExpander"] {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-card) !important;
        border-radius: var(--radius) !important;
        box-shadow: var(--shadow-sm) !important;
    }

    /* ── Dataframe ────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--border-card) !important;
        border-radius: var(--radius) !important;
        overflow: hidden !important;
        box-shadow: var(--shadow-sm) !important;
    }

    /* ── Dividers ─────────────────────────────────────── */
    hr {
        border-color: var(--border-card) !important;
        opacity: 0.6 !important;
    }

    /* ── Alerts ───────────────────────────────────────── */
    .stAlert, [data-testid="stNotification"] {
        border-radius: var(--radius) !important;
    }

    /* ── Download Buttons ─────────────────────────────── */
    .stDownloadButton > button {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-card) !important;
        border-radius: 10px !important;
        color: var(--accent-blue) !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }

    .stDownloadButton > button:hover {
        border-color: var(--accent-blue) !important;
        box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
    }

    /* ── Progress Bar ─────────────────────────────────── */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #2563EB, #0EA5E9) !important;
        border-radius: 10px !important;
    }

    /* ── Custom Classes ───────────────────────────────── */
    .hero-title {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: var(--text-primary) !important;
        margin-bottom: 0.5rem !important;
        line-height: 1.2 !important;
        letter-spacing: -0.02em !important;
    }

    .hero-subtitle {
        color: var(--text-secondary) !important;
        font-size: 1rem !important;
        font-weight: 400 !important;
        margin-bottom: 1.5rem !important;
    }

    .info-card {
        background: var(--bg-card);
        border: 1px solid var(--border-card);
        border-radius: var(--radius);
        padding: 1.25rem 1.5rem;
        box-shadow: var(--shadow-sm);
        transition: all 0.25s ease;
    }

    .info-card:hover {
        box-shadow: var(--shadow-md);
        border-color: var(--border-hover);
    }

    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.45rem 1rem;
        margin-bottom: 0.35rem;
        margin-right: 0.5rem;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }

    .status-connected {
        background: #ECFDF5;
        border: 1px solid #A7F3D0;
        color: #000000 !important;
    }

    .status-disconnected {
        background: #FFFBEB;
        border: 1px solid #FDE68A;
        color: #000000 !important;
    }

    /* Sidebar-specific spacing to separate badge from buttons */
    [data-testid="stSidebar"] .status-badge {
        margin-bottom: 0.6rem !important;
        margin-right: 0.5rem !important;
        display: inline-flex !important;
    }

    .section-header {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        color: var(--text-primary) !important;
        margin-bottom: 1rem !important;
        letter-spacing: -0.01em;
        border-bottom: 2px solid var(--border-card);
        padding-bottom: 0.5rem;
    }

    .script-card {
        background: var(--bg-card);
        border: 1px solid var(--border-card);
        border-radius: 10px;
        padding: 0.85rem 1.1rem;
        margin-bottom: 0.4rem;
        transition: all 0.2s ease;
        box-shadow: var(--shadow-sm);
    }

    .script-card:hover {
        border-color: var(--border-hover);
        box-shadow: var(--shadow-md);
    }

    .category-badge {
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        background: #EFF6FF;
        color: var(--accent-blue);
        border: 1px solid #BFDBFE;
    }

    /* ── Sidebar Brand ────────────────────────────────── */
    .sidebar-brand {
        text-align: center;
        padding: 1.2rem 0.5.5 1.5rem 0;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 0.6rem;
    }

    /* Pull the sidebar logo up to remove extra top space */
    [data-testid="stSidebar"] img {
        margin-top: -3rem !important;
        display: block;
        margin-left: auto;
        margin-right: auto;
    }

    .sidebar-brand-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #F1F5F9 !important;
        line-height: 1.3;
        letter-spacing: -0.02em;
    }

    .sidebar-brand-sub {
        font-size: 0.7rem;
        color: #94A3B8 !important;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-top: 0.3rem;
        font-weight: 500;
    }

    .sidebar-brand-logo {
        width: 20px;
        height: auto;
        border-radius: 6px;
        object-fit: contain;
    }

    .sidebar-section {
        font-size: 0.62rem;
        font-weight: 600;
        color: #64748B !important;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        padding: 0.6rem 1rem 0.25rem 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Import scripts to register them
import scripts

# Import pages
from pages import home, script_execution, history, connection_config

# ── Session State Initialization ────────────────────────────────────────
defaults = {
    'sf_client': None,
    'current_result': None,
    'selected_script': None,
    'execution_history': [],
    'current_page': 'home',
    'script_executing': False,
    'executing_script_name': None,
    'execution_console_log': [],
    'execution_progress': 0.0,
    'execution_result': None,
    'execution_error': None
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ── Page Registry ───────────────────────────────────────────────────────
PAGES = {
    'home':             {'label': 'Inicio',           'module': home},
    'script_execution': {'label': 'Ejecutar Scripts',  'module': script_execution},
    'history':          {'label': 'Historial',         'module': history},
    'connection_config': {'label': 'Configuración', 'module': connection_config},
}


def navigate_to(page_key: str):
    """Set session state to navigate to a page."""
    st.session_state.current_page = page_key


def main():
    """Main application function."""

    # ── Sidebar ─────────────────────────────────────────────────────────
    with st.sidebar:
        # Display logo image from project folder on its own line (centered), then brand text below
        logo_path = dashboard_dir / "logo.png"
        try:
            cols = st.columns([1, 2, 1])
            if logo_path.exists():
                cols[1].image(str(logo_path), width=120)
        except Exception:
            pass

        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="sidebar-brand-title">Naturgy Data Scripts</div>
                <div class="sidebar-brand-sub">Dashboard</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="sidebar-section">Navegación</div>', unsafe_allow_html=True)

        for key, page in PAGES.items():
            is_active = st.session_state.current_page == key
            btn_type = "primary" if is_active else "secondary"
            if st.button(page['label'], key=f"nav_{key}", type=btn_type, use_container_width=True):
                navigate_to(key)
                st.rerun()

        st.markdown('<div class="sidebar-section">Conexión</div>', unsafe_allow_html=True)

        if st.session_state.sf_client and st.session_state.sf_client.is_authenticated:
            env = st.session_state.sf_client.env.upper()
            st.markdown(f'<div class="status-badge status-connected">CONECTADO · {env}</div>', unsafe_allow_html=True)
            if st.button("Desconectar", use_container_width=True):
                st.session_state.sf_client.disconnect()
                st.session_state.sf_client = None
                st.rerun()
        else:
            st.markdown('<div class="status-badge status-disconnected">DESCONECTADO</div>', unsafe_allow_html=True)

    # ── Render Active Page ──────────────────────────────────────────────
    current = st.session_state.current_page
    if current in PAGES:
        PAGES[current]['module'].render()
    else:
        PAGES['home']['module'].render()


if __name__ == "__main__":
    main()
