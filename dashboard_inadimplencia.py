import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

st.set_page_config(
    page_title="Dashboard de Inadimplência",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MESES_PT = {
    "Jan": "Jan", "Feb": "Fev", "Mar": "Mar", "Apr": "Abr",
    "May": "Mai", "Jun": "Jun", "Jul": "Jul", "Aug": "Ago",
    "Sep": "Set", "Oct": "Out", "Nov": "Nov", "Dec": "Dez",
}

def fmt_mes(dt):
    eng = dt.strftime("%b/%y")
    for en, pt in MESES_PT.items():
        eng = eng.replace(en, pt)
    return eng

def fmt_brl(value):
    if abs(value) >= 1_000_000:
        return f"R$ {value/1_000_000:.2f}M".replace(".", ",")
    elif abs(value) >= 1_000:
        return f"R$ {value/1_000:.1f}K".replace(".", ",")
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_brl_full(value):
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"

def fmt_pct(value):
    return f"{value * 100:.2f}%".replace(".", ",")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        background-color: #f8fafc;
        color: #1e293b;
    }

    .main { background-color: #f8fafc; }
    .block-container { padding: 2rem 2.5rem; }

    .kpi-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        text-align: center;
        height: 130px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .kpi-label {
        font-size: 0.75rem;
        font-weight: 500;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.5rem;
    }
    .kpi-value {
        font-size: 1.9rem;
        font-weight: 700;
        color: #1e293b;
        line-height: 1.1;
    }
    .kpi-sub {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-top: 0.25rem;
    }
    .kpi-value.red { color: #dc2626; }
    .kpi-value.yellow { color: #d97706; }
    .kpi-value.blue { color: #2563eb; }

    .section-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 1rem;
        padding-top: 0.5rem;
    }

    /* Streamlit dataframe */
    .stDataFrame { border-radius: 10px; overflow: hidden; }

    /* Remove default streamlit borders */
    div[data-testid="stVerticalBlock"] > div { background: transparent !important; }
    .stFileUploader > div { background: #ffffff !important; border: 1.5px dashed #cbd5e1 !important; border-radius: 12px !important; }
    .stFileUploader label { color: #64748b !important; }
</style>
""", unsafe_allow_html=True)


def load_tendencia(file) -> pd.DataFrame:
    try:
        df = pd.read_excel(file, sheet_name="Tendencia", engine="openpyxl", header=0)
    except Exception:
        return None

    df = df.iloc[:, :4].copy()
    df.columns = ["mes", "emitido", "inadimplente", "pct"]

    df["emitido"] = pd.to_numeric(df["emitido"], errors="coerce")
    df["inadimplente"] = pd.to_numeric(df["inadimplente"], errors="coerce")
    df["pct"] = pd.to_numeric(df["pct"], errors="coerce")
    df["mes"] = pd.to_datetime(df["mes"], errors="coerce")

    df = df[df["emitido"].notna() & df["inadimplente"].notna() & df["mes"].notna()].copy()
    df = df.sort_values("mes").reset_index(drop=True)
    df["mes_label"] = df["mes"].apply(fmt_mes)
    return df


def color_for_pct(pct, min_v, max_v):
    if max_v == min_v:
        return "#f59e0b"
    ratio = (pct - min_v) / (max_v - min_v)
    if ratio < 0.5:
        r = int(59 + (245 - 59) * ratio * 2)
        g = int(130 + (158 - 130) * ratio * 2)
        b = int(246 + (11 - 246) * ratio * 2)
    else:
        ratio2 = (ratio - 0.5) * 2
        r = int(245 + (239 - 245) * ratio2)
        g = int(158 + (68 - 158) * ratio2)
        b = int(11 + (68 - 11) * ratio2)
    return f"#{r:02x}{g:02x}{b:02x}"


def build_line_chart(df: pd.DataFrame) -> go.Figure:
    min_p, max_p = df["pct"].min(), df["pct"].max()
    avg_p = df["pct"].mean()

    colors = [color_for_pct(p, min_p, max_p) for p in df["pct"]]
    worst_idx = df["pct"].idxmax()

    fig = go.Figure()

    # Área de fundo (gradiente simulado)
    fig.add_trace(go.Scatter(
        x=df["mes_label"],
        y=df["pct"],
        fill="tozeroy",
        fillcolor="rgba(239,68,68,0.08)",
        line=dict(color="rgba(0,0,0,0)", width=0),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Linha principal segmentada por cor
    for i in range(len(df) - 1):
        fig.add_trace(go.Scatter(
            x=[df["mes_label"].iloc[i], df["mes_label"].iloc[i + 1]],
            y=[df["pct"].iloc[i], df["pct"].iloc[i + 1]],
            mode="lines",
            line=dict(color=colors[i], width=2.5),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Pontos com hover e labels de percentual
    labels = [fmt_pct(p) for p in df["pct"]]
    # Posição do label: acima ou abaixo para evitar colisão com a anotação do pior mês
    text_positions = []
    for i, p in enumerate(df["pct"]):
        if i == worst_idx:
            text_positions.append("bottom center")
        elif i > 0 and df["pct"].iloc[i] < df["pct"].iloc[i - 1]:
            text_positions.append("top center")
        else:
            text_positions.append("top center")

    fig.add_trace(go.Scatter(
        x=df["mes_label"],
        y=df["pct"],
        mode="markers+text",
        marker=dict(color=colors, size=7, line=dict(color="#f8fafc", width=1.5)),
        text=labels,
        textposition=text_positions,
        textfont=dict(family="DM Sans", size=10, color="#475569"),
        showlegend=False,
        customdata=np.stack([
            df["emitido"].values,
            df["inadimplente"].values,
            df["pct"].values,
        ], axis=-1),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "% Inadimplência: <b>%{customdata[2]:.2%}</b><br>"
            "Emitido: <b>R$ %{customdata[0]:,.2f}</b><br>"
            "Inadimplente: <b>R$ %{customdata[1]:,.2f}</b>"
            "<extra></extra>"
        ),
    ))

    # Linha de média
    fig.add_hline(
        y=avg_p,
        line=dict(color="#94a3b8", width=1.5, dash="dot"),
        annotation_text=f"Média {fmt_pct(avg_p)}",
        annotation_position="top left",
        annotation_font=dict(color="#64748b", size=11),
    )

    # Anotação do pior mês
    fig.add_annotation(
        x=df["mes_label"].iloc[worst_idx],
        y=df["pct"].iloc[worst_idx],
        text=f"Pior: {fmt_pct(df['pct'].iloc[worst_idx])}",
        showarrow=True,
        arrowhead=2,
        arrowcolor="#ef4444",
        arrowsize=1,
        arrowwidth=1.5,
        ax=0, ay=-36,
        font=dict(color="#dc2626", size=11, family="DM Sans"),
        bgcolor="#ffffff",
        bordercolor="#dc2626",
        borderwidth=1,
        borderpad=4,
    )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(family="DM Sans", size=11, color="#64748b"),
            linecolor="#e2e8f0",
        ),
        yaxis=dict(
            tickformat=".1%",
            showgrid=True,
            gridcolor="#f1f5f9",
            tickfont=dict(family="DM Sans", size=11, color="#64748b"),
            linecolor="#e2e8f0",
            range=[0, df["pct"].max() * 1.18],
        ),
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor="#e2e8f0",
            font=dict(family="DM Sans", size=12, color="#1e293b"),
        ),
        height=360,
    )
    return fig


def build_bar_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Emitido",
        x=df["mes_label"],
        y=df["emitido"],
        marker_color="#3b82f6",
        marker_line_width=0,
        customdata=df["emitido"],
        hovertemplate="<b>%{x}</b><br>Emitido: <b>R$ %{y:,.2f}</b><extra></extra>",
    ))

    fig.add_trace(go.Bar(
        name="Inadimplente",
        x=df["mes_label"],
        y=df["inadimplente"],
        marker_color="#ef4444",
        marker_line_width=0,
        hovertemplate="<b>%{x}</b><br>Inadimplente: <b>R$ %{y:,.2f}</b><extra></extra>",
    ))

    def y_tick(val):
        if val >= 1_000_000:
            return f"R$ {val/1_000_000:.1f}M"
        elif val >= 1_000:
            return f"R$ {val/1_000:.0f}K"
        return f"R$ {val:.0f}"

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        barmode="group",
        bargap=0.25,
        bargroupgap=0.05,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left", x=0,
            font=dict(family="DM Sans", size=11, color="#64748b"),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            showgrid=False,
            tickfont=dict(family="DM Sans", size=11, color="#64748b"),
            linecolor="#e2e8f0",
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#f1f5f9",
            tickfont=dict(family="DM Sans", size=11, color="#64748b"),
            linecolor="#e2e8f0",
            tickprefix="",
        ),
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor="#e2e8f0",
            font=dict(family="DM Sans", size=12, color="#1e293b"),
        ),
        height=300,
    )
    return fig


def render_kpis(df: pd.DataFrame):
    last = df.iloc[-1]
    worst = df.loc[df["pct"].idxmax()]
    total_emitido = df["emitido"].sum()
    total_inadimplente = df["inadimplente"].sum()

    last_pct = last["pct"]
    pct_class = "red" if last_pct > 0.20 else ("yellow" if last_pct > 0.10 else "blue")

    cols = st.columns(4)
    cards = [
        {
            "label": "Último % Inadimplência",
            "value": fmt_pct(last_pct),
            "sub": last["mes_label"],
            "cls": pct_class,
        },
        {
            "label": "Pior Mês",
            "value": fmt_pct(worst["pct"]),
            "sub": worst["mes_label"],
            "cls": "red",
        },
        {
            "label": "Total Emitido",
            "value": fmt_brl(total_emitido),
            "sub": "acumulado do período",
            "cls": "blue",
        },
        {
            "label": "Total Inadimplente",
            "value": fmt_brl(total_inadimplente),
            "sub": "acumulado do período",
            "cls": "red",
        },
    ]

    for col, card in zip(cols, cards):
        with col:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{card['label']}</div>
                    <div class="kpi-value {card['cls']}">{card['value']}</div>
                    <div class="kpi-sub">{card['sub']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_table(df: pd.DataFrame):
    display = df[["mes_label", "emitido", "inadimplente", "pct"]].copy()
    display.columns = ["Mês/Ref", "Emitido", "Inadimplente", "%"]

    min_p, max_p = df["pct"].min(), df["pct"].max()

    def pct_color_bg(val):
        try:
            v = float(val)
        except Exception:
            return ""
        if max_p == min_p:
            ratio = 0.5
        else:
            ratio = (v - min_p) / (max_p - min_p)
        r = int(50 + ratio * (180 - 50))
        g = int(150 - ratio * (150 - 50))
        b = 50
        return f"background-color: rgba({r},{g},{b},0.25); color: #1e293b;"

    def style_row(row):
        styles = [""] * len(row)
        pct_idx = list(row.index).index("%")
        styles[pct_idx] = pct_color_bg(row["%"])
        return styles

    formatted = pd.DataFrame({
        "Mês/Ref": display["Mês/Ref"],
        "Emitido": display["Emitido"].apply(fmt_brl_full),
        "Inadimplente": display["Inadimplente"].apply(fmt_brl_full),
        "%": display["%"].apply(fmt_pct),
    })

    raw_pct = df["pct"].values

    styled = formatted.style.apply(
        lambda row: style_row(row), axis=1
    ).set_properties(**{
        "background-color": "#ffffff",
        "color": "#1e293b",
        "border": "1px solid #e2e8f0",
        "font-family": "DM Sans, sans-serif",
        "font-size": "13px",
    }).set_table_styles([
        {"selector": "thead th", "props": [
            ("background-color", "#f8fafc"),
            ("color", "#64748b"),
            ("font-size", "11px"),
            ("text-transform", "uppercase"),
            ("letter-spacing", "0.08em"),
            ("border-bottom", "1px solid #e2e8f0"),
        ]},
        {"selector": "tbody tr:hover td", "props": [
            ("background-color", "#f1f5f9 !important"),
        ]},
    ])

    st.dataframe(styled, use_container_width=True, hide_index=True)


# ── Layout ────────────────────────────────────────────────────────────────────

st.markdown('<p style="font-size:1.6rem;font-weight:700;color:#1e293b;margin-bottom:0.25rem;">Dashboard de Inadimplência</p>', unsafe_allow_html=True)
st.markdown('<p style="font-size:0.85rem;color:#64748b;margin-bottom:1.5rem;">Análise da aba <code>Tendencia</code> — upload do arquivo .xlsx para carregar os dados</p>', unsafe_allow_html=True)

uploaded = st.file_uploader(
    "Selecione o arquivo .xlsx",
    type=["xlsx"],
    label_visibility="collapsed",
)

if uploaded is None:
    st.markdown("""
    <div style="background:#ffffff;border:1.5px dashed #cbd5e1;border-radius:12px;padding:3rem;text-align:center;margin-top:1rem;">
        <div style="font-size:2.5rem;margin-bottom:1rem;">📂</div>
        <div style="color:#64748b;font-size:1rem;font-weight:500;">Arraste ou selecione um arquivo .xlsx acima</div>
        <div style="color:#94a3b8;font-size:0.8rem;margin-top:0.5rem;">O arquivo deve conter a aba <strong>Tendencia</strong></div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

df = load_tendencia(uploaded)

if df is None:
    st.error("Não foi possível ler a aba **Tendencia** do arquivo. Verifique se a aba existe e se o formato está correto.")
    st.stop()

if df.empty:
    st.warning("A aba **Tendencia** foi encontrada, mas não contém dados válidos nas colunas esperadas.")
    st.stop()

# KPIs
render_kpis(df)

st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)

# Gráfico de linha
st.markdown('<div class="section-title">Evolução do % de Inadimplência</div>', unsafe_allow_html=True)
st.plotly_chart(build_line_chart(df), use_container_width=True, config={"displayModeBar": False})

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# Gráfico de barras
st.markdown('<div class="section-title">Emitido vs Inadimplente</div>', unsafe_allow_html=True)
st.plotly_chart(build_bar_chart(df), use_container_width=True, config={"displayModeBar": False})

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

# Tabela
st.markdown('<div class="section-title">Dados detalhados</div>', unsafe_allow_html=True)
render_table(df)
