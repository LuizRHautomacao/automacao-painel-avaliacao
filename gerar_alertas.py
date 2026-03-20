import pandas as pd
import webbrowser
import urllib.parse
from datetime import datetime
from pathlib import Path
import re
import unicodedata

PASTA_ATUAL = Path(__file__).resolve().parent

CANDIDATOS_AVALIACAO = ["avaliacao.xlsx", "avaliacao.xls"]
CANDIDATOS_EMAILS = ["emails.xlsx", "emails.xls"]

ABRIR_QUANTAS_ABAS = 1
MAX_URL_LEN = 2800

MESES_PT = [
    "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"
]

ARQUIVO_HISTORICO = "historico_gcpec.xlsx"
ARQUIVO_PAINEL = "painel_gcpec.html"
ARQUIVO_AUDITORIA_XLSX = "auditoria_lideres.xlsx"
ARQUIVO_AUDITORIA_HTML = "auditoria_lideres.html"
ARQUIVO_LINKS_TXT = "links_emails.txt"
ARQUIVO_LINKS_HTML = "links_emails.html"


# =========================
# UTIL
# =========================

def encontrar_arquivo(candidatos: list[str]) -> Path:
    for nome in candidatos:
        p = PASTA_ATUAL / nome
        if p.exists():
            return p
    raise FileNotFoundError(
        "Não encontrei nenhum destes arquivos na pasta:\n- "
        + "\n- ".join(candidatos)
        + f"\n\nPasta atual: {PASTA_ATUAL}"
    )

def saudacao_por_horario() -> str:
    return "bom dia" if datetime.now().hour < 12 else "boa tarde"

def garantir_coluna(df: pd.DataFrame, nome: str):
    if nome not in df.columns:
        raise KeyError(f"Coluna '{nome}' não encontrada. Colunas disponíveis: {list(df.columns)}")

def vazio_ou_em_aberto(v) -> bool:
    if pd.isna(v):
        return True
    s = str(v).strip().lower()
    return s == "" or s == "em aberto" or s == "nan" or s == "nat"

def tipo_curto(v) -> str:
    s = str(v).strip().lower()
    return "PRORROGADA" if "prorrog" in s else "ORIGINAL"

def html_escape(s: str) -> str:
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))

def normalizar_nome(nome: str) -> str:
    s = str(nome).strip().upper()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# =========================
# DEPARTAMENTO
# =========================

def extrair_departamento(pec: str) -> str:
    try:
        partes = str(pec).split("/")
        miolo = partes[1].strip()
        if " - " in miolo:
            return miolo.split(" - ", 1)[1].strip()
        return miolo
    except Exception:
        return "SEM_DEPARTAMENTO"


# =========================
# COMPETÊNCIA / PRAZO
# =========================

def obter_competencia_e_prazo(df: pd.DataFrame):
    if "Avaliar até" not in df.columns:
        return None, None, None

    prazos = pd.to_datetime(df["Avaliar até"], dayfirst=True, errors="coerce").dropna()
    if prazos.empty:
        return None, None, None

    prazo_mais_comum = prazos.value_counts().index[0]
    mes = MESES_PT[prazo_mais_comum.month - 1]
    ano = int(prazo_mais_comum.year)
    prazo_str = prazo_mais_comum.strftime("%d/%m/%Y")
    return mes, ano, prazo_str


# =========================
# EMAILS
# =========================

def carregar_mapa_emails(caminho: Path) -> dict:
    df_e = pd.read_excel(caminho)

    cols_upper = {str(c).strip().upper(): c for c in df_e.columns}
    col_nome = cols_upper.get("NOME")
    col_email = cols_upper.get("E-MAIL") or cols_upper.get("EMAIL")

    if not col_nome or not col_email:
        raise KeyError(
            f"Planilha de e-mails precisa ter colunas 'Nome' e 'E-MAIL'/'EMAIL'. "
            f"Colunas encontradas: {list(df_e.columns)}"
        )

    df_e = df_e[[col_nome, col_email]].copy()
    df_e[col_nome] = df_e[col_nome].astype(str).str.strip()
    df_e[col_email] = df_e[col_email].astype(str).str.strip()

    mapa = {}
    for _, r in df_e.iterrows():
        nome = r[col_nome]
        email = r[col_email]
        if nome and email and "@" in str(email):
            mapa[normalizar_nome(nome)] = str(email)

    return mapa


# =========================
# STATUS DA AVALIAÇÃO
# =========================

def obter_nome_coluna_superior_avaliacao(df: pd.DataFrame) -> str:
    candidatos = ["Superior.1", "Avaliação do Gestor", "Avaliacao do Gestor", "Gestor"]
    for c in candidatos:
        if c in df.columns:
            return c
    return ""

def status_pendencia(row: pd.Series, col_auto: str, col_gestor_avaliacao: str, col_consenso: str) -> str:
    auto_ok = False if not col_auto else not vazio_ou_em_aberto(row.get(col_auto))
    gestor_ok = False if not col_gestor_avaliacao else not vazio_ou_em_aberto(row.get(col_gestor_avaliacao))
    consenso_ok = False if not col_consenso else not vazio_ou_em_aberto(row.get(col_consenso))

    if consenso_ok:
        return "PROCESSO FINALIZADO"

    if auto_ok and gestor_ok:
        return "FALTA REGISTRO DO CONSENSO"
    if auto_ok and not gestor_ok:
        return "COLABORADOR JÁ REALIZOU A AUTOAVALIAÇÃO; FALTA A AVALIAÇÃO DO GESTOR"
    if not auto_ok and gestor_ok:
        return "GESTOR JÁ REALIZOU A AVALIAÇÃO; FALTA A AUTOAVALIAÇÃO DO COLABORADOR"
    return "FALTA AUTOAVALIAÇÃO DO COLABORADOR E AVALIAÇÃO DO GESTOR"


# =========================
# BLOCO DO LÍDER
# =========================

def montar_bloco_lider(lider: str, g_lider: pd.DataFrame) -> str:
    linhas = []
    linhas.append(f"🟨 GESTOR: {lider}")
    g_lider = g_lider.sort_values(by=["PRIORIDADE", "Colaborador"])
    for _, r in g_lider.iterrows():
        linhas.append(f"   - {r['Colaborador']} | {r['STATUS_PENDENCIA']} ({r['TIPO_CURTO']})")
    linhas.append("")
    return "\n".join(linhas)


# =========================
# GMAIL
# =========================

def gmail_link(assunto: str, corpo: str, to_emails: str) -> str:
    base = "https://mail.google.com/mail/?view=cm&fs=1"
    return (
        base +
        f"&to={urllib.parse.quote(to_emails)}" +
        f"&su={urllib.parse.quote(assunto)}" +
        f"&body={urllib.parse.quote(corpo)}"
    )


# =========================
# EMPACOTAMENTO INTELIGENTE
# =========================

def dividir_pacotes_por_limite(assunto_base: str, cabecalho: str, pacotes_lider: list[dict]) -> list[dict]:
    """
    Cada pacote_lider = {"lider": ..., "bloco": ..., "email": ...}
    Retorna lista de partes com:
    {
        "assunto": ...,
        "corpo": ...,
        "emails": ...
    }
    Cada parte leva somente os e-mails dos líderes contidos nela.
    """
    partes = []
    atuais = []

    def montar_corpo(pacotes):
        blocos = [p["bloco"] for p in pacotes]
        return (cabecalho + "\n\n" + "\n".join(blocos)).strip()

    def montar_emails(pacotes):
        emails = [p["email"] for p in pacotes if p["email"]]
        return ", ".join(sorted(set(emails)))

    for pacote in pacotes_lider:
        tentativa = atuais + [pacote]
        corpo_tent = montar_corpo(tentativa)
        emails_tent = montar_emails(tentativa)
        link_tent = gmail_link(assunto_base, corpo_tent, emails_tent)

        if len(link_tent) <= MAX_URL_LEN:
            atuais = tentativa
        else:
            if not atuais:
                partes.append({
                    "assunto": assunto_base,
                    "corpo": corpo_tent,
                    "emails": emails_tent
                })
                atuais = []
            else:
                partes.append({
                    "assunto": assunto_base,
                    "corpo": montar_corpo(atuais),
                    "emails": montar_emails(atuais)
                })
                atuais = [pacote]

    if atuais:
        partes.append({
            "assunto": assunto_base,
            "corpo": montar_corpo(atuais),
            "emails": montar_emails(atuais)
        })

    if len(partes) == 1:
        return partes

    total = len(partes)
    saida = []
    for i, p in enumerate(partes, start=1):
        saida.append({
            "assunto": f"{p['assunto']} (PARTE {i}/{total})",
            "corpo": p["corpo"],
            "emails": p["emails"]
        })
    return saida


# =========================
# HISTÓRICO
# =========================

def construir_snapshot_historico(df_original: pd.DataFrame, prazo_str: str, mes: str, ano: int, execucao_dt: datetime) -> pd.DataFrame:
    col_auto = "Autoavaliação" if "Autoavaliação" in df_original.columns else ""
    col_consenso = "Consenso"
    col_gestor = obter_nome_coluna_superior_avaliacao(df_original)

    hist = df_original.copy()

    hist["Execucao_DataHora"] = execucao_dt.strftime("%Y-%m-%d %H:%M:%S")
    hist["Execucao_Data"] = execucao_dt.strftime("%Y-%m-%d")
    hist["Execucao_Hora"] = execucao_dt.strftime("%H:%M:%S")
    hist["Prazo_Ciclo"] = prazo_str if prazo_str else ""
    hist["Mes_Ciclo"] = mes if mes else ""
    hist["Ano_Ciclo"] = ano if ano else ""
    hist["DEPARTAMENTO"] = hist["PEC"].apply(extrair_departamento)
    hist["Tipo_Curto"] = hist["Tipo de agendamento"].apply(tipo_curto)

    hist["Auto_Data"] = hist[col_auto] if col_auto else ""
    hist["Gestor_Data"] = hist[col_gestor] if col_gestor else ""
    hist["Consenso_Data"] = hist[col_consenso] if col_consenso else ""

    hist["Status_Pendencia"] = hist.apply(
        lambda row: status_pendencia(row, col_auto, col_gestor, col_consenso),
        axis=1
    )

    cols_out = [
        "Execucao_DataHora", "Execucao_Data", "Execucao_Hora",
        "Mes_Ciclo", "Ano_Ciclo", "Prazo_Ciclo",
        "DEPARTAMENTO", "Superior", "Colaborador", "PEC",
        "Tipo de agendamento", "Tipo_Curto",
        "Auto_Data", "Gestor_Data", "Consenso_Data",
        "Status_Pendencia"
    ]

    for c in cols_out:
        if c not in hist.columns:
            hist[c] = ""

    return hist[cols_out].copy()

def atualizar_historico(snapshot_df: pd.DataFrame, caminho_historico: Path):
    """
    Acrescenta uma nova fotografia do ciclo a cada execução.
    Remove duplicidade exata caso o mesmo snapshot seja gravado duas vezes.
    """
    if caminho_historico.exists():
        try:
            hist_antigo = pd.read_excel(caminho_historico)
            hist_novo = pd.concat([hist_antigo, snapshot_df], ignore_index=True)
        except Exception:
            hist_novo = snapshot_df.copy()
    else:
        hist_novo = snapshot_df.copy()

    # remove duplicidade exata
    hist_novo = hist_novo.drop_duplicates()

    hist_novo.to_excel(caminho_historico, index=False)
    return hist_novo

def classificar_semaforo(percentual_pendente: float) -> str:
    if percentual_pendente <= 20:
        return "🟢"
    elif percentual_pendente <= 50:
        return "🟡"
    return "🔴"


def montar_resumo_historico(historico_df: pd.DataFrame):
    """
    Monta visão por execução para acompanhar evolução do ciclo.
    """
    if historico_df.empty:
        return pd.DataFrame()

    hist = historico_df.copy()
    hist["Consenso_ok"] = ~hist["Consenso_Data"].apply(vazio_ou_em_aberto)

    resumo = (
        hist.groupby(["Execucao_DataHora", "Mes_Ciclo", "Ano_Ciclo", "Prazo_Ciclo"])
        .agg(
            Avaliacoes_Totais=("Colaborador", "count"),
            Concluidas=("Consenso_ok", "sum")
        )
        .reset_index()
    )

    resumo["Pendentes"] = resumo["Avaliacoes_Totais"] - resumo["Concluidas"]
    resumo["Percentual_Concluido"] = (
        resumo["Concluidas"] / resumo["Avaliacoes_Totais"] * 100
    ).round(1)

    resumo = resumo.sort_values(by="Execucao_DataHora")
    return resumo


def montar_semaforo_departamentos(df_original: pd.DataFrame):
    """
    Semáforo por departamento com base no percentual pendente.
    """
    if df_original.empty:
        return pd.DataFrame()

    base = df_original.copy()
    base["DEPARTAMENTO"] = base["PEC"].apply(extrair_departamento)
    base["Consenso_ok"] = ~base["Consenso"].apply(vazio_ou_em_aberto)

    resumo = (
        base.groupby("DEPARTAMENTO")
        .agg(
            Total=("Colaborador", "count"),
            Concluidas=("Consenso_ok", "sum")
        )
        .reset_index()
    )

    resumo["Pendentes"] = resumo["Total"] - resumo["Concluidas"]
    resumo["Percentual_Pendente"] = (resumo["Pendentes"] / resumo["Total"] * 100).round(1)
    resumo["Semaforo"] = resumo["Percentual_Pendente"].apply(classificar_semaforo)

    resumo = resumo.sort_values(by=["Percentual_Pendente", "Pendentes"], ascending=[False, False])
    return resumo


def montar_top_lideres_organizados(df_original: pd.DataFrame):
    """
    Ranking simples de líderes mais organizados com base em:
    - 100% concluído
    - maior volume concluído
    - consenso mais cedo
    """
    if df_original.empty:
        return pd.DataFrame()

    base = df_original.copy()
    base["DEPARTAMENTO"] = base["PEC"].apply(extrair_departamento)
    base["Consenso_ok"] = ~base["Consenso"].apply(vazio_ou_em_aberto)
    base["Consenso_Data_dt"] = pd.to_datetime(base["Consenso"], dayfirst=True, errors="coerce")

    resumo = (
        base.groupby(["DEPARTAMENTO", "Superior"])
        .agg(
            Total=("Colaborador", "count"),
            Concluidos=("Consenso_ok", "sum"),
            Primeiro_Consenso=("Consenso_Data_dt", "min")
        )
        .reset_index()
    )

    resumo["Percentual_Concluido"] = (resumo["Concluidos"] / resumo["Total"] * 100).round(1)

    resumo = resumo.sort_values(
        by=["Percentual_Concluido", "Concluidos", "Primeiro_Consenso"],
        ascending=[False, False, True]
    )

    return resumo


# =========================
# PAINEL
# =========================

def gerar_painel_gcpec(df_original: pd.DataFrame, df_pendencias: pd.DataFrame, historico_df: pd.DataFrame, caminho_html: Path, mes: str, ano: int, prazo_str: str):
    total_lideres = df_pendencias["Superior"].nunique() if not df_pendencias.empty else 0
    total_colabs_pendentes = len(df_pendencias)
    total_prorrogadas = int((df_pendencias["TIPO_CURTO"] == "PRORROGADA").sum()) if not df_pendencias.empty else 0
    total_originais = int((df_pendencias["TIPO_CURTO"] == "ORIGINAL").sum()) if not df_pendencias.empty else 0

    falta_auto = int(df_pendencias["STATUS_PENDENCIA"].str.contains("AUTOAVALIAÇÃO DO COLABORADOR", na=False).sum()) if not df_pendencias.empty else 0
    falta_gestor = int(df_pendencias["STATUS_PENDENCIA"].str.contains("AVALIAÇÃO DO GESTOR", na=False).sum()) if not df_pendencias.empty else 0
    falta_consenso = int(df_pendencias["STATUS_PENDENCIA"].str.contains("CONSENSO", na=False).sum()) if not df_pendencias.empty else 0

    if df_pendencias.empty:
        rank_pend = pd.DataFrame(columns=["DEPARTAMENTO", "Superior", "Pendencias", "Prorrogadas", "Falta_Auto", "Falta_Gestor", "Falta_Consenso"])
        por_departamento = pd.DataFrame(columns=["DEPARTAMENTO", "Lideres", "Colaboradores_Pendentes", "Prorrogadas"])
    else:
        rank_pend = (
            df_pendencias.groupby(["DEPARTAMENTO", "Superior"])
            .agg(
                Pendencias=("Colaborador", "count"),
                Prorrogadas=("TIPO_CURTO", lambda s: int((s == "PRORROGADA").sum())),
                Falta_Auto=("STATUS_PENDENCIA", lambda s: int(s.str.contains("AUTOAVALIAÇÃO DO COLABORADOR", na=False).sum())),
                Falta_Gestor=("STATUS_PENDENCIA", lambda s: int(s.str.contains("AVALIAÇÃO DO GESTOR", na=False).sum())),
                Falta_Consenso=("STATUS_PENDENCIA", lambda s: int(s.str.contains("CONSENSO", na=False).sum()))
            )
            .reset_index()
            .sort_values(by=["Pendencias", "Prorrogadas"], ascending=[False, False])
        )

        por_departamento = (
            df_pendencias.groupby("DEPARTAMENTO")
            .agg(
                Lideres=("Superior", "nunique"),
                Colaboradores_Pendentes=("Colaborador", "count"),
                Prorrogadas=("TIPO_CURTO", lambda s: int((s == "PRORROGADA").sum()))
            )
            .reset_index()
            .sort_values(by=["Colaboradores_Pendentes", "Prorrogadas"], ascending=[False, False])
        )

    # histórico do ciclo
    resumo_historico = montar_resumo_historico(historico_df)
    semaforo_departamentos = montar_semaforo_departamentos(df_original)
    top_organizados = montar_top_lideres_organizados(df_original)

    # ranking de pontualidade via histórico
    hist_ciclo = historico_df.copy()
    if prazo_str:
        hist_ciclo = hist_ciclo[hist_ciclo["Prazo_Ciclo"].astype(str) == str(prazo_str)].copy()

    hist_ciclo["Consenso_Data_dt"] = pd.to_datetime(hist_ciclo["Consenso_Data"], dayfirst=True, errors="coerce")

    ranking_pontualidade = pd.DataFrame(columns=["Superior", "DEPARTAMENTO", "Qtde_Consensos", "Primeiro_Consenso", "Ultimo_Consenso"])
    if not hist_ciclo.empty:
        concluidos = hist_ciclo.dropna(subset=["Consenso_Data_dt"]).copy()

        if not concluidos.empty:
            ranking_pontualidade = (
                concluidos.groupby(["DEPARTAMENTO", "Superior"])
                .agg(
                    Qtde_Consensos=("Colaborador", "count"),
                    Primeiro_Consenso=("Consenso_Data_dt", "min"),
                    Ultimo_Consenso=("Consenso_Data_dt", "max")
                )
                .reset_index()
                .sort_values(by=["Primeiro_Consenso", "Qtde_Consensos"], ascending=[True, False])
            )

    with open(caminho_html, "w", encoding="utf-8") as f:
        f.write("<html><head><meta charset='utf-8'>"
                "<title>Painel GCPEC</title>"
                "<style>"
                "body{font-family:Arial;margin:20px;background:#fafafa;color:#222}"
                "h1,h2{margin-top:28px}"
                ".cards{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}"
                ".card{background:white;border:1px solid #ddd;border-radius:10px;padding:14px;min-width:220px;box-shadow:0 1px 2px rgba(0,0,0,.04)}"
                ".big{font-size:28px;font-weight:700;margin-top:8px}"
                "table{border-collapse:collapse;width:100%;background:white;margin-top:10px}"
                "th,td{border:1px solid #ddd;padding:8px;text-align:left}"
                "th{background:#f2f2f2}"
                ".small{color:#666;font-size:12px}"
                ".tag{display:inline-block;padding:3px 8px;border-radius:999px;background:#fff3cd;color:#8a6d3b;font-size:12px;margin-left:6px}"
                "</style></head><body>")

        f.write("<h1>Painel Operacional GCPEC</h1>")
        if mes and ano:
            f.write(f"<div class='small'>Ciclo: {html_escape(mes)} {ano}</div>")
        if prazo_str:
            f.write(f"<div class='small'>Prazo final: {html_escape(prazo_str)}</div>")

        # resumo geral
        f.write("<h2>Resumo Geral</h2>")
        f.write("<div class='cards'>")
        resumo_cards = [
            ("Líderes com pendência", total_lideres),
            ("Colaboradores pendentes", total_colabs_pendentes),
            ("Prorrogadas", total_prorrogadas),
            ("Originais", total_originais),
            ("Falta autoavaliação", falta_auto),
            ("Falta avaliação do gestor", falta_gestor),
            ("Falta consenso", falta_consenso),
        ]
        for titulo, valor in resumo_cards:
            f.write(f"<div class='card'><div>{html_escape(titulo)}</div><div class='big'>{valor}</div></div>")
        f.write("</div>")

        # avanço do ciclo
        if not resumo_historico.empty:
            ultimo = resumo_historico.iloc[-1]
            f.write("<h2>% de Avanço do Ciclo</h2>")
            f.write("<div class='cards'>")
            cards_avanco = [
                ("Avaliações totais", int(ultimo["Avaliacoes_Totais"])),
                ("Concluídas", int(ultimo["Concluidas"])),
                ("Pendentes", int(ultimo["Pendentes"])),
                ("Progresso do ciclo", f"{float(ultimo['Percentual_Concluido']):.1f}%")
            ]
            for titulo, valor in cards_avanco:
                f.write(f"<div class='card'><div>{html_escape(titulo)}</div><div class='big'>{valor}</div></div>")
            f.write("</div>")

            f.write("<h2>Histórico das Execuções</h2>")
            f.write("<table><tr><th>Execução</th><th>Total</th><th>Concluídas</th><th>Pendentes</th><th>% Concluído</th></tr>")
            for _, r in resumo_historico.iterrows():
                f.write(
                    "<tr>"
                    f"<td>{html_escape(str(r['Execucao_DataHora']))}</td>"
                    f"<td>{int(r['Avaliacoes_Totais'])}</td>"
                    f"<td>{int(r['Concluidas'])}</td>"
                    f"<td>{int(r['Pendentes'])}</td>"
                    f"<td>{float(r['Percentual_Concluido']):.1f}%</td>"
                    "</tr>"
                )
            f.write("</table>")

        # semáforo
        f.write("<h2>Semáforo por Departamento</h2>")
        if semaforo_departamentos.empty:
            f.write("<p>Sem dados para o semáforo.</p>")
        else:
            f.write("<table><tr><th>Semáforo</th><th>Departamento</th><th>Total</th><th>Concluídas</th><th>Pendentes</th><th>% Pendente</th></tr>")
            for _, r in semaforo_departamentos.iterrows():
                f.write(
                    "<tr>"
                    f"<td>{html_escape(r['Semaforo'])}</td>"
                    f"<td>{html_escape(r['DEPARTAMENTO'])}</td>"
                    f"<td>{int(r['Total'])}</td>"
                    f"<td>{int(r['Concluidas'])}</td>"
                    f"<td>{int(r['Pendentes'])}</td>"
                    f"<td>{float(r['Percentual_Pendente']):.1f}%</td>"
                    "</tr>"
                )
            f.write("</table>")

        # resumo por departamento
        f.write("<h2>Resumo por Departamento</h2>")
        f.write("<table><tr><th>Departamento</th><th>Líderes</th><th>Colaboradores pendentes</th><th>Prorrogadas</th></tr>")
        for _, r in por_departamento.iterrows():
            f.write(
                "<tr>"
                f"<td>{html_escape(r['DEPARTAMENTO'])}</td>"
                f"<td>{int(r['Lideres'])}</td>"
                f"<td>{int(r['Colaboradores_Pendentes'])}</td>"
                f"<td>{int(r['Prorrogadas'])}</td>"
                "</tr>"
            )
        f.write("</table>")

        # ranking pendências
        f.write("<h2>Ranking de Pendências</h2>")
        f.write("<table><tr><th>Departamento</th><th>Líder</th><th>Pendências</th><th>Prorrogadas</th><th>Falta Auto</th><th>Falta Gestor</th><th>Falta Consenso</th></tr>")
        for _, r in rank_pend.head(40).iterrows():
            f.write(
                "<tr>"
                f"<td>{html_escape(r['DEPARTAMENTO'])}</td>"
                f"<td>{html_escape(r['Superior'])}</td>"
                f"<td>{int(r['Pendencias'])}</td>"
                f"<td>{int(r['Prorrogadas'])}</td>"
                f"<td>{int(r['Falta_Auto'])}</td>"
                f"<td>{int(r['Falta_Gestor'])}</td>"
                f"<td>{int(r['Falta_Consenso'])}</td>"
                "</tr>"
            )
        f.write("</table>")

        # pontualidade
        f.write("<h2>Ranking de Pontualidade (Consensos)</h2>")
        if ranking_pontualidade.empty:
            f.write("<p>Sem dados suficientes de consenso no histórico para montar o ranking ainda.</p>")
        else:
            f.write("<table><tr><th>Departamento</th><th>Líder</th><th>Qtde consensos</th><th>Primeiro consenso</th><th>Último consenso</th></tr>")
            for _, r in ranking_pontualidade.head(30).iterrows():
                f.write(
                    "<tr>"
                    f"<td>{html_escape(r['DEPARTAMENTO'])}</td>"
                    f"<td>{html_escape(r['Superior'])}</td>"
                    f"<td>{int(r['Qtde_Consensos'])}</td>"
                    f"<td>{r['Primeiro_Consenso'].strftime('%d/%m/%Y') if pd.notna(r['Primeiro_Consenso']) else ''}</td>"
                    f"<td>{r['Ultimo_Consenso'].strftime('%d/%m/%Y') if pd.notna(r['Ultimo_Consenso']) else ''}</td>"
                    "</tr>"
                )
            f.write("</table>")

        # organizados
        f.write("<h2>Top 10 Líderes Mais Organizados</h2>")
        if top_organizados.empty:
            f.write("<p>Sem dados suficientes para esse ranking ainda.</p>")
        else:
            f.write("<table><tr><th>Departamento</th><th>Líder</th><th>Total</th><th>Concluídos</th><th>% Concluído</th><th>Primeiro Consenso</th></tr>")
            for _, r in top_organizados.head(10).iterrows():
                primeiro = ""
                if pd.notna(r["Primeiro_Consenso"]):
                    primeiro = r["Primeiro_Consenso"].strftime("%d/%m/%Y")
                f.write(
                    "<tr>"
                    f"<td>{html_escape(r['DEPARTAMENTO'])}</td>"
                    f"<td>{html_escape(r['Superior'])} <span class='tag'>DESTAQUE</span></td>"
                    f"<td>{int(r['Total'])}</td>"
                    f"<td>{int(r['Concluidos'])}</td>"
                    f"<td>{float(r['Percentual_Concluido']):.1f}%</td>"
                    f"<td>{primeiro}</td>"
                    "</tr>"
                )
            f.write("</table>")

        # reconhecimento
        reconhecimento_destaque = top_organizados[top_organizados["Percentual_Concluido"] >= 100].copy()
        f.write("<h2>Reconhecimento dos Líderes Mais Organizados</h2>")
        if reconhecimento_destaque.empty:
            f.write("<p>Ainda não há líderes com 100% concluído neste ciclo.</p>")
        else:
            f.write("<table><tr><th>Departamento</th><th>Líder</th><th>Total</th><th>Concluídos</th><th>% Concluído</th></tr>")
            for _, r in reconhecimento_destaque.head(30).iterrows():
                f.write(
                    "<tr>"
                    f"<td>{html_escape(r['DEPARTAMENTO'])}</td>"
                    f"<td>{html_escape(r['Superior'])} <span class='tag'>DESTAQUE</span></td>"
                    f"<td>{int(r['Total'])}</td>"
                    f"<td>{int(r['Concluidos'])}</td>"
                    f"<td>{float(r['Percentual_Concluido']):.1f}%</td>"
                    "</tr>"
                )
            f.write("</table>")

        f.write("</body></html>")

# =========================
# MAIN
# =========================

def main():
    arquivo_avaliacao = encontrar_arquivo(CANDIDATOS_AVALIACAO)
    arquivo_emails = encontrar_arquivo(CANDIDATOS_EMAILS)

    df_original = pd.read_excel(arquivo_avaliacao)

    garantir_coluna(df_original, "Superior")
    garantir_coluna(df_original, "Colaborador")
    garantir_coluna(df_original, "PEC")
    garantir_coluna(df_original, "Consenso")
    garantir_coluna(df_original, "Tipo de agendamento")

    col_auto = "Autoavaliação" if "Autoavaliação" in df_original.columns else ""
    col_consenso = "Consenso"
    col_gestor_avaliacao = obter_nome_coluna_superior_avaliacao(df_original)

    df_original["Superior"] = df_original["Superior"].astype(str).str.strip()
    df_original["Colaborador"] = df_original["Colaborador"].astype(str).str.strip()
    df_original["PEC"] = df_original["PEC"].astype(str).str.strip()

    mes, ano, prazo_str = obter_competencia_e_prazo(df_original)
    saudacao = saudacao_por_horario()

    execucao_dt = datetime.now()

    snapshot_df = construir_snapshot_historico(df_original, prazo_str, mes, ano, execucao_dt)
    historico_df = atualizar_historico(snapshot_df, PASTA_ATUAL / ARQUIVO_HISTORICO)

    # pendências
    df = df_original[df_original["Consenso"].apply(vazio_ou_em_aberto)].copy()
    if df.empty:
        print("Nenhuma pendência encontrada (consenso em aberto).")
        gerar_painel_gcpec(df_original, df, historico_df, PASTA_ATUAL / ARQUIVO_PAINEL, mes, ano, prazo_str)
        return

    df["DEPARTAMENTO"] = df["PEC"].apply(extrair_departamento)
    df["TIPO_CURTO"] = df["Tipo de agendamento"].apply(tipo_curto)
    df["PRIORIDADE"] = df["TIPO_CURTO"].apply(lambda x: 0 if x == "PRORROGADA" else 1)

    df["STATUS_PENDENCIA"] = df.apply(
        lambda row: status_pendencia(row, col_auto, col_gestor_avaliacao, col_consenso),
        axis=1
    )

    dept_principal_por_lider = (
        df.groupby("Superior")["DEPARTAMENTO"]
        .agg(lambda s: s.value_counts().index[0])
        .to_dict()
    )
    df["DEPARTAMENTO"] = df["Superior"].map(dept_principal_por_lider)

    df = df.sort_values(by=["DEPARTAMENTO", "PRIORIDADE", "Superior", "Colaborador"])

    mapa_emails = carregar_mapa_emails(arquivo_emails)

    links = []
    auditoria = []

    for dept, g_dept in df.groupby("DEPARTAMENTO"):
        lideres = sorted(g_dept["Superior"].dropna().astype(str).str.strip().unique().tolist())

        faltando = []
        pacotes_lider = []

        for lider in lideres:
            email = mapa_emails.get(normalizar_nome(lider), "")
            sub_df = g_dept[g_dept["Superior"] == lider]

            qtd_colabs = len(sub_df)
            qtd_falta_auto = int(sub_df["STATUS_PENDENCIA"].str.contains("AUTOAVALIAÇÃO DO COLABORADOR", na=False).sum())
            qtd_falta_gestor = int(sub_df["STATUS_PENDENCIA"].str.contains("AVALIAÇÃO DO GESTOR", na=False).sum())
            qtd_falta_consenso = int(sub_df["STATUS_PENDENCIA"].str.contains("CONSENSO", na=False).sum())

            if email:
                status_email = "OK"
            else:
                status_email = "SEM_EMAIL"
                faltando.append(lider)

            auditoria.append({
                "DEPARTAMENTO": dept,
                "Lider": lider,
                "Qtde_Colaboradores": qtd_colabs,
                "Falta_Autoavaliacao": qtd_falta_auto,
                "Falta_Avaliacao_Gestor": qtd_falta_gestor,
                "Falta_Consenso": qtd_falta_consenso,
                "Email_Encontrado": status_email,
                "Email": email
            })

            pacotes_lider.append({
                "lider": lider,
                "email": email,
                "bloco": montar_bloco_lider(lider, sub_df)
            })

        if mes and ano:
            linha_periodo = f"Encaminhamos abaixo a lista de colaboradores com avaliações pendentes para {mes} de {ano}."
        else:
            linha_periodo = "Encaminhamos abaixo a lista de colaboradores com avaliações pendentes neste mês."

        linha_prazo = f"Data limite para conclusão no sistema: {prazo_str}." if prazo_str else ""

        tem_prorrogadas = (g_dept["TIPO_CURTO"] == "PRORROGADA").any()

        if tem_prorrogadas:
            linha_alerta = (
                "Solicitamos que o gestor realize sua avaliação e oriente seus colaboradores a concluírem a autoavaliação, "
                "priorizando especialmente as avaliações PRORROGADAS, pois esta é a última oportunidade para finalização dentro do prazo."
            )
        else:
            linha_alerta = (
                "Solicitamos que o gestor realize sua avaliação e oriente seus colaboradores a concluírem a autoavaliação, "
                "etapa indispensável para o fechamento do processo dentro do prazo."
            )

        linha_gcpec = (
            "Reforçamos a importância de comunicar o colaborador com antecedência, "
            "considerando que dificuldades de acesso ao GCPEC, como esquecimento de senha, podem impactar o cumprimento do prazo."
        )

        cabecalho = (
            f"Prezado(a) Gestor(a), {saudacao}!\n\n"
            f"{linha_periodo}\n"
            + (f"{linha_prazo}\n" if linha_prazo else "")
            + "\n"
            f"{linha_alerta}\n\n"
            f"{linha_gcpec}\n\n"
            "IMPORTANTE:\n"
            "A avaliação somente é considerada finalizada após:\n"
            "- o colaborador concluir a autoavaliação;\n"
            "- o gestor concluir a avaliação;\n"
            "- e ambos registrarem o CONSENSO no sistema.\n\n"
            "Em caso de dúvidas, nossa equipe permanece à disposição.\n"
            "Atenciosamente,\n"
        ).strip()

        if mes and ano:
            assunto_base = f"AVALIAÇÃO DE DESEMPENHO – {mes} {ano} – {dept}"
        else:
            assunto_base = f"AVALIAÇÃO DE DESEMPENHO – {dept}"

        partes = dividir_pacotes_por_limite(assunto_base, cabecalho, pacotes_lider)

        for parte in partes:
            link = gmail_link(parte["assunto"], parte["corpo"], parte["emails"])
            links.append((dept, parte["assunto"], link, faltando, parte["emails"]))

    # TXT
    txt_path = PASTA_ATUAL / ARQUIVO_LINKS_TXT
    with open(txt_path, "w", encoding="utf-8") as f:
        for dept, assunto, link, faltando, emails_parte in links:
            f.write(f"{dept}\n{assunto}\nPARA: {emails_parte}\n{link}\n")
            if faltando:
                f.write("SEM EMAIL CADASTRADO PARA:\n")
                for n in faltando[:30]:
                    f.write(f"- {n}\n")
                if len(faltando) > 30:
                    f.write(f"... +{len(faltando)-30} nomes\n")
            f.write("\n")

    # HTML LINKS
    html_path = (PASTA_ATUAL / ARQUIVO_LINKS_HTML).resolve()
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("<html><head><meta charset='utf-8'>"
                "<title>Links de e-mails</title>"
                "<style>"
                "body{font-family:Arial;margin:20px}"
                ".card{margin:10px 0;padding:12px;border:1px solid #ddd;border-radius:10px}"
                ".dept{font-weight:700;margin-bottom:6px}"
                ".ass{color:#444;margin-bottom:6px}"
                ".para{color:#0f766e;font-size:12px;margin-bottom:6px;white-space:pre-line}"
                ".warn{color:#b45309;margin-top:8px;white-space:pre-line}"
                "a{display:inline-block;margin-top:6px}"
                "</style></head><body>")
        f.write("<h2>Links de e-mails por departamento</h2>")
        f.write("<p>Clique em <b>Abrir e-mail</b> para gerar o rascunho no Gmail. Cada parte leva apenas os líderes presentes nela.</p>")

        for dept, assunto, link, faltando, emails_parte in links:
            f.write("<div class='card'>")
            f.write(f"<div class='dept'>{html_escape(dept)}</div>")
            f.write(f"<div class='ass'>{html_escape(assunto)}</div>")
            f.write(f"<div class='para'>Para: {html_escape(emails_parte)}</div>")
            f.write(f"<a href='{html_escape(link)}'>Abrir e-mail</a>")
            if faltando:
                aviso = "Sem e-mail cadastrado para:\n" + "\n".join(f"- {x}" for x in faltando[:20])
                if len(faltando) > 20:
                    aviso += f"\n... +{len(faltando)-20} nomes"
                f.write(f"<div class='warn'>{html_escape(aviso)}</div>")
            f.write("</div>")
        f.write("</body></html>")

    # AUDITORIA XLSX
    auditoria_df = pd.DataFrame(auditoria).sort_values(by=["DEPARTAMENTO", "Lider"])
    auditoria_xlsx = PASTA_ATUAL / ARQUIVO_AUDITORIA_XLSX
    auditoria_df.to_excel(auditoria_xlsx, index=False)

    # AUDITORIA HTML
    auditoria_html = (PASTA_ATUAL / ARQUIVO_AUDITORIA_HTML).resolve()
    with open(auditoria_html, "w", encoding="utf-8") as f:
        f.write("<html><head><meta charset='utf-8'>"
                "<title>Auditoria de Líderes</title>"
                "<style>"
                "body{font-family:Arial;margin:20px}"
                "table{border-collapse:collapse;width:100%}"
                "th,td{border:1px solid #ddd;padding:8px;text-align:left}"
                "th{background:#f5f5f5}"
                ".ok{color:green;font-weight:700}"
                ".sem{color:#b45309;font-weight:700}"
                "</style></head><body>")
        f.write("<h2>Auditoria de Líderes</h2>")
        f.write("<p>Conferência dos líderes encontrados na planilha de avaliação e seus e-mails.</p>")
        f.write("<table>")
        f.write(
            "<tr>"
            "<th>Departamento</th>"
            "<th>Líder</th>"
            "<th>Qtd. Colaboradores</th>"
            "<th>Falta Autoavaliação</th>"
            "<th>Falta Avaliação do Gestor</th>"
            "<th>Falta Consenso</th>"
            "<th>E-mail Encontrado</th>"
            "<th>Email</th>"
            "</tr>"
        )
        for _, r in auditoria_df.iterrows():
            cls = "ok" if r["Email_Encontrado"] == "OK" else "sem"
            f.write(
                "<tr>"
                f"<td>{html_escape(r['DEPARTAMENTO'])}</td>"
                f"<td>{html_escape(r['Lider'])}</td>"
                f"<td>{int(r['Qtde_Colaboradores'])}</td>"
                f"<td>{int(r['Falta_Autoavaliacao'])}</td>"
                f"<td>{int(r['Falta_Avaliacao_Gestor'])}</td>"
                f"<td>{int(r['Falta_Consenso'])}</td>"
                f"<td class='{cls}'>{html_escape(r['Email_Encontrado'])}</td>"
                f"<td>{html_escape(r['Email'])}</td>"
                "</tr>"
            )
        f.write("</table></body></html>")

    # PAINEL
    gerar_painel_gcpec(
        df_original=df_original,
        df_pendencias=df,
        historico_df=historico_df,
        caminho_html=PASTA_ATUAL / ARQUIVO_PAINEL,
        mes=mes,
        ano=ano,
        prazo_str=prazo_str
    )

    # ABRIR
    for _, _, link, _, _ in links[:ABRIR_QUANTAS_ABAS]:
        webbrowser.open(link)

    webbrowser.open(html_path.as_uri())
    webbrowser.open(auditoria_html.as_uri())
    webbrowser.open((PASTA_ATUAL / ARQUIVO_PAINEL).resolve().as_uri())

    print(f"OK! {len(links)} link(s) gerados.")
    print(
        f"Arquivos: {ARQUIVO_LINKS_TXT}, {ARQUIVO_LINKS_HTML}, "
        f"{ARQUIVO_AUDITORIA_XLSX}, {ARQUIVO_AUDITORIA_HTML}, "
        f"{ARQUIVO_HISTORICO}, {ARQUIVO_PAINEL}"
    )
    print(f"Abrindo automaticamente: {ABRIR_QUANTAS_ABAS} aba(s) + páginas HTML")

if __name__ == "__main__":
    main()