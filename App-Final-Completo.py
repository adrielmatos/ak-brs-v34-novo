import base64
import html
import json
import os
import re
from datetime import datetime, timedelta

import pandas as pd
import requests
import streamlit as st

# ============================================================
# CONFIGURAÇÃO
# ============================================================
st.set_page_config(
    page_title="Discadora Eletrônica A&K",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "3.0"
LOCAL_FILE = "brs_dados_local.json"
GITHUB_PATH = "brs_dados.json"

BANCO_EMOJI = {
    "PAN": "🟢",
    "SAFRA": "🟠",
    "BMG": "🔵",
    "C6": "⚫",
    "ITAU": "🔷",
    "ITAÚ": "🔷",
    "OLE": "🟡",
    "PARANÁ": "🟣",
    "DEFAULT": "⚪",
}

STATUS_LABELS = {
    "pendente": "Pendente",
    "atendido": "Atendido",
    "nao_atendeu": "Não atendeu",
    "retorno_futuro": "Retorno",
    "venda_finalizada": "Venda",
    "arquivado": "Arquivado",
}

STATUS_COLORS = {
    "pendente": "#00e5ff",
    "atendido": "#00ff88",
    "nao_atendeu": "#ffab00",
    "retorno_futuro": "#7c4dff",
    "venda_finalizada": "#ff6d00",
    "arquivado": "#78909c",
}


# ============================================================
# ESTILO
# ============================================================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

:root {
    --bg: #070a10;
    --panel: rgba(18, 23, 34, .78);
    --panel-2: rgba(255, 255, 255, .035);
    --line: rgba(255,255,255,.08);
    --cyan: #00e5ff;
    --green: #00ff88;
    --gold: #ffab00;
    --purple: #8b5cf6;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 8% 8%, rgba(0,229,255,.08), transparent 28%),
        radial-gradient(circle at 88% 12%, rgba(124,77,255,.08), transparent 24%),
        radial-gradient(circle at 50% 90%, rgba(0,255,136,.05), transparent 30%),
        var(--bg);
    color: #f7f9fc;
}

header[data-testid="stHeader"] {
    background: transparent;
}

section[data-testid="stSidebar"] {
    background: rgba(8, 11, 18, .92) !important;
    border-right: 1px solid var(--line);
}

.block-container {
    padding-top: 1.1rem;
    padding-bottom: 2rem;
}

div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button {
    border-radius: 11px;
    border: 1px solid rgba(255,255,255,.09);
    background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025));
    color: #fff;
    min-height: 40px;
    font-weight: 700;
    transition: all .18s ease;
}

div[data-testid="stButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover {
    transform: translateY(-1px);
    border-color: rgba(0,229,255,.35);
    box-shadow: 0 8px 22px rgba(0,229,255,.12);
}

div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #00e5ff, #00ff88);
    color: #041014;
    border: 0;
}

div[data-baseweb="input"] input,
div[data-baseweb="select"] > div,
textarea {
    border-radius: 10px !important;
}

div[data-testid="stMetric"] {
    background: var(--panel-2);
    border: 1px solid var(--line);
    border-radius: 15px;
    padding: 10px 12px;
}

.ak-header {
    padding: 18px 20px;
    border: 1px solid rgba(0,229,255,.15);
    border-radius: 20px;
    background:
        linear-gradient(135deg, rgba(0,229,255,.06), rgba(0,255,136,.03)),
        rgba(18,23,34,.74);
    box-shadow: 0 14px 45px rgba(0,0,0,.24);
    margin-bottom: 15px;
}

.ak-brand {
    display:flex;
    align-items:center;
    gap:14px;
}

.ak-logo {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:22px;
    background:linear-gradient(135deg,#00e5ff,#00ff88);
    color:#041014;
    box-shadow: 0 0 28px rgba(0,229,255,.22);
}

.ak-title {
    margin:0;
    font-size: 21px;
    font-weight: 800;
}

.ak-sub {
    margin:2px 0 0;
    opacity:.55;
    font-size:11px;
}

.ak-online {
    padding:7px 12px;
    border-radius:999px;
    font-size:10px;
    font-weight:800;
    border:1px solid rgba(0,255,136,.24);
    background:rgba(0,255,136,.07);
    color:#00ff88;
}

.card {
    padding:16px;
    border-radius:16px;
    border:1px solid var(--line);
    background:var(--panel);
    box-shadow:0 10px 32px rgba(0,0,0,.18);
}

.lead-card {
    padding:18px;
    border-radius:18px;
    border:1px solid rgba(0,229,255,.13);
    background:
        linear-gradient(135deg, rgba(0,229,255,.055), rgba(0,255,136,.02)),
        var(--panel);
}

.lead-phone {
    font-family:'JetBrains Mono', monospace;
    font-size:28px;
    font-weight:800;
    letter-spacing:.5px;
    background:linear-gradient(90deg,#00e5ff,#00ff88);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
}

.queue-item {
    padding:11px 12px;
    border-radius:12px;
    border:1px solid rgba(255,255,255,.06);
    background:rgba(255,255,255,.025);
    margin-bottom:8px;
}

.queue-selected {
    border-color:rgba(0,229,255,.38);
    background:linear-gradient(135deg, rgba(0,229,255,.10), rgba(0,255,136,.05));
}

.venda-card {
    padding:15px;
    border-radius:15px;
    border:1px solid rgba(255,171,0,.22);
    background:linear-gradient(135deg, rgba(255,171,0,.08), rgba(255,109,0,.05));
    margin-bottom:10px;
}

.status-pill {
    display:inline-block;
    padding:4px 8px;
    border-radius:999px;
    font-size:10px;
    font-weight:800;
    border:1px solid rgba(255,255,255,.10);
}

.small-muted {
    opacity:.58;
    font-size:11px;
}

.section-title {
    font-size:16px;
    font-weight:800;
    margin:4px 0 12px;
}

.login-shell {
    max-width: 470px;
    margin: 8vh auto 0;
    padding: 30px;
    border-radius: 24px;
    border: 1px solid rgba(0,255,136,.17);
    background: rgba(12,16,25,.82);
    box-shadow: 0 25px 70px rgba(0,0,0,.42);
    backdrop-filter: blur(18px);
}

.login-icon {
    width:72px;
    height:72px;
    margin:0 auto 16px;
    display:flex;
    align-items:center;
    justify-content:center;
    border-radius:20px;
    background:linear-gradient(135deg,#00e5ff,#00ff88);
    color:#041014;
    font-size:32px;
}

[data-testid="stDataFrame"] {
    border-radius: 14px;
    overflow: hidden;
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# UTILITÁRIOS
# ============================================================
def clean_text(value) -> str:
    return "" if value is None else str(value).strip()


def normalize_digits(value) -> str:
    return re.sub(r"\D+", "", clean_text(value))


def phone_display(value) -> str:
    d = normalize_digits(value)
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return d or "Sem telefone"


def calculate_ddd(phone) -> str:
    d = normalize_digits(phone)
    return d[:2] if len(d) >= 10 else ""


def now_str() -> str:
    return datetime.now().strftime("%d/%m %H:%M")


def now_full() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def status_label(status) -> str:
    return STATUS_LABELS.get(status, clean_text(status) or "Pendente")


def bank_emoji(bank) -> str:
    key = clean_text(bank).upper()
    return BANCO_EMOJI.get(key, BANCO_EMOJI["DEFAULT"])


def safe_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def default_lead(lead, idx=0):
    if not isinstance(lead, dict):
        lead = {}

    telefone = normalize_digits(lead.get("telefone", lead.get("telefone1", "")))
    nome = clean_text(lead.get("nome", lead.get("name", ""))) or f"Lead {idx + 1}"
    banco = clean_text(lead.get("banco", lead.get("bank", ""))).upper() or "NÃO INFORMADO"

    result = dict(lead)
    result["id"] = clean_text(lead.get("id")) or f"lead_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{idx}"
    result["nome"] = nome
    result["banco"] = banco
    result["telefone"] = telefone
    result["ddd"] = clean_text(lead.get("ddd")) or calculate_ddd(telefone)
    result["status"] = clean_text(lead.get("status")) or "pendente"
    if result["status"] not in STATUS_LABELS:
        result["status"] = "pendente"
    result["tentativas"] = safe_int(lead.get("tentativas"), 0)
    result["ultima"] = clean_text(lead.get("ultima")) or "Nunca"
    result["notas_cliente"] = clean_text(lead.get("notas_cliente"))
    result["observacao"] = clean_text(lead.get("observacao"))
    result["lote"] = clean_text(lead.get("lote"))
    result["retorno_hora"] = clean_text(lead.get("retorno_hora"))
    result["arquivado_motivo"] = clean_text(lead.get("arquivado_motivo"))
    result["historico"] = lead.get("historico") if isinstance(lead.get("historico"), list) else []
    return result


def migrate_data(data):
    if not isinstance(data, dict):
        data = {}
    leads_raw = data.get("leads", [])
    leads = [default_lead(item, i) for i, item in enumerate(leads_raw if isinstance(leads_raw, list) else [])]
    blocklist = set(clean_text(x) for x in (data.get("bloqueados") or []))
    lotes = data.get("lotes") if isinstance(data.get("lotes"), list) else []
    nao_perturbe = data.get("nao_perturbe") if isinstance(data.get("nao_perturbe"), list) else []
    meta_diaria = safe_int(data.get("meta_diaria"), 20)
    excluidos = data.get("excluidos") if isinstance(data.get("excluidos"), list) else []
    excluidos = [default_lead(x, i) for i, x in enumerate(excluidos)]
    return leads, blocklist, lotes, nao_perturbe, meta_diaria, excluidos


# ============================================================
# PERSISTÊNCIA LOCAL / GITHUB
# ============================================================
try:
    GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN")
    GITHUB_REPO = st.secrets.get("GITHUB_REPO")
    APP_PASSWORD = st.secrets.get("APP_PASSWORD", "1234")
except Exception:
    GITHUB_TOKEN = None
    GITHUB_REPO = None
    APP_PASSWORD = "1234"

GITHUB_API = (
    f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
    if GITHUB_REPO and GITHUB_TOKEN
    else None
)


def load_json_local():
    if not os.path.exists(LOCAL_FILE):
        return {}
    try:
        with open(LOCAL_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}


def carregar_dados():
    if not GITHUB_API:
        return migrate_data(load_json_local())

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

    try:
        response = requests.get(GITHUB_API, headers=headers, timeout=15)
        if response.status_code == 404:
            return migrate_data({})
        response.raise_for_status()

        content = response.json()
        sha = content.get("sha")
        encoded = content.get("content", "")
        if not encoded:
            return migrate_data({})

        raw = base64.b64decode(encoded).decode("utf-8")
        data = json.loads(raw)
        st.session_state["_gh_sha"] = sha
        return migrate_data(data)

    except (requests.RequestException, ValueError, json.JSONDecodeError):
        return migrate_data(load_json_local())


def salvar_dados():
    payload = {
        "leads": st.session_state.get("leads", []),
        "bloqueados": sorted(st.session_state.get("blocklist", set())),
        "lotes": st.session_state.get("lotes", []),
        "nao_perturbe": st.session_state.get("nao_perturbe", []),
        "meta_diaria": safe_int(st.session_state.get("meta_diaria", 20), 20),
        "excluidos": st.session_state.get("excluidos", []),
        "atualizado_em": now_full(),
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2)

    if not GITHUB_API:
        try:
            with open(LOCAL_FILE, "w", encoding="utf-8") as file:
                file.write(text)
            return True
        except OSError as exc:
            st.error(f"Falha ao salvar localmente: {exc}")
            return False

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    body = {
        "message": f"A&K Discadora {now_full()}",
        "content": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
    }
    if st.session_state.get("_gh_sha"):
        body["sha"] = st.session_state["_gh_sha"]

    try:
        response = requests.put(GITHUB_API, headers=headers, json=body, timeout=20)
        if response.status_code not in (200, 201):
            st.error(f"GitHub recusou o salvamento ({response.status_code}).")
            return False

        result = response.json()
        st.session_state["_gh_sha"] = result.get("content", {}).get("sha")
        with open(LOCAL_FILE, "w", encoding="utf-8") as file:
            file.write(text)
        return True

    except (requests.RequestException, OSError, ValueError) as exc:
        try:
            with open(LOCAL_FILE, "w", encoding="utf-8") as file:
                file.write(text)
        except OSError:
            pass
        st.warning(f"GitHub indisponível; cópia local preservada. {exc}")
        return False


# ============================================================
# LOGIN
# ============================================================
def checar_login():
    if st.session_state.get("logado"):
        return True

    st.markdown(
        """
        <div class="login-shell">
            <div class="login-icon">📞</div>
            <h1 style="text-align:center;margin:0;font-size:28px;">Discadora Eletrônica <span style="color:#00ff88;">A&K</span></h1>
            <p style="text-align:center;opacity:.55;font-size:12px;letter-spacing:1.7px;text-transform:uppercase;">
                Gestão inteligente de leads
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        _, center, _ = st.columns([1, 2, 1])
        with center:
            senha = st.text_input(
                "Senha",
                type="password",
                placeholder="Digite sua senha",
                key="senha_login",
            )
            if st.button("🚀 Acessar sistema", type="primary", width='stretch'):
                if senha == str(APP_PASSWORD):
                    st.session_state.logado = True
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
    return False


if GITHUB_TOKEN:
    if not checar_login():
        st.stop()


# ============================================================
# SESSION STATE
# ============================================================
if "leads" not in st.session_state:
    (
        st.session_state.leads,
        st.session_state.blocklist,
        st.session_state.lotes,
        st.session_state.nao_perturbe,
        st.session_state.meta_diaria,
        st.session_state.excluidos,
    ) = carregar_dados()

if "meta_diaria" not in st.session_state:
    st.session_state.meta_diaria = 20
if "excluidos" not in st.session_state:
    st.session_state.excluidos = []
if "atendimento_ativo" not in st.session_state:
    st.session_state.atendimento_ativo = False
if "selected_id" not in st.session_state:
    st.session_state.selected_id = None
if "busca_global" not in st.session_state:
    st.session_state.busca_global = ""
if "filtro_banco" not in st.session_state:
    st.session_state.filtro_banco = "TODOS"
if "filtro_status" not in st.session_state:
    st.session_state.filtro_status = "PENDENTES"
if "filtro_ddd" not in st.session_state:
    st.session_state.filtro_ddd = "TODOS"
if "ordenar_por" not in st.session_state:
    st.session_state.ordenar_por = "NUNCA LIGADOS PRIMEIRO"
if "somente_nunca" not in st.session_state:
    st.session_state.somente_nunca = False

st.session_state.leads = [
    default_lead(lead, i) for i, lead in enumerate(st.session_state.leads)
]


# ============================================================
# OPERAÇÕES DE NEGÓCIO
# ============================================================
def get_lead(lead_id):
    return next(
        (lead for lead in st.session_state.leads if lead.get("id") == lead_id),
        None,
    )


def registrar_historico(lead, acao, texto=""):
    history = lead.get("historico")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "data": now_full(),
            "acao": acao,
            "texto": clean_text(texto),
        }
    )
    lead["historico"] = history[-100:]


def atualizar_lead(lead, status, obs="", extra=None):
    if status != "arquivado":
        lead["tentativas"] = safe_int(lead.get("tentativas"), 0) + 1

    lead["status"] = status
    lead["ultima"] = now_str()
    lead["observacao"] = clean_text(obs)
    if extra:
        lead.update(extra)

    registrar_historico(lead, status, obs)
    salvar_dados()

    if status == "pendente":
        st.session_state.selected_id = lead.get("id")
    else:
        pendentes = [
            x for x in st.session_state.leads
            if x.get("status") == "pendente"
        ]
        pendentes.sort(
            key=lambda x: (
                0 if x.get("ultima") == "Nunca" else 1,
                safe_int(x.get("tentativas"), 0),
                x.get("nome", "").lower(),
            )
        )
        st.session_state.selected_id = pendentes[0]["id"] if pendentes else None

    st.session_state.atendimento_ativo = False
    st.rerun()


def filtrar_lista(status_filtro):
    lista = []

    for lead in st.session_state.leads:
        status = lead.get("status", "pendente")

        status_ok = True
        if status_filtro != "TODOS":
            mapping = {
                "PENDENTES": {"pendente"},
                "ATENDIDOS": {"atendido"},
                "NÃO ATENDEU": {"nao_atendeu"},
                "RETORNOS": {"retorno_futuro"},
                "VENDAS": {"venda_finalizada"},
                "ARQUIVADOS": {"arquivado"},
            }
            status_ok = status in mapping.get(status_filtro, set())

        if not status_ok:
            continue

        if st.session_state.get("somente_nunca", False):
            if not (status == "pendente" and lead.get("ultima") == "Nunca"):
                continue

        bank = clean_text(lead.get("banco")).upper()
        if st.session_state.filtro_banco != "TODOS" and bank != st.session_state.filtro_banco:
            continue

        if st.session_state.filtro_ddd != "TODOS" and lead.get("ddd", "") != st.session_state.filtro_ddd:
            continue

        search = clean_text(st.session_state.busca_global).lower()
        if search:
            haystack = " ".join(
                [
                    clean_text(lead.get("nome")),
                    clean_text(lead.get("banco")),
                    normalize_digits(lead.get("telefone")),
                    clean_text(lead.get("observacao")),
                    clean_text(lead.get("notas_cliente")),
                    clean_text(lead.get("lote")),
                ]
            ).lower()
            if search not in haystack:
                continue

        if lead.get("id") in st.session_state.blocklist:
            continue

        lista.append(lead)

    order = st.session_state.ordenar_por
    if order == "NUNCA LIGADOS PRIMEIRO":
        lista.sort(
            key=lambda x: (
                0 if x.get("ultima") == "Nunca" else 1,
                safe_int(x.get("tentativas"), 0),
                x.get("nome", "").lower(),
            )
        )
    elif order == "MENOS TENTATIVAS":
        lista.sort(key=lambda x: (safe_int(x.get("tentativas")), x.get("nome", "").lower()))
    elif order == "NOME A-Z":
        lista.sort(key=lambda x: x.get("nome", "").lower())
    elif order == "MAIS RECENTES":
        lista.sort(key=lambda x: x.get("ultima", ""), reverse=True)

    return lista


# ============================================================
# KPIs
# ============================================================
total = len(st.session_state.leads)
pendentes = sum(x.get("status") == "pendente" for x in st.session_state.leads)
nunca = sum(
    x.get("status") == "pendente" and x.get("ultima") == "Nunca"
    for x in st.session_state.leads
)
vendas = sum(x.get("status") == "venda_finalizada" for x in st.session_state.leads)
vendas_hoje = sum(
    x.get("status") == "venda_finalizada"
    and datetime.now().strftime("%d/%m") in x.get("ultima", "")
    for x in st.session_state.leads
)
retornos = sum(x.get("status") == "retorno_futuro" for x in st.session_state.leads)
arquivados = sum(x.get("status") == "arquivado" for x in st.session_state.leads)
atendidos = sum(x.get("status") == "atendido" for x in st.session_state.leads)


# ============================================================
# HEADER
# ============================================================
st.markdown(
    f"""
    <div class="ak-header">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
            <div class="ak-brand">
                <div class="ak-logo">📞</div>
                <div>
                    <div class="ak-title">Discadora Eletrônica <span style="color:#00ff88;">A&K</span></div>
                    <div class="ak-sub">Painel de atendimento • v{APP_VERSION} • atualizado {now_str()}</div>
                </div>
            </div>
            <div class="ak-online">● ONLINE • {total} LEADS</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

def _kpi_button(container, label, value, filtro=None, somente_nunca=False):
    with container:
        if st.button(f"{label}\n{value}", key=f"kpi_{label}", width="stretch"):
            st.session_state.filtro_status = filtro or "TODOS"
            st.session_state.somente_nunca = somente_nunca
            st.session_state.selected_id = None
            st.rerun()

m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
_kpi_button(m1, "Total", total, "TODOS")
_kpi_button(m2, "Pendentes", pendentes, "PENDENTES")
_kpi_button(m3, "Nunca ligados", nunca, "PENDENTES", True)
_kpi_button(m4, "Atendidos", atendidos, "ATENDIDOS")
_kpi_button(m5, "Vendas", vendas, "VENDAS")
_kpi_button(m6, "Retornos", retornos, "RETORNOS")
_kpi_button(m7, "Arquivados", arquivados, "ARQUIVADOS")


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown(
        """
        <div class="card" style="margin-bottom:12px;">
            <b>📞 A&K Discadora</b><br>
            <span class="small-muted">Gestão de leads e follow-up</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.session_state.busca_global = st.text_input(
        "Busca",
        value=st.session_state.busca_global,
        placeholder="Nome, banco, telefone, lote...",
    )

    bank_values = sorted(
        {
            clean_text(lead.get("banco")).upper()
            for lead in st.session_state.leads
            if clean_text(lead.get("banco"))
        }
    )
    ddd_values = sorted(
        {
            clean_text(lead.get("ddd"))
            for lead in st.session_state.leads
            if clean_text(lead.get("ddd"))
        }
    )

    st.session_state.filtro_banco = st.selectbox(
        "🏦 Banco",
        ["TODOS"] + bank_values,
        index=(
            ["TODOS"] + bank_values
        ).index(st.session_state.filtro_banco)
        if st.session_state.filtro_banco in ["TODOS"] + bank_values
        else 0,
    )

    st.session_state.filtro_status = st.selectbox(
        "📊 Status",
        [
            "PENDENTES",
            "ATENDIDOS",
            "NÃO ATENDEU",
            "RETORNOS",
            "VENDAS",
            "ARQUIVADOS",
            "TODOS",
        ],
        index=[
            "PENDENTES",
            "ATENDIDOS",
            "NÃO ATENDEU",
            "RETORNOS",
            "VENDAS",
            "ARQUIVADOS",
            "TODOS",
        ].index(st.session_state.filtro_status)
        if st.session_state.filtro_status in {
            "PENDENTES",
            "ATENDIDOS",
            "NÃO ATENDEU",
            "RETORNOS",
            "VENDAS",
            "ARQUIVADOS",
            "TODOS",
        }
        else 0,
    )

    st.session_state.filtro_ddd = st.selectbox(
        "📍 DDD",
        ["TODOS"] + ddd_values,
        index=(
            ["TODOS"] + ddd_values
        ).index(st.session_state.filtro_ddd)
        if st.session_state.filtro_ddd in ["TODOS"] + ddd_values
        else 0,
    )

    st.session_state.ordenar_por = st.selectbox(
        "↕ Ordenar",
        [
            "NUNCA LIGADOS PRIMEIRO",
            "MENOS TENTATIVAS",
            "NOME A-Z",
            "MAIS RECENTES",
        ],
    )

    if st.button("🧹 Limpar filtros", width='stretch'):
        st.session_state.busca_global = ""
        st.session_state.filtro_banco = "TODOS"
        st.session_state.filtro_status = "PENDENTES"
        st.session_state.filtro_ddd = "TODOS"
        st.session_state.ordenar_por = "NUNCA LIGADOS PRIMEIRO"
        st.session_state.somente_nunca = False
        st.session_state.selected_id = None
        st.rerun()

    st.divider()

    st.number_input(
        "🎯 Meta diária de vendas",
        min_value=1,
        max_value=1000,
        value=safe_int(st.session_state.meta_diaria, 20),
        key="meta_diaria",
    )

    target = safe_int(st.session_state.meta_diaria, 20)
    progress = min(vendas_hoje / target, 1.0) if target else 0.0
    st.progress(progress, text=f"Meta hoje: {vendas_hoje}/{target}")

    if st.button("💾 Salvar agora", width='stretch'):
        if salvar_dados():
            st.success("Dados salvos.")

    if GITHUB_API:
        st.caption("☁ Sincronização GitHub ativa")
    else:
        st.caption(f"💾 Armazenamento local: {LOCAL_FILE}")


# ============================================================
# ABAS
# ============================================================
tab_disc, tab_ret, tab_vendas, tab_arq, tab_exc, tab_lotes, tab_rel = st.tabs(
    [
        "🎯 Discador",
        "⏰ Retornos",
        "💰 Vendas",
        "📁 Arquivados",
        "🗑 Excluídos",
        "📦 Lotes / Importar",
        "📊 Relatórios",
    ]
)


# ============================================================
# DISCADOR
# ============================================================
with tab_disc:
    lista = filtrar_lista(st.session_state.filtro_status)

    col_lista, col_det = st.columns([0.95, 2.05], gap="large")

    with col_lista:
        st.markdown(
            f"""
            <div class="card" style="margin-bottom:12px;">
                <div class="section-title">📋 Fila {html.escape(st.session_state.filtro_status)} <span class="small-muted">({len(lista)})</span></div>
                <div class="small-muted">Clique em um lead para abrir o painel de atendimento.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not lista:
            st.info("Nenhum lead encontrado com os filtros atuais.")
        else:
            for lead in lista[:80]:
                selected = lead.get("id") == st.session_state.selected_id
                label = (
                    f"{'👉' if selected else '○'} "
                    f"{clean_text(lead.get('nome'))[:22]} • "
                    f"{bank_emoji(lead.get('banco'))} "
                    f"{clean_text(lead.get('banco'))[:10]} • "
                    f"T{safe_int(lead.get('tentativas'))}"
                )
                if st.button(
                    label,
                    key=f"lead_{lead['id']}",
                    width='stretch',
                    type="primary" if selected else "secondary",
                ):
                    st.session_state.selected_id = lead["id"]
                    st.session_state.atendimento_ativo = False
                    st.rerun()

    with col_det:
        sel = get_lead(st.session_state.selected_id)

        if not sel:
            st.markdown(
                """
                <div class="lead-card" style="text-align:center;padding:62px 20px;">
                    <div style="font-size:54px;">📞</div>
                    <div style="font-size:18px;font-weight:800;">Selecione um lead</div>
                    <div class="small-muted">A fila ao lado mostra quem está pronto para atendimento.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            status = sel.get("status", "pendente")
            color = STATUS_COLORS.get(status, "#00e5ff")

            st.markdown(
                f"""
                <div class="lead-card">
                    <div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start;">
                        <div>
                            <div style="font-size:18px;font-weight:800;">
                                {bank_emoji(sel.get("banco"))} {html.escape(sel.get("nome",""))}
                            </div>
                            <div class="small-muted">🏦 {html.escape(sel.get("banco",""))} • Lote: {html.escape(sel.get("lote","") or "Sem lote")}</div>
                        </div>
                        <span class="status-pill" style="color:{color};">{html.escape(status_label(status).upper())}</span>
                    </div>
                    <div class="lead-phone" style="margin:14px 0 4px;">{html.escape(phone_display(sel.get("telefone")))}</div>
                    <div class="small-muted">DDD {html.escape(sel.get("ddd") or "—")} • Tentativas {safe_int(sel.get("tentativas"))} • Último contato {html.escape(sel.get("ultima","Nunca"))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if not st.session_state.atendimento_ativo:
                if st.button("📞 Iniciar atendimento", key=f"start_{sel['id']}", width='stretch', type="primary"):
                    st.session_state.atendimento_ativo = True
                    sel["tentativas"] = safe_int(sel.get("tentativas"), 0) + 1
                    sel["ultima"] = now_str()
                    registrar_historico(sel, "atendimento_iniciado", "Atendimento iniciado")
                    salvar_dados()
                    st.rerun()
            else:
                st.success("🟢 Atendimento em andamento")

            url_tel = f"tel:{normalize_digits(sel.get('telefone'))}"
            wa_digits = normalize_digits(sel.get('telefone'))
            if len(wa_digits) in (10, 11):
                wa_url = f"https://wa.me/55{wa_digits}"
            else:
                wa_url = ""

            c_call, c_wa, c_next = st.columns(3)
            with c_call:
                st.link_button("📱 Ligar", url_tel, width='stretch')
            with c_wa:
                if wa_url:
                    st.link_button("💬 WhatsApp", wa_url, width='stretch')
                else:
                    st.button("💬 WhatsApp indisponível", disabled=True, width='stretch')
            with c_next:
                if st.button("➡ Próximo pendente", width='stretch'):
                    pending = [
                        x for x in st.session_state.leads
                        if x.get("status") == "pendente" and x.get("id") != sel.get("id")
                    ]
                    pending.sort(
                        key=lambda x: (
                            0 if x.get("ultima") == "Nunca" else 1,
                            safe_int(x.get("tentativas")),
                            x.get("nome", "").lower(),
                        )
                    )
                    st.session_state.selected_id = pending[0]["id"] if pending else None
                    st.rerun()

            st.markdown("#### Ações de atendimento")
            a1, a2, a3, a4, a5 = st.columns(5)

            with a1:
                if st.button("✅ Atendeu", key=f"att_{sel['id']}", width='stretch', type="primary"):
                    atualizar_lead(sel, "atendido", "Atendeu")

            with a2:
                if st.button("📬 Não atendeu", key=f"no_{sel['id']}", width='stretch'):
                    atualizar_lead(sel, "nao_atendeu", "Não atendeu")

            with a3:
                if st.button("💰 Venda", key=f"sale_{sel['id']}", width='stretch'):
                    atualizar_lead(sel, "venda_finalizada", "Venda concluída")

            with a4:
                if st.button("📁 Arquivar", key=f"archive_{sel['id']}", width='stretch'):
                    atualizar_lead(sel, "arquivado", "Arquivado")

            with a5:
                if st.button("↩ Reabrir", key=f"reopen_{sel['id']}", width='stretch'):
                    atualizar_lead(sel, "pendente", "Retornado para pendentes")

            st.markdown("#### 🕒 Agendar retorno")
            ret_date = st.date_input(
                "Data do retorno",
                value=datetime.now().date() + timedelta(days=1),
                min_value=datetime.now().date(),
                key=f"ret_date_{sel['id']}",
            )
            ret_time = st.time_input(
                "Horário do retorno",
                value=datetime.now().time().replace(second=0, microsecond=0),
                key=f"ret_time_{sel['id']}",
            )
            r1, r2 = st.columns([2, 1])
            with r1:
                retorno_obs = st.text_input(
                    "Observação do retorno",
                    value=clean_text(sel.get("retorno_hora")),
                    key=f"ret_obs_{sel['id']}",
                )
            with r2:
                if st.button("⏰ Agendar retorno", width='stretch'):
                    when = datetime.combine(ret_date, ret_time).strftime("%d/%m/%Y %H:%M")
                    atualizar_lead(
                        sel,
                        "retorno_futuro",
                        retorno_obs or f"Retorno agendado para {when}",
                        {"retorno_hora": when},
                    )

            st.markdown("#### 📝 Cliente")
            notes = st.text_area(
                "Notas",
                value=clean_text(sel.get("notas_cliente")),
                height=100,
                key=f"notes_{sel['id']}",
                label_visibility="collapsed",
                placeholder="Anote perfil, interesse, objeções, observações...",
            )
            n1, n2 = st.columns(2)
            with n1:
                if st.button("💾 Salvar observações", width='stretch'):
                    sel["notas_cliente"] = notes
                    registrar_historico(sel, "nota", "Observação atualizada")
                    if salvar_dados():
                        st.success("Observações salvas.")
            with n2:
                if st.button("🗑 Remover da base", width='stretch'):
                    removed = dict(sel)
                    removed["excluido_em"] = now_full()
                    removed["excluido_motivo"] = "Excluído manualmente da base"
                    st.session_state.excluidos.append(removed)
                    st.session_state.leads = [
                        x for x in st.session_state.leads
                        if x.get("id") != sel.get("id")
                    ]
                    st.session_state.selected_id = None
                    st.session_state.atendimento_ativo = False
                    salvar_dados()
                    st.rerun()

            with st.expander("📜 Histórico do lead"):
                history = sel.get("historico") or []
                if not history:
                    st.caption("Sem histórico.")
                else:
                    for item in reversed(history[-20:]):
                        st.markdown(
                            f"**{html.escape(clean_text(item.get('data')))}** — "
                            f"{html.escape(status_label(item.get('acao','')))}  \n"
                            f"{html.escape(clean_text(item.get('texto')))}"
                        )


# ============================================================
# RETORNOS
# ============================================================
with tab_ret:
    retorno_list = [x for x in st.session_state.leads if x.get("status") == "retorno_futuro"]

    if not retorno_list:
        st.info("Nenhum retorno agendado.")
    else:
        retorno_list.sort(key=lambda x: x.get("retorno_hora", "99/99/9999"))
        for lead in retorno_list:
            with st.container():
                st.markdown(
                    f"""
                    <div class="card">
                        <div style="font-size:15px;font-weight:800;">⏰ {html.escape(lead.get("nome",""))}</div>
                        <div class="small-muted">{bank_emoji(lead.get("banco"))} {html.escape(lead.get("banco",""))} • {html.escape(phone_display(lead.get("telefone")))}</div>
                        <div style="margin-top:8px;"><b>Retorno:</b> {html.escape(lead.get("retorno_hora") or "Sem horário")}</div>
                        <div class="small-muted">{html.escape(lead.get("observacao") or "")}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("📥 Voltar para pendentes", key=f"ret_pending_{lead['id']}", width='stretch', type="primary"):
                        atualizar_lead(lead, "pendente", "Retorno convertido em pendente", {"retorno_hora": ""})
                with c2:
                    if st.button("📞 Abrir no discador", key=f"ret_open_{lead['id']}", width='stretch'):
                        st.session_state.selected_id = lead["id"]
                        st.session_state.filtro_status = "RETORNOS"
                        st.rerun()
                with c3:
                    if st.button("❌ Cancelar retorno", key=f"ret_cancel_{lead['id']}", width='stretch'):
                        atualizar_lead(lead, "arquivado", "Retorno cancelado", {"retorno_hora": ""})


# ============================================================
# VENDAS
# ============================================================
with tab_vendas:
    st.markdown(
        f"""
        <div class="venda-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div style="font-size:16px;font-weight:800;">💰 Central de Vendas</div>
                    <div class="small-muted">{vendas} vendas totais • {vendas_hoje} hoje</div>
                </div>
                <div style="font-size:28px;font-weight:900;color:#ffab00;">{vendas}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    sale_list = [x for x in st.session_state.leads if x.get("status") == "venda_finalizada"]
    sale_banks = sorted({x.get("banco", "") for x in sale_list if x.get("banco")})
    sale_filter = st.selectbox("Filtrar vendas por banco", ["TODOS"] + sale_banks, key="sale_filter")

    if sale_filter != "TODOS":
        sale_list = [x for x in sale_list if x.get("banco") == sale_filter]

    if not sale_list:
        st.info("Nenhuma venda encontrada.")
    else:
        for lead in sale_list[:100]:
            st.markdown(
                f"""
                <div class="venda-card">
                    <div style="font-weight:800;">💰 {html.escape(lead.get("nome",""))} • {bank_emoji(lead.get("banco"))} {html.escape(lead.get("banco",""))}</div>
                    <div class="small-muted">📱 {html.escape(phone_display(lead.get("telefone")))} • {html.escape(lead.get("ultima",""))} • T{safe_int(lead.get("tentativas"))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔄 Voltar para pendentes", key=f"sale_back_{lead['id']}", width='stretch'):
                    atualizar_lead(lead, "pendente", "Venda revertida para pendente")
            with c2:
                if st.button("📞 Abrir lead", key=f"sale_open_{lead['id']}", width='stretch'):
                    st.session_state.selected_id = lead["id"]
                    st.rerun()


# ============================================================
# ARQUIVADOS
# ============================================================
with tab_arq:
    archive_list = [x for x in st.session_state.leads if x.get("status") == "arquivado"]

    if not archive_list:
        st.info("Nenhum lead arquivado.")
    else:
        st.caption(f"{len(archive_list)} lead(s) arquivado(s)")
        for lead in archive_list[:100]:
            st.markdown(
                f"""
                <div class="card" style="margin-bottom:8px;">
                    <div style="font-weight:800;">📁 {html.escape(lead.get("nome",""))} • {html.escape(lead.get("banco",""))}</div>
                    <div class="small-muted">{html.escape(phone_display(lead.get("telefone")))} • Motivo: {html.escape(lead.get("arquivado_motivo") or lead.get("observacao") or "—")}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔄 Voltar", key=f"arch_back_{lead['id']}", width='stretch', type="primary"):
                    atualizar_lead(lead, "pendente", "Lead reaberto")
            with c2:
                if st.button("🗑 Excluir definitivamente", key=f"arch_delete_{lead['id']}", width='stretch'):
                    st.session_state.leads = [x for x in st.session_state.leads if x.get("id") != lead.get("id")]
                    salvar_dados()
                    st.rerun()


# ============================================================
# EXCLUÍDOS
# ============================================================
with tab_exc:
    st.markdown(f"<div class='card'><div class='section-title'>🗑 Contatos excluídos</div><div class='small-muted'>{len(st.session_state.excluidos)} contato(s) protegidos contra reimportação.</div></div>", unsafe_allow_html=True)
    if not st.session_state.excluidos:
        st.info("Nenhum contato excluído.")
    else:
        busca_exc = st.text_input("Pesquisar excluídos", placeholder="Nome ou telefone", key="busca_excluidos")
        for lead in [x for x in st.session_state.excluidos if busca_exc.lower() in f"{x.get('nome','')} {x.get('telefone','')}".lower()][:200]:
            st.markdown(f"<div class='card' style='margin-bottom:8px;'><b>🗑 {html.escape(lead.get('nome',''))}</b> • {html.escape(lead.get('banco',''))}<br><span class='small-muted'>📱 {html.escape(phone_display(lead.get('telefone')))} • Excluído em {html.escape(lead.get('excluido_em','—'))}</span></div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("♻ Restaurar", key=f"restore_{lead['id']}", width='stretch', type="primary"):
                    restored = dict(lead)
                    restored.pop("excluido_em", None)
                    restored.pop("excluido_motivo", None)
                    restored["status"] = "pendente"
                    st.session_state.leads.append(default_lead(restored, len(st.session_state.leads)))
                    st.session_state.excluidos = [x for x in st.session_state.excluidos if x.get("id") != lead.get("id")]
                    salvar_dados()
                    st.rerun()
            with c2:
                if st.button("❌ Apagar histórico", key=f"purge_{lead['id']}", width='stretch'):
                    st.session_state.excluidos = [x for x in st.session_state.excluidos if x.get("id") != lead.get("id")]
                    salvar_dados()
                    st.rerun()


# LOTES / IMPORTAÇÃO
# ============================================================
with tab_lotes:
    left, right = st.columns([1.1, 1.4], gap="large")

    with left:
        st.markdown('<div class="card"><div class="section-title">📦 Criar lote</div></div>', unsafe_allow_html=True)
        lote_nome = st.text_input("Nome do lote", placeholder="Ex.: INSS Setembro 01")
        lote_desc = st.text_input("Descrição", placeholder="Origem, convênio, campanha...")
        if st.button("➕ Criar lote", width='stretch', type="primary"):
            if not lote_nome.strip():
                st.warning("Informe um nome para o lote.")
            else:
                st.session_state.lotes.append(
                    {
                        "id": f"lote_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                        "nome": lote_nome.strip(),
                        "descricao": lote_desc.strip(),
                        "criado_em": now_full(),
                        "quantidade": 0,
                    }
                )
                if salvar_dados():
                    st.success(f"Lote '{lote_nome}' criado.")
                    st.rerun()

        st.markdown("#### Lotes cadastrados")
        if not st.session_state.lotes:
            st.caption("Nenhum lote cadastrado.")
        else:
            for lote in st.session_state.lotes:
                st.markdown(
                    f"""
                    <div class="card" style="margin-bottom:8px;">
                        <b>📦 {html.escape(clean_text(lote.get("nome")))}</b><br>
                        <span class="small-muted">{html.escape(clean_text(lote.get("descricao")))} • Criado {html.escape(clean_text(lote.get("criado_em")))}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with right:
        st.markdown('<div class="card"><div class="section-title">⬆ Importar leads</div><div class="small-muted">CSV ou Excel. Colunas aceitas: nome, telefone, banco, lote.</div></div>', unsafe_allow_html=True)

        selected_lote = st.selectbox(
            "Associar ao lote",
            ["SEM LOTE"] + [clean_text(x.get("nome")) for x in st.session_state.lotes],
        )
        uploaded = st.file_uploader(
            "Escolha uma ou várias planilhas",
            type=["csv", "txt", "tsv", "xlsx", "xls", "xlsm", "xltx", "xltm", "xlsb", "ods", "fods"],
            accept_multiple_files=True,
            key="lead_uploader",
        )

        if uploaded:
            try:
                engines = {
                    ".xlsx": "openpyxl", ".xlsm": "openpyxl", ".xltx": "openpyxl", ".xltm": "openpyxl",
                    ".xls": "xlrd", ".xlsb": "pyxlsb", ".ods": "odf", ".fods": "odf",
                }

                def read_uploaded_file(file):
                    ext = os.path.splitext(file.name.lower())[1]
                    file.seek(0)
                    if ext in {".csv", ".txt", ".tsv"}:
                        last_error = None
                        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
                            try:
                                file.seek(0)
                                return pd.read_csv(
                                    file,
                                    sep="\t" if ext == ".tsv" else None,
                                    engine="python",
                                    dtype=str,
                                    encoding=enc,
                                ).fillna("")
                            except Exception as exc:
                                last_error = exc
                        raise ValueError(f"arquivo de texto nao reconhecido: {last_error}")
                    
                    if ext not in engines:
                        raise ValueError(f"formato nao suportado: {ext or 'sem extensao'}")
                    
                    try:
                        file.seek(0)
                        return pd.read_excel(file, engine=engines[ext], dtype=str).fillna("")
                    except ImportError as ie:
                        try:
                            file.seek(0)
                            return pd.read_excel(file, dtype=str).fillna("")
                        except Exception:
                            raise ValueError(f"dependencia faltando para {ext}: {ie}. Adicione '{engines[ext]}' no requirements.txt")
                    except Exception:
                        file.seek(0)
                        return pd.read_excel(file, dtype=str).fillna("")

                dataframes = []
                erros = []
                for file in uploaded:
                    try:
                        df_file = read_uploaded_file(file)
                        dataframes.append((file.name, df_file))
                    except Exception as exc:
                        erros.append(f"{file.name}: {exc}")

                if dataframes:
                    total_linhas = sum(len(df) for _, df in dataframes)
                    st.success(f"{len(dataframes)} arquivo(s) lido(s) • {total_linhas} linha(s) encontradas.")
                    for fname, df_file in dataframes:
                        with st.expander(f"📄 {fname} • {len(df_file)} linha(s)", expanded=len(dataframes) == 1):
                            st.dataframe(df_file.head(20), width="stretch", hide_index=True)

                    if erros:
                        st.warning("Alguns arquivos não puderam ser lidos: " + " | ".join(erros))

                    if st.button("✅ Importar todos os arquivos", key="import_leads_multi", width="stretch", type="primary"):
                        imported = []
                        total_duplicados = 0
                        total_sem_dados = 0

                        for fname, preview_df in dataframes:
                            normalized_columns = {clean_text(col).lower(): col for col in preview_df.columns}

                            def col_value(row, keys):
                                for key in keys:
                                    original = normalized_columns.get(key)
                                    if original is not None:
                                        return clean_text(row.get(original))
                                return ""

                            for idx, (_, row) in enumerate(preview_df.iterrows()):
                                nome = col_value(row, ["nome", "name", "cliente", "nome_cliente"])
                                telefone = col_value(row, ["telefone", "phone", "celular", "whatsapp", "telefone1", "telefone 1"])
                                banco = col_value(row, ["banco", "bank", "instituicao", "instituição"])
                                lote = col_value(row, ["lote"])
                                if not nome and not telefone:
                                    total_sem_dados += 1
                                    continue
                                imported.append(default_lead({
                                    "nome": nome or f"Lead importado {len(imported) + 1}",
                                    "telefone": telefone,
                                    "banco": banco or "NÃO INFORMADO",
                                    "lote": lote or ("" if selected_lote == "SEM LOTE" else selected_lote),
                                    "status": "pendente",
                                }, len(imported)))

                        existing_phones = {normalize_digits(x.get("telefone")) for x in st.session_state.leads if normalize_digits(x.get("telefone"))}
                        deleted_phones = {normalize_digits(x.get("telefone")) for x in st.session_state.excluidos if normalize_digits(x.get("telefone"))}
                        seen = set()
                        unique_imported = []
                        bloqueados = 0
                        for item in imported:
                            phone = normalize_digits(item.get("telefone"))
                            if phone and phone in deleted_phones:
                                bloqueados += 1
                                continue
                            if phone and (phone in existing_phones or phone in seen):
                                total_duplicados += 1
                                continue
                            if phone:
                                seen.add(phone)
                            unique_imported.append(item)

                        st.session_state.leads.extend(unique_imported)
                        salvar_dados()
                        st.success(f"{len(unique_imported)} lead(s) importado(s) de {len(dataframes)} arquivo(s). {total_duplicados} duplicado(s), {bloqueados} excluído(s) bloqueado(s), {total_sem_dados} linha(s) sem nome/telefone ignorada(s).")
                        st.rerun()
                else:
                    st.error("❌ Nenhum dos arquivos enviados pôde ser lido. Verifique se o arquivo não está corrompido e se o requirements.txt tem: openpyxl, xlrd, pyxlsb, odfpy")
                    if erros:
                        st.code("\n".join(erros))
            except Exception as exc:
                st.error(f"Não foi possível ler os arquivos: {exc}")

    st.divider()
    st.markdown("#### ➕ Cadastro manual")
    c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1])
    with c1:
        new_name = st.text_input("Nome", key="manual_name")
    with c2:
        new_phone = st.text_input("Telefone", key="manual_phone")
    with c3:
        new_bank = st.text_input("Banco", key="manual_bank")
    with c4:
        new_lote = st.text_input("Lote", key="manual_lote")

    if st.button("➕ Adicionar lead", key="manual_add", width='stretch'):
        if not new_name.strip() and not new_phone.strip():
            st.warning("Preencha pelo menos nome ou telefone.")
        else:
            new_lead = default_lead(
                {
                    "nome": new_name,
                    "telefone": new_phone,
                    "banco": new_bank,
                    "lote": new_lote,
                    "status": "pendente",
                },
                len(st.session_state.leads),
            )
            st.session_state.leads.append(new_lead)
            salvar_dados()
            st.success("Lead adicionado.")
            st.rerun()


# ============================================================
# RELATÓRIOS
# ============================================================
with tab_rel:
    df = pd.DataFrame(st.session_state.leads)

    if df.empty:
        st.info("Sem dados para gerar relatório.")
    else:
        r1, r2, r3 = st.columns(3)

        status_counts = df["status"].map(status_label).value_counts()
        bank_counts = df["banco"].fillna("NÃO INFORMADO").value_counts().head(10)

        with r1:
            st.markdown('<div class="card"><div class="section-title">📊 Distribuição por status</div></div>', unsafe_allow_html=True)
            st.bar_chart(status_counts)

        with r2:
            st.markdown('<div class="card"><div class="section-title">🏦 Leads por banco</div></div>', unsafe_allow_html=True)
            st.bar_chart(bank_counts)

        with r3:
            total_non_archived = max(total - arquivados, 0)
            conversion = (vendas / total_non_archived * 100) if total_non_archived else 0
            st.metric("Conversão para venda", f"{conversion:.1f}%")
            st.metric("Vendas hoje", vendas_hoje)
            st.metric("Meta diária", safe_int(st.session_state.meta_diaria, 20))

        export_cols = [
            col for col in [
                "id", "nome", "telefone", "ddd", "banco", "status",
                "tentativas", "ultima", "retorno_hora", "lote",
                "observacao", "notas_cliente"
            ] if col in df.columns
        ]
        export_df = df[export_cols].copy()
        csv = export_df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "⬇ Baixar relatório CSV",
            data=csv,
            file_name=f"AK_Discadora_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            width='stretch',
            type="primary",
        )

        with st.expander("🔎 Visualizar base completa"):
            st.dataframe(export_df, width="stretch", hide_index=True)


# ============================================================
# RODAPÉ / STATUS
# ============================================================
st.markdown(
    f"""
    <div style="text-align:center;opacity:.38;font-size:10px;padding:24px 0 6px;">
        A&K Discadora • v{APP_VERSION} • {len(st.session_state.leads)} leads • sincronização {'GitHub + local' if GITHUB_API else 'local'}
    </div>
    """,
    unsafe_allow_html=True,
)
