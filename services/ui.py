import streamlit as st

COLOR_DORADO = "#D89B1D"
COLOR_NEGRO = "#111111"
COLOR_CREMA = "#FFF7E6"


def apply_theme():
    st.set_page_config(page_title="Ñam Ñam Web", page_icon="🍝", layout="wide")
    st.markdown(f"""
    <style>
    .stApp {{
        background: linear-gradient(135deg, #090909 0%, #171717 55%, #221805 100%);
        color: #FFF7E6 !important;
    }}

    html, body, [class*="css"] {{
        color: #FFF7E6 !important;
    }}

    [data-testid="stSidebar"] {{
        background-color: #0d0d0d;
        border-right: 2px solid {COLOR_DORADO};
    }}

    [data-testid="stSidebar"] * {{
        color: #ffffff !important;
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

    [data-testid="stSidebar"] [role="radiogroup"] label:hover {{
        background: rgba(216,155,29,.28) !important;
        border: 1px solid {COLOR_DORADO} !important;
    }}

    h1, h2, h3, h4, h5, h6 {{
        color: #FFF7E6 !important;
        opacity: 1 !important;
        font-weight: 900 !important;
    }}

    p, span, label, div, small {{
        color: #FFF7E6 !important;
        opacity: 1 !important;
    }}

    label,
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stNumberInput label,
    .stRadio label,
    .stCheckbox label {{
        color: #FFF7E6 !important;
        font-weight: 900 !important;
        opacity: 1 !important;
    }}

    div[data-testid="stMarkdownContainer"] p {{
        color: #FFF7E6 !important;
        opacity: 1 !important;
        font-weight: 600 !important;
    }}

    div[data-testid="stCaptionContainer"] {{
        color: #ffffff !important;
        opacity: .92 !important;
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
        color: #ffffff !important;
        opacity: 1 !important;
        font-weight: 800;
    }}

    .metric-card b {{
        color: #FFF7E6 !important;
        font-size: 28px;
    }}

    div[data-testid="stMetricValue"] {{
        color: #FFF7E6 !important;
        opacity: 1 !important;
        font-weight: 900 !important;
    }}

    div[data-testid="stMetricLabel"] {{
        color: #ffffff !important;
        opacity: 1 !important;
        font-weight: 900 !important;
    }}

    .stButton>button {{
        background-color: {COLOR_DORADO};
        color: #111 !important;
        border-radius: 12px;
        border: 0;
        font-weight: 900;
    }}

    .stButton>button:hover {{
        background-color: #ffc247;
        color: #111 !important;
        border: 0;
    }}

    input, textarea, select {{
        color: #111111 !important;
        font-weight: 800 !important;
        background-color: #fffaf0 !important;
    }}

    [data-testid="stDataFrame"] * {{
        color: #111111 !important;
    }}

    .stAlert * {{
        color: inherit !important;
        font-weight: 700 !important;
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
