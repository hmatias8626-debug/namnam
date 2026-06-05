import streamlit as st

COLOR_DORADO = "#D89B1D"
COLOR_CREMA = "#FFF7E6"


def apply_theme():
    st.set_page_config(page_title="Ñam Ñam Web", page_icon="🍝", layout="wide")
    st.markdown(f"""
    <style>
    .stApp {{
        background: linear-gradient(135deg, #090909 0%, #171717 55%, #221805 100%);
        color: #FFF7E6 !important;
    }}

    h1, h2, h3, h4, h5, h6 {{
        color: #FFF7E6 !important;
        opacity: 1 !important;
        font-weight: 900 !important;
    }}

    p, label, small {{
        color: #FFF7E6 !important;
        opacity: 1 !important;
        font-weight: 700 !important;
    }}

    div[data-testid="stMarkdownContainer"] p {{
        color: #FFF7E6 !important;
        opacity: 1 !important;
    }}

    div[data-testid="stCaptionContainer"] {{
        color: #FFFFFF !important;
        opacity: .95 !important;
    }}

    label,
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stNumberInput label,
    .stRadio label {{
        color: #FFF7E6 !important;
        font-weight: 900 !important;
        opacity: 1 !important;
    }}

    [data-testid="stSidebar"] {{
        background-color: #0d0d0d;
        border-right: 2px solid {COLOR_DORADO};
    }}

    [data-testid="stSidebar"] * {{
        color: #FFFFFF !important;
        opacity: 1 !important;
    }}

    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {{
        font-size: 18px !important;
        font-weight: 800 !important;
    }}

    [data-testid="stSidebar"] [role="radiogroup"] label {{
        background: rgba(255,255,255,.075) !important;
        border: 1px solid rgba(216,155,29,.45) !important;
        border-radius: 13px !important;
        padding: 10px 12px !important;
        margin-bottom: 7px !important;
    }}

    .nam-title {{
        color: {COLOR_DORADO} !important;
        font-weight: 950 !important;
        letter-spacing: .5px;
        text-shadow: 0 2px 12px rgba(216,155,29,.22);
    }}

    .metric-card {{
        background: rgba(216,155,29,.18);
        border: 1px solid {COLOR_DORADO};
        border-radius: 18px;
        padding: 16px;
    }}

    .metric-card small {{
        color: #FFFFFF !important;
        opacity: 1 !important;
        font-weight: 800;
    }}

    .metric-card b {{
        color: #FFF7E6 !important;
        font-size: 28px;
    }}

    div[data-testid="stMetricValue"],
    div[data-testid="stMetricLabel"] {{
        color: #FFF7E6 !important;
        opacity: 1 !important;
        font-weight: 900 !important;
    }}

    .stButton>button {{
        background-color: {COLOR_DORADO};
        color: #111111 !important;
        border-radius: 12px;
        border: 0;
        font-weight: 900;
    }}

    .stButton>button:hover {{
        background-color: #ffc247;
        color: #111111 !important;
        border: 0;
    }}

    /* Inputs normales */
    input, textarea {{
        color: #111111 !important;
        background-color: #FFF7E6 !important;
        font-weight: 800 !important;
    }}

    /* Selectbox cerrado */
    div[data-baseweb="select"] > div {{
        background-color: #FFF7E6 !important;
        color: #111111 !important;
        border: 2px solid {COLOR_DORADO} !important;
    }}

    div[data-baseweb="select"] span {{
        color: #111111 !important;
        font-weight: 800 !important;
    }}

    /* Dropdown abierto del selectbox */
    div[data-baseweb="popover"] * {{
        color: #111111 !important;
        background-color: #FFFFFF !important;
        font-weight: 800 !important;
    }}

    div[data-baseweb="menu"] {{
        background-color: #FFFFFF !important;
    }}

    div[data-baseweb="menu"] li,
    div[data-baseweb="menu"] div {{
        color: #111111 !important;
        background-color: #FFFFFF !important;
        font-weight: 800 !important;
    }}

    div[data-baseweb="menu"] li:hover,
    div[data-baseweb="menu"] div:hover {{
        background-color: #FFE3A1 !important;
        color: #111111 !important;
    }}

    /* Number input botones */
    button[kind="secondary"] {{
        color: #111111 !important;
    }}

    /* Dataframes: fondo claro, texto oscuro */
    [data-testid="stDataFrame"] * {{
        color: #111111 !important;
    }}

    .stAlert * {{
        font-weight: 800 !important;
    }}

    div[role="radiogroup"] label {{
        background: rgba(255,255,255,.075) !important;
        border: 1px solid rgba(216,155,29,.35) !important;
        border-radius: 13px !important;
        padding: 8px 12px !important;
        margin: 4px !important;
    }}

    div[role="radiogroup"] label:hover {{
        background: rgba(216,155,29,.22) !important;
        border-color: {COLOR_DORADO} !important;
    }}
    </style>
    """, unsafe_allow_html=True)


def header(title: str, subtitle: str = ""):
    st.markdown(f"<h1 class='nam-title'>{title}</h1>", unsafe_allow_html=True)
    if subtitle:
        st.caption(subtitle)


def card_metric(label: str, value: str):
    st.markdown(
        f"<div class='metric-card'><small>{label}</small><br><b>{value}</b></div>",
        unsafe_allow_html=True
    )
