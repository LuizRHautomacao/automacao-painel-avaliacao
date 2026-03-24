import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================
st.set_page_config(
    page_title="Painel Avaliações GCPEC",
    layout="wide"
)

# =========================================================
# ESTILO VISUAL
# =========================================================
st.markdown("""
<style>
    .main {
        background-color: #f4f7fb;
    }

    .block-container {
        padding-top: 0.8rem;
        padding-bottom: 1rem;
        max-width: 98%;
    }

    h1, h2, h3 {
        color: #0b2e59;
    }

    section[data-testid="stSidebar"] {
        display: none;
    }

    .faixa-topo {
        background: linear-gradient(90deg, #0b2e59 0%, #114a8b 100%);
        color: white;
        padding: 16px 22px;
        border-radius: 12px;
        margin-bottom: 12px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.10);
    }

    .faixa-topo h1 {
        color: white !important;
        margin: 0;
        font-size: 2rem;
        font-weight: 800;
    }

    .faixa-topo p {
        margin: 4px 0 0 0;
        font-size: 0.95rem;
        opacity: 0.95;
    }

    .secao-titulo {
        background: #103d73;
        color: white;
        padding: 8px 14px;
        border-radius: 8px;
        margin-top: 8px;
        margin-bottom: 8px;
        font-weight: 700;
        font-size: 1rem;
    }

    .card-kpi {
        background: white;
        border: 1px solid #d9e2f1;
        border-left: 6px solid #114a8b;
        border-radius: 12px;
        padding: 12px 14px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.05);
        min-height: 88px;
    }

    .card-kpi.verde { border-left-color: #1f9d55; }
    .card-kpi.vermelho { border-left-color: #dc2626; }
    .card-kpi.amarelo { border-left-color: #f59e0b; }
    .card-kpi.azul { border-left-color: #114a8b; }

    .kpi-label {
        color: #4b5875;
        font-size: 0.88rem;
        margin-bottom: 8px;
        font-weight: 600;
    }

    .kpi-value {
        color: #0f172a;
        font-size: 1.95rem;
        line-height: 1.05;
        font-weight: 800;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .kpi-small {
        color: #64748b;
        font-size: 0.80rem;
        margin-top: 6px;
    }

    .box-bloco {
        background: white;
        border: 1px solid #d9e2f1;
        border-radius: 12px;
        padding: 10px 10px 6px 10px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.05);
    }

    .meta-box {
        background: white;
        border: 1px solid #d9e2f1;
        border-radius: 12px;
        padding: 14px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.05);
    }

    .filtro-box {
        background: white;
        border: 1px solid #d9e2f1;
        border-radius: 12px;
        padding: 10px 14px 4px 14px;
        box-shadow: 0 3px 10px rgba(0,0,0,0.05);
        margin-bottom: 8px;
    }

    .status-ok {
        color: #1f9d55;
        font-weight: 700;
    }

    .status-alerta {
        color: #f59e0b;
        font-weight: 700;
    }

    .status-critico {
        color: #dc2626;
        font-weight: 700;
    }

    div[data-testid="stDataFrame"] {
        background: white;
        border-radius: 12px;
        border: 1px solid #d9e2f1;
        padding: 6px;
    }

    div[data-testid="stExpander"] {
        border: 1px solid #d9e2f1;
        border-radius: 10px;
        background: white;
    }

    .stMultiSelect label,
    .stCheckbox label {
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        color: #42526b !important;
    }

    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMarkdownContainer"]) {
        gap: 0.35rem;
    }

    .stButton > button {
        border-radius: 10px;
        border: 1px solid #c9d8ef;
        background: #ffffff;
        color: #103d73;
        font-weight: 700;
        height: 2.5rem;
    }

    .stButton > button:hover {
        border-color: #103d73;
        color: #103d73;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================
def card_kpi(label, value, subtitulo="", cor="azul"):
    st.markdown(
        f"""
        <div class="card-kpi {cor}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" title="{value}">{value}</div>
            <div class="kpi-small">{subtitulo}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def normalizar_departamento(df_):
    if "Departamento" in df_.columns and "DEPARTAMENTO" in df_.columns:
        return df_["Departamento"].fillna(df_["DEPARTAMENTO"])
    if "Departamento" in df_.columns:
        return df_["Departamento"]
    if "DEPARTAMENTO" in df_.columns:
        return df_["DEPARTAMENTO"]
    return pd.Series(["SEM DEPARTAMENTO"] * len(df_))

def classificar_status(status):
    s = str(status).upper()

    if "PROCESSO FINALIZADO" in s:
        return "Concluído"

    if "CONSENSO" in s:
        return "Pronto para consenso"

    if "FALTA" in s:
        return "Atrasado"

    return "Atrasado"

def resumo_nome(nome, limite=20):
    nome = str(nome) if pd.notna(nome) else "—"
    return nome if len(nome) <= limite else nome[:limite] + "..."

# =========================================================
# ESTADO DOS FILTROS
# =========================================================
if "filtro_ano" not in st.session_state:
    st.session_state.filtro_ano = []
if "filtro_mes" not in st.session_state:
    st.session_state.filtro_mes = []
if "filtro_lider" not in st.session_state:
    st.session_state.filtro_lider = []
if "filtro_dep" not in st.session_state:
    st.session_state.filtro_dep = []
if "filtro_status" not in st.session_state:
    st.session_state.filtro_status = []
if "filtro_pendentes" not in st.session_state:
    st.session_state.filtro_pendentes = False

def limpar_filtros():
    st.session_state.filtro_ano = anos.copy()
    st.session_state.filtro_mes = []
    st.session_state.filtro_lider = []
    st.session_state.filtro_dep = []
    st.session_state.filtro_status = []
    st.session_state.filtro_pendentes = False

# =========================================================
# CARREGAR BASE
# =========================================================
PASTA_ATUAL = Path(__file__).resolve().parent
ARQUIVO = PASTA_ATUAL / "historico_gcpec.xlsx"

df = pd.read_excel(ARQUIVO)
df.columns = df.columns.str.strip()

if "Execucao_DataHora" in df.columns:
    df["Execucao_DataHora"] = pd.to_datetime(df["Execucao_DataHora"], errors="coerce")

df["Departamento_Final"] = normalizar_departamento(df)
df["Status_Sintese"] = df["Status_Pendencia"].apply(classificar_status)

# =========================================================
# BASE ATUAL = ÚLTIMA EXECUÇÃO
# =========================================================
ultima_execucao = df["Execucao_DataHora"].max()
df_base = df[df["Execucao_DataHora"] == ultima_execucao].copy()

anos = sorted(df_base["Ano_Ciclo"].dropna().unique().tolist())
meses = sorted(df_base["Mes_Ciclo"].dropna().unique().tolist())
lideres = sorted(df_base["Superior"].dropna().unique().tolist())
deps = sorted(df_base["Departamento_Final"].dropna().unique().tolist())

if not st.session_state.filtro_ano:
    st.session_state.filtro_ano = anos.copy()

# =========================================================
# TOPO
# =========================================================
ciclo_txt = "—"
if "Mes_Ciclo" in df_base.columns and "Ano_Ciclo" in df_base.columns and len(df_base) > 0:
    ciclo_txt = f"{df_base['Mes_Ciclo'].iloc[0]} / {df_base['Ano_Ciclo'].iloc[0]}"

st.markdown(
    f"""
    <div class="faixa-topo">
        <h1>📊 Painel Operacional GCPEC</h1>
        <p><strong>Ciclo:</strong> {ciclo_txt} &nbsp;&nbsp;|&nbsp;&nbsp;
        <strong>Base atualizada:</strong> {ultima_execucao.strftime('%d/%m/%Y %H:%M:%S') if pd.notna(ultima_execucao) else '—'}</p>
    </div>
    """,
    unsafe_allow_html=True
)

# =========================================================
# FILTROS NO TOPO
# =========================================================
st.markdown('<div class="secao-titulo">Filtros</div>', unsafe_allow_html=True)
st.markdown('<div class="filtro-box">', unsafe_allow_html=True)

f1, f2, f3, f4, f5, f6, f7 = st.columns([1, 1, 1.5, 1.5, 1.2, 0.9, 0.8])

with f1:
    ano_sel = st.multiselect("Ano", anos, key="filtro_ano")
with f2:
    mes_sel = st.multiselect("Mês", meses, key="filtro_mes")
with f3:
    lider_sel = st.multiselect("Líder", lideres, key="filtro_lider")
with f4:
    dep_sel = st.multiselect("Departamento", deps, key="filtro_dep")
with f5:
    status_sel = st.multiselect(
        "Status",
        ["Concluído", "Pronto para consenso", "Atrasado"],
        key="filtro_status"
    )
with f6:
    st.markdown("<div style='height: 26px;'></div>", unsafe_allow_html=True)
    somente_pendentes = st.checkbox("Só pendentes", key="filtro_pendentes")
with f7:
    st.markdown("<div style='height: 26px;'></div>", unsafe_allow_html=True)
    st.button("Limpar", use_container_width=True, on_click=limpar_filtros)

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# APLICAR FILTROS
# =========================================================
df_filtrado = df_base.copy()

if ano_sel:
    df_filtrado = df_filtrado[df_filtrado["Ano_Ciclo"].isin(ano_sel)]

if mes_sel:
    df_filtrado = df_filtrado[df_filtrado["Mes_Ciclo"].isin(mes_sel)]

if lider_sel:
    df_filtrado = df_filtrado[df_filtrado["Superior"].isin(lider_sel)]

if dep_sel:
    df_filtrado = df_filtrado[df_filtrado["Departamento_Final"].isin(dep_sel)]

if status_sel:
    df_filtrado = df_filtrado[df_filtrado["Status_Sintese"].isin(status_sel)]

if somente_pendentes:
    df_filtrado = df_filtrado[df_filtrado["Status_Sintese"] != "Concluído"]

# =========================================================
# INDICADORES
# =========================================================
total = len(df_filtrado)
concluidas = int((df_filtrado["Status_Sintese"] == "Concluído").sum())
pendentes = int(total - concluidas)
atrasados = int((df_filtrado["Status_Sintese"] == "Atrasado").sum())
pronto_consenso = int((df_filtrado["Status_Sintese"] == "Pronto para consenso").sum())

falta_auto = int(df_filtrado["Status_Pendencia"].astype(str).str.upper().str.contains("AUTOAVALIA").sum())
falta_gestor = int(df_filtrado["Status_Pendencia"].astype(str).str.upper().str.contains("GESTOR").sum())
falta_consenso = int(df_filtrado["Status_Pendencia"].astype(str).str.upper().str.contains("CONSENSO").sum())
prorrogadas = int(df_filtrado["Tipo_Curto"].astype(str).str.upper().str.contains("PRORROG").sum()) if "Tipo_Curto" in df_filtrado.columns else 0
originais = int(df_filtrado["Tipo_Curto"].astype(str).str.upper().str.contains("ORIGINAL").sum()) if "Tipo_Curto" in df_filtrado.columns else 0

progresso = round((concluidas / total) * 100, 1) if total else 0.0
meta = 80.0
faltam_para_meta = max(0, round((meta / 100 * total) - concluidas)) if total else 0

lideres_com_pendencia = df_filtrado.loc[df_filtrado["Status_Sintese"] != "Concluído", "Superior"].nunique()

ranking_atraso = (
    df_filtrado[df_filtrado["Status_Sintese"] != "Concluído"]
    .groupby("Superior")
    .size()
    .reset_index(name="Pendencias")
    .sort_values("Pendencias", ascending=False)
)

ranking_conc = (
    df_filtrado[df_filtrado["Status_Sintese"] == "Concluído"]
    .groupby("Superior")
    .size()
    .reset_index(name="Concluidas")
    .sort_values("Concluidas", ascending=False)
)

mais_atrasado = ranking_atraso.iloc[0]["Superior"] if not ranking_atraso.empty else "—"
mais_adiantado = ranking_conc.iloc[0]["Superior"] if not ranking_conc.empty else "—"

lideres_100 = (
    df_filtrado.groupby("Superior")["Status_Sintese"]
    .apply(lambda s: (s == "Concluído").all())
    .reset_index(name="Tudo_Concluido")
)
qtd_lideres_100 = int(lideres_100["Tudo_Concluido"].sum()) if not lideres_100.empty else 0

dep_pendencias = (
    df_filtrado[df_filtrado["Status_Sintese"] != "Concluído"]
    .groupby("Departamento_Final")
    .size()
    .reset_index(name="Pendencias")
    .sort_values("Pendencias", ascending=False)
)
dep_mais_critico = dep_pendencias.iloc[0]["Departamento_Final"] if not dep_pendencias.empty else "—"

primeiros_a_concluir = (
    df_filtrado[df_filtrado["Status_Sintese"] == "Concluído"]
    .groupby("Superior")
    .size()
    .reset_index(name="Concluidas")
    .sort_values(["Concluidas", "Superior"], ascending=[False, True])
    .head(5)
)

# =========================================================
# KPIS PRINCIPAIS
# =========================================================
st.markdown('<div class="secao-titulo">Resumo Executivo</div>', unsafe_allow_html=True)
k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    card_kpi("Avaliações totais", total, "Base da última execução", "azul")
with k2:
    card_kpi("Concluídas", concluidas, f"{progresso}% do ciclo", "verde")
with k3:
    card_kpi("Pendentes", pendentes, "Ainda exigem ação", "vermelho")
with k4:
    card_kpi("Líderes com pendência", lideres_com_pendencia, "Gestão com itens abertos", "amarelo")
with k5:
    card_kpi("Prorrogadas", prorrogadas, "Itens reprogramados", "amarelo")
with k6:
    card_kpi("Originais", originais, "Pendências do ciclo", "azul")

st.markdown('<div class="secao-titulo">Indicadores Críticos</div>', unsafe_allow_html=True)
k7, k8, k9, k10, k11, k12 = st.columns(6)

with k7:
    card_kpi("Falta autoavaliação", falta_auto, "Do colaborador", "vermelho")
with k8:
    card_kpi("Falta avaliação gestor", falta_gestor, "Pendência da liderança", "vermelho")
with k9:
    card_kpi("Pronto para consenso", pronto_consenso, "Etapa final pendente", "amarelo")
with k10:
    card_kpi("Mais atrasado", resumo_nome(mais_atrasado, 18), "Maior volume pendente", "vermelho")
with k11:
    card_kpi("Mais adiantado", resumo_nome(mais_adiantado, 18), "Maior volume concluído", "verde")
with k12:
    card_kpi("Líderes com 100%", qtd_lideres_100, "Todas concluídas", "verde")

# =========================================================
# META VISUAL
# =========================================================
st.markdown('<div class="secao-titulo">Meta do Ciclo</div>', unsafe_allow_html=True)
m1, m2 = st.columns([2, 1])

with m1:
    st.markdown('<div class="meta-box">', unsafe_allow_html=True)
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=progresso,
        number={"suffix": "%"},
        delta={"reference": meta, "increasing": {"color": "#1f9d55"}, "decreasing": {"color": "#dc2626"}},
        title={"text": "Progresso do ciclo"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#114a8b"},
            "steps": [
                {"range": [0, 50], "color": "#fee2e2"},
                {"range": [50, 80], "color": "#fef3c7"},
                {"range": [80, 100], "color": "#dcfce7"},
            ],
            "threshold": {
                "line": {"color": "#dc2626", "width": 4},
                "thickness": 0.8,
                "value": meta
            }
        }
    ))
    fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=5))
    st.plotly_chart(fig_gauge, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with m2:
    st.markdown('<div class="meta-box">', unsafe_allow_html=True)
    if progresso >= meta:
        status_meta = '<span class="status-ok">Meta atingida</span>'
    elif progresso >= 60:
        status_meta = '<span class="status-alerta">Atenção para a meta</span>'
    else:
        status_meta = '<span class="status-critico">Abaixo da meta</span>'

    st.markdown(f"""
        <div style="font-size:1rem; color:#4b5875; font-weight:700;">Meta definida</div>
        <div style="font-size:2rem; font-weight:800; color:#0f172a;">{meta:.1f}%</div>
        <div style="margin-top:12px; font-size:1rem; color:#4b5875; font-weight:700;">Situação</div>
        <div style="font-size:1.15rem;">{status_meta}</div>
        <div style="margin-top:12px; font-size:1rem; color:#4b5875; font-weight:700;">Faltam para a meta</div>
        <div style="font-size:1.8rem; font-weight:800; color:#0f172a;">{faltam_para_meta}</div>
        <div style="margin-top:6px; color:#64748b;">avaliações concluídas necessárias</div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# GRÁFICOS 1
# =========================================================
st.markdown('<div class="secao-titulo">Visão Gerencial</div>', unsafe_allow_html=True)
g1, g2, g3 = st.columns([1.1, 1.1, 1.0])

with g1:
    st.markdown('<div class="box-bloco">', unsafe_allow_html=True)
    st.subheader("Status Geral")
    graf_status = (
        df_filtrado.groupby("Status_Sintese")
        .size()
        .reset_index(name="Quantidade")
    )
    fig_status = px.pie(
        graf_status,
        names="Status_Sintese",
        values="Quantidade",
        hole=0.48,
        color="Status_Sintese",
        color_discrete_map={
            "Concluído": "#16a34a",
            "Pronto para consenso": "#f59e0b",
            "Atrasado": "#dc2626"
        }
    )
    fig_status.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10), legend_title="")
    st.plotly_chart(fig_status, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with g2:
    st.markdown('<div class="box-bloco">', unsafe_allow_html=True)
    st.subheader("Pendências por Tipo")
    pend_tipos = pd.DataFrame({
        "Indicador": ["Falta autoavaliação", "Falta gestor", "Pronto para consenso", "Atrasados"],
        "Quantidade": [falta_auto, falta_gestor, pronto_consenso, atrasados]
    })
    fig_tipos = px.bar(
        pend_tipos,
        x="Quantidade",
        y="Indicador",
        orientation="h",
        color="Quantidade",
        color_continuous_scale="OrRd"
    )
    fig_tipos.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10), yaxis_title="", xaxis_title="")
    st.plotly_chart(fig_tipos, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with g3:
    st.markdown('<div class="box-bloco">', unsafe_allow_html=True)
    st.subheader("Departamento mais crítico")
    st.markdown(f"""
        <div style="font-size:0.95rem; color:#4b5875; font-weight:700;">Maior volume de pendências</div>
        <div style="font-size:1.85rem; font-weight:800; color:#0f172a; margin-top:8px;" title="{dep_mais_critico}">
            {resumo_nome(dep_mais_critico, 24)}
        </div>
        <div style="margin-top:16px; font-size:0.95rem; color:#4b5875; font-weight:700;">Top destaques de conclusão</div>
    """, unsafe_allow_html=True)

    if not primeiros_a_concluir.empty:
        st.dataframe(
            primeiros_a_concluir.rename(columns={"Superior": "Líder", "Concluidas": "Conclusões"}),
            use_container_width=True,
            height=210
        )
    else:
        st.info("Ainda não há líderes com avaliações concluídas.")
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# GRÁFICOS 2
# =========================================================
st.markdown('<div class="secao-titulo">Rankings Operacionais</div>', unsafe_allow_html=True)
r1, r2 = st.columns(2)

with r1:
    st.markdown('<div class="box-bloco">', unsafe_allow_html=True)
    st.subheader("Top líderes com mais pendências")
    top_atraso = ranking_atraso.head(10).sort_values("Pendencias", ascending=True)
    fig_atraso = px.bar(
        top_atraso,
        x="Pendencias",
        y="Superior",
        orientation="h",
        color="Pendencias",
        color_continuous_scale="Reds"
    )
    fig_atraso.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10), yaxis_title="", xaxis_title="Pendências")
    st.plotly_chart(fig_atraso, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with r2:
    st.markdown('<div class="box-bloco">', unsafe_allow_html=True)
    st.subheader("Top líderes com mais conclusões")
    top_conc = ranking_conc.head(10).sort_values("Concluidas", ascending=True)
    fig_conc = px.bar(
        top_conc,
        x="Concluidas",
        y="Superior",
        orientation="h",
        color="Concluidas",
        color_continuous_scale="Greens"
    )
    fig_conc.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10), yaxis_title="", xaxis_title="Concluídas")
    st.plotly_chart(fig_conc, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# GRÁFICOS 3
# =========================================================
st.markdown('<div class="secao-titulo">Departamentos e Tendência</div>', unsafe_allow_html=True)
d1, d2 = st.columns([1.2, 1.0])

with d1:
    st.markdown('<div class="box-bloco">', unsafe_allow_html=True)
    st.subheader("Departamentos mais críticos")

    graf_dep = (
        df_filtrado[df_filtrado["Status_Sintese"] != "Concluído"]
        .groupby("Departamento_Final")
        .size()
        .reset_index(name="Pendências")
        .sort_values("Pendências", ascending=False)
        .head(12)
        .sort_values("Pendências", ascending=True)
    )

    fig_dep = px.bar(
        graf_dep,
        x="Pendências",
        y="Departamento_Final",
        orientation="h",
        color="Pendências",
        color_continuous_scale="Reds"
    )

    fig_dep.update_layout(
        height=390,
        margin=dict(l=10, r=10, t=20, b=10),
        yaxis_title="",
        xaxis_title="Quantidade de pendências"
    )

    st.plotly_chart(fig_dep, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

with d2:
    st.markdown('<div class="box-bloco">', unsafe_allow_html=True)
    st.subheader("Histórico de avanço do ciclo")
    hist = (
        df.groupby("Execucao_DataHora")
        .agg(
            Total=("Colaborador", "size"),
            Concluidas=("Status_Pendencia", lambda s: s.astype(str).str.upper().str.contains("PROCESSO FINALIZADO").sum())
        )
        .reset_index()
    )
    hist["Pendentes"] = hist["Total"] - hist["Concluidas"]
    hist["% Concluido"] = (hist["Concluidas"] / hist["Total"] * 100).round(1)

    fig_hist = px.line(
        hist,
        x="Execucao_DataHora",
        y="% Concluido",
        markers=True
    )
    fig_hist.update_traces(line=dict(width=3, color="#114a8b"))
    fig_hist.update_layout(height=390, margin=dict(l=10, r=10, t=20, b=10), xaxis_title="Execução", yaxis_title="% concluído")
    st.plotly_chart(fig_hist, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# HISTÓRICO TABELA
# =========================================================
st.markdown('<div class="secao-titulo">Histórico das Execuções</div>', unsafe_allow_html=True)
with st.expander("Abrir histórico consolidado"):
    hist_exibir = hist.copy()
    hist_exibir["Execucao_DataHora"] = hist_exibir["Execucao_DataHora"].dt.strftime("%d/%m/%Y %H:%M:%S")
    st.dataframe(hist_exibir, use_container_width=True, height=260)

# =========================================================
# BASE DETALHADA ESCONDIDA
# =========================================================
st.markdown('<div class="secao-titulo">Base Detalhada da Última Execução</div>', unsafe_allow_html=True)
with st.expander("Abrir base detalhada"):
    colunas_prioritarias = [
        c for c in [
            "Execucao_DataHora", "Mes_Ciclo", "Ano_Ciclo", "Superior", "Colaborador",
            "Departamento_Final", "Status_Pendencia", "Status_Sintese", "Tipo_Curto", "PEC"
        ] if c in df_filtrado.columns
    ]

    st.dataframe(
        df_filtrado[colunas_prioritarias + [c for c in df_filtrado.columns if c not in colunas_prioritarias]],
        use_container_width=True,
        height=430
    )