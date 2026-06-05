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
        color: {COLOR_CREMA} !important;
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
        font-weight: 700 !important;
    }}

    [data-testid="stSidebar"] [role="radiogroup"] label {{
        background: rgba(255,255,255,.045) !important;
        border: 1px solid rgba(216,155,29,.35) !important;
        border-radius: 13px !important;
        padding: 9px 12px !important;
        margin-bottom: 6px !important;
    }}

    [data-testid="stSidebar"] [role="radiogroup"] label:hover {{
        background: rgba(216,155,29,.22) !important;
        border: 1px solid {COLOR_DORADO} !important;
    }}

    h1, h2, h3, h4, h5, h6 {{
        color: #FFF7E6 !important;
        opacity: 1 !important;
    }}

    p, span, label, div {{
        color: #FFF7E6;
    }}

    label,
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stNumberInput label,
    .stRadio label,
    .stCheckbox label {{
        color: #FFF7E6 !important;
        font-weight: 800 !important;
        opacity: 1 !important;
    }}

    div[data-testid="stForm"] label,
    div[data-testid="stMarkdownContainer"] p {{
        color: #FFF7E6 !important;
        opacity: 1 !important;
    }}

    .nam-card {{
        background: rgba(255,255,255,.07);
        border: 1px solid rgba(216,155,29,.65);
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 8px 25px rgba(0,0,0,.35);
    }}

    .nam-title {{
        color: {COLOR_DORADO} !important;
        font-weight: 900;
        letter-spacing: .5px;
        text-shadow: 0 2px 10px rgba(216,155,29,.2);
    }}

    .metric-card {{
        background: rgba(216,155,29,.16);
        border: 1px solid {COLOR_DORADO};
        border-radius: 18px;
        padding: 16px;
    }}

    .metric-card small {{
        color: #ffffff !important;
        opacity: .92 !important;
        font-weight: 700;
    }}

    .metric-card b {{
        color: {COLOR_CREMA} !important;
        font-size: 28px;
    }}

    div[data-testid="stMetricValue"] {{
        color: {COLOR_CREMA} !important;
    }}

    div[data-testid="stMetricLabel"] {{
        color: #ffffff !important;
        opacity: 1 !important;
        font-weight: 800 !important;
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

    .stDataFrame, .stTable {{
        background: rgba(255,255,255,.04);
    }}

    input, textarea, select {{
        color: #111111 !important;
        font-weight: 700 !important;
    }}

    .stAlert div {{
        color: inherit !important;
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
