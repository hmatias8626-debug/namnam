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
        color: {COLOR_CREMA};
    }}

    [data-testid="stSidebar"] {{
        background-color: #0d0d0d;
        border-right: 2px solid {COLOR_DORADO};
    }}

    [data-testid="stSidebar"] * {{
        color: #ffffff !important;
        font-size: 18px !important;
    }}

    [data-testid="stSidebar"] a {{
        color: #ffffff !important;
        font-weight: 700 !important;
        padding: 10px 14px !important;
        border-radius: 12px !important;
    }}

    [data-testid="stSidebar"] a:hover {{
        background-color: rgba(216,155,29,.25) !important;
        color: #ffffff !important;
    }}

    [data-testid="stSidebar"] button {{
        color: #111111 !important;
        font-weight: 800 !important;
    }}

    h1, h2, h3 {{
        color: {COLOR_CREMA};
    }}

    .nam-card {{
        background: rgba(255,255,255,.055);
        border: 1px solid rgba(216,155,29,.55);
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 8px 25px rgba(0,0,0,.35);
    }}

    .nam-title {{
        color: {COLOR_DORADO};
        font-weight: 900;
        letter-spacing: .5px;
    }}

    .metric-card {{
        background: rgba(216,155,29,.13);
        border: 1px solid {COLOR_DORADO};
        border-radius: 18px;
        padding: 16px;
    }}

    .metric-card small {{
        color: #dddddd;
    }}

    .metric-card b {{
        color: {COLOR_CREMA};
        font-size: 28px;
    }}

    div[data-testid="stMetricValue"] {{
        color: {COLOR_CREMA};
    }}

    .stButton>button {{
        background-color: {COLOR_DORADO};
        color: #111;
        border-radius: 12px;
        border: 0;
        font-weight: 800;
    }}

    .stButton>button:hover {{
        background-color: #ffc247;
        color: #111;
        border: 0;
    }}

    .stDataFrame, .stTable {{
        background: rgba(255,255,255,.04);
    }}
    </style>
    """, unsafe_allow_html=True)