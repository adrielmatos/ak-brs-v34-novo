import streamlit as st
import pandas as pd
import hashlib
import base64
import json
import requests
from datetime import datetime, timedelta, date, time
from io import BytesIO
import urllib.parse
import os
from collections import Counter

st.set_page_config(page_title="Discadora Eletrônica A&K", layout="wide", page_icon="📞")

BANCO_EMOJI = {"PAN": "🟢", "SAFRA": "🟠", "BMG": "🔵", "C6": "⚫", "ITAU": "🔷", "ITAÚ": "🔷", "OLE": "🟡", "DEFAULT": "⚪"}

# =========================================================
# CSS GLOBAL — corrige espaço em branco no topo (login precisando rolar)
# =========================================================
st.markdown("""
<style>
header {visibility: hidden;}
.block-container {padding-top: 1.2rem; padding-bottom: 1rem;}
</style>
""", unsafe_allow_html=True)

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]
except Exception:
    GITHUB_TOKEN = None
    GITHUB_REPO = None

GITHUB_PATH = "brs_dados.json"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}" if GITHUB_REPO else None

# =========================================================
# LOGIN — compactado, sem padding excessivo, sem precisar rolar
# =========================================================
def checar_login():
    if st.session_state.get("logado"):
        return True
    st.markdown(
        "<div style='text-align:center;padding:10px 0 6px;'><h2 style='margin:0;'>Discadora Eletrônica<br><span style='color:#00e5ff;'>A&K</span></h2></div>",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1, 3, 1])
    with c2:
        senha = st.text_input("Senha", type="password", key="senha_login")
        if st.button("Entrar", type="primary", use_container_width=True, key="btn_login"):
            senha_correta = st.secrets.get("APP_PASSWORD", None) if GITHUB_TOKEN else "1234"
            if senha_correta is None:
                st.error("APP_PASSWORD não configurada nos Secrets.")
            elif senha == senha_correta:
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Senha incorreta")
    return False

if GITHUB_TOKEN:
    if not checar_login():
        st.stop()

# =========================================================
# PERSISTÊNCIA — com retry em conflito e erro visível
# =========================================================
def carregar_dados():
    if not GITHUB_API or not GITHUB_TOKEN:
        if os.path.exists("brs_dados_local.json"):
            try:
                with open("brs_dados_local.json", "r", encoding="utf-8") as f:
                    d = json.load(f)
                return d.get("leads", []), d.get("pausas", []), set(d.get("bloqueados", [])), d.get("lotes", []), d.get("nao_perturbe", []), d.get("meta_diaria", 20)
            except Exception:
                return [], [], set(), [], [], 20
        return [], [], set(), [], [], 20
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(GITHUB_API, headers=headers)
        if r.status_code == 200:
            conteudo = r.json()
            st.session_state["_gh_sha"] = conteudo["sha"]
            dados = json.loads(base64.b64decode(conteudo["content"]).decode("utf-8"))
            return dados.get("leads", []), dados.get("pausas", []), set(dados.get("bloqueados", [])), dados.get("lotes", []), dados.get("nao_perturbe", []), dados.get("meta_diaria", 20)
        elif r.status_code == 404:
            st.session_state["_gh_sha"] = None
            return [], [], set(), [], [], 20
        else:
            st.error(f"Erro ao carregar do GitHub (código {r.status_code}): {r.text[:200]}")
            return [], [], set(), [], [], 20
    except Exception as e:
        st.error(f"Erro GitHub: {e}")
        return [], [], set(), [], [], 20

def _commit(payload_str):
    conteudo_b64 = base64.b64encode(payload_str.encode("utf-8")).decode("utf-8")
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    body = {"message": f"A&K {datetime.now().strftime('%d/%m %H:%M:%S')}", "content": conteudo_b64}
    if st.session_state.get("_gh_sha"):
        body["sha"] = st.session_state["_gh_sha"]
    return requests.put(GITHUB_API, headers=headers, json=body)

def salvar_dados():
    payload = {
        "leads": st.session_state.leads,
        "pausas": st.session_state.pausas,
        "bloqueados": list(st.session_state.blocklist),
        "lotes": st.session_state.lotes,
        "nao_perturbe": st.session_state.nao_perturbe,
        "meta_diaria": st.session_state.get("meta_diaria", 20),
    }
    conteudo_str = json.dumps(payload, ensure_ascii=False, indent=2)

    if not GITHUB_API or not GITHUB_TOKEN:
        try:
            with open("brs_dados_local.json", "w", encoding="utf-8") as f:
                f.write(conteudo_str)
        except Exception as e:
            st.warning(f"Erro ao salvar localmente: {e}")
        return

    try:
        with st.spinner("Salvando..."):
            r = _commit(conteudo_str)
            if r.status_code in (200, 201):
                st.session_state["_gh_sha"] = r.json()["content"]["sha"]
                return
            if r.status_code == 409:
                # Conflito: outra sessão salvou primeiro. Busca o sha mais recente e tenta de novo, uma vez.
                headers = {"Authorization": f"token {GITHUB_TOKEN}"}
                r2 = requests.get(GITHUB_API, headers=headers)
                if r2.status_code == 200:
                    st.session_state["_gh_sha"] = r2.json()["sha"]
                    r3 = _commit(conteudo_str)
                    if r3.status_code in (200, 201):
                        st.session_state["_gh_sha"] = r3.json()["content"]["sha"]
                        return
                st.error("Conflito ao salvar (provavelmente outra aba/sessão aberta ao mesmo tempo). Feche abas duplicadas do app e tente de novo.")
            else:
                st.error(f"Não consegui salvar no GitHub (código {r.status_code}): {r.text[:200]}")
    except Exception as e:
        st.warning(f"Erro salvar: {e}")

# =========================================================
# ESTADO INICIAL
# =========================================================
if "leads" not in st.session_state:
    leads, pausas, blocklist, lotes, nao_perturbe, meta_diaria = carregar_dados()
    for l in leads:
        l.setdefault("notas_cliente", "")
        l.setdefault("arquivado_motivo", "")
        l.setdefault("retorno_hora", "")
        l.setdefault("ddd", "")
        l.setdefault("lote", "")
    st.session_state.leads = leads
    st.session_state.pausas = pausas
    st.session_state.blocklist = blocklist
    st.session_state.lotes = lotes
    st.session_state.nao_perturbe = nao_perturbe
    st.session_state.meta_diaria = meta_diaria
    st.session_state.selected_id = None
    st.session_state.filtro_banco = "TODOS"
    st.session_state.filtro_status = "PENDENTES"
    st.session_state.filtro_ddd = "TODOS"
    st.session_state.busca_global = ""
    st.session_state.ordenar_por = "NUNCA LIGADOS PRIMEIRO"
    st.session_state.preview_lotes = None

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================
def formatar_tempo(seg):
    if not seg or seg <= 0:
        return "00:00"
    m = int(seg // 60); s = int(seg % 60)
    if m >= 60:
        h = m // 60; m = m % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def proximo_inteligente(atual_id=None):
    pend = [l for l in st.session_state.leads if l["status"] == "pendente"]
    if not pend:
        return None
    pend_sorted = sorted(pend, key=lambda x: (0 if x.get("ultima") == "Nunca" else 1, x.get("tentativas", 0)))
    if not atual_id:
        return pend_sorted[0]["id"]
    ids = [l["id"] for l in pend_sorted]
    if atual_id not in ids:
        return pend_sorted[0]["id"]
    idx = ids.index(atual_id)
    if idx + 1 < len(ids):
        return ids[idx + 1]
    return pend_sorted[0]["id"] if len(pend_sorted) > 1 else None

def tabular(sel, status_final, obs_pronta, extra=None):
    """Função única de tabulação — garante que todo evento entra no histórico."""
    sel["status"] = status_final
    sel["ultima"] = datetime.now().strftime("%d/%m %H:%M")
    sel["tentativas"] = sel.get("tentativas", 0) + 1
    sel["observacao"] = obs_pronta
    if extra:
        sel.update(extra)
    historico = sel.get("historico") or []
    historico.append({"data": datetime.now().strftime("%d/%m %H:%M:%S"), "acao": status_final, "tab": obs_pronta})
    sel["historico"] = historico
    salvar_dados()
    st.session_state.selected_id = proximo_inteligente(sel["id"])
    st.rerun()

# =========================================================
# IMPORTAÇÃO DE PLANILHA (agora implementada de verdade)
# =========================================================
def ler_planilha(up):
    nome = up.name.lower()
    if nome.endswith((".xlsx", ".xls")):
        return pd.read_excel(up)
    conteudo = up.read()
    for enc in ["utf-8", "latin1", "cp1252"]:
        for sep in [",", ";"]:
            try:
                df = pd.read_csv(BytesIO(conteudo), encoding=enc, sep=sep)
                if len(df.columns) > 1:
                    return df
            except Exception:
                continue
    raise ValueError("Não consegui identificar separador/codificação do CSV automaticamente.")

def montar_novos_leads(df, existentes, bloqueados, nome_lote):
    df.columns = [str(c).upper().strip() for c in df.columns]
    col_nome = next((c for c in df.columns if "NOME" in c), df.columns[0])
    col_cpf = next((c for c in df.columns if "CPF" in c), None)
    col_tel = next((c for c in df.columns if "TELEFONE" in c or c == "TEL" or "CEL" in c), None)
    col_banco = next((c for c in df.columns if "BANCO" in c), None)

    novos, ig_tel, ig_bloq, ig_dup = [], 0, 0, 0
    for idx, row in df.iterrows():
        cpf = str(row.get(col_cpf, "")).strip() if col_cpf else f"semcpf{idx}"
        tel_raw = str(row.get(col_tel, "")).strip() if col_tel else ""
        tel = "".join(filter(str.isdigit, tel_raw))
        if not tel or len(tel) < 8:
            ig_tel += 1
            continue
        if tel in bloqueados:
            ig_bloq += 1
            continue
        h = hashlib.sha256(f"{cpf}{tel}".encode()).hexdigest()[:12]
        if h in existentes:
            ig_dup += 1
            continue
        existentes.add(h)
        ddd = tel[:2] if len(tel) >= 10 else ""
        novos.append({
            "id": h, "nome": str(row.get(col_nome, f"Lead {idx}"))[:40], "cpf": cpf,
            "telefone": tel, "ddd": ddd,
            "banco": str(row.get(col_banco, "PAN")).upper()[:20] if col_banco else "PAN",
            "status": "pendente", "tentativas": 0, "ultima": "Nunca",
            "historico": [], "observacao": "", "notas_cliente": "", "arquivado_motivo": "",
            "retorno_data": "", "retorno_hora": "", "lote": nome_lote,
        })
    return novos, ig_tel, ig_bloq, ig_dup

# =========================================================
# HEADER + KPIs
# =========================================================
total = len(st.session_state.leads)
pend = len([l for l in st.session_state.leads if l["status"] == "pendente"])
nunca = len([l for l in st.session_state.leads if l["status"] == "pendente" and l.get("ultima") == "Nunca"])
vendas = len([l for l in st.session_state.leads if l["status"] == "venda_finalizada"])
vendas_hoje = len([l for l in st.session_state.leads if l["status"] == "venda_finalizada" and datetime.now().strftime("%d/%m") in l.get("ultima", "")])
retornos_total = len([l for l in st.session_state.leads if l["status"] == "retorno_futuro"])
arquivados = len([l for l in st.session_state.leads if l["status"] == "arquivado"])
atendidos = len([l for l in st.session_state.leads if l["status"] == "atendido"])
nao_atendeu = len([l for l in st.session_state.leads if l["status"] == "nao_atendeu"])

st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f0c29,#302b63);padding:18px 22px;border-radius:16px;color:white;margin-bottom:12px;border:1px solid rgba(0,255,136,0.15);">
<h1 style="margin:0;font-size:20px;">Discadora Eletrônica <span style="color:#00e5ff;">A&K</span></h1>
<p style="margin:0;opacity:0.6;font-size:11px;">{total} leads • {pend} pendentes • {arquivados} arquivados • {datetime.now().strftime('%d/%m %H:%M')}</p>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
with c1: st.metric("TOTAL", total, f"{atendidos}a {nao_atendeu}na")
with c2: st.metric("PENDENTES", pend)
with c3: st.metric("NUNCA", nunca)
with c4: st.metric("VENDAS", vendas)
with c5: st.metric("HOJE", vendas_hoje)
with c6: st.metric("RETORNOS", retornos_total)
with c7: st.metric("ARQUIV", arquivados)

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("### 🔍 Filtros")
    st.session_state.busca_global = st.text_input("Busca", value=st.session_state.busca_global, placeholder="Nome, banco, tel", key="busca_side")
    bancos = sorted(list(set([l["banco"] for l in st.session_state.leads]))) if st.session_state.leads else []
    st.session_state.filtro_banco = st.selectbox("Banco", ["TODOS"] + bancos, key="f_banco_side")
    st.session_state.filtro_status = st.selectbox("Status (aba Discador)", ["PENDENTES", "ATENDIDOS", "NÃO ATENDEU", "RETORNOS", "VENDAS", "ARQUIVADOS", "TODOS"], key="f_status_side")
    ddds = sorted(list(set([l.get("ddd", "") for l in st.session_state.leads if l.get("ddd")]))) if st.session_state.leads else []
    st.session_state.filtro_ddd = st.selectbox("DDD", ["TODOS"] + ddds, key="f_ddd_side")
    st.session_state.ordenar_por = st.selectbox("Ordenar", ["NUNCA LIGADOS PRIMEIRO", "MENOS TENTATIVAS", "NOME A-Z"], key="f_ord_side")
    if st.button("🧹 Limpar Filtros", use_container_width=True, key="clear_side"):
        st.session_state.filtro_banco = "TODOS"
        st.session_state.filtro_status = "PENDENTES"
        st.session_state.filtro_ddd = "TODOS"
        st.session_state.busca_global = ""
        st.session_state.selected_id = None
        st.rerun()

# =========================================================
# ABAS
# =========================================================
tab1, tab_ret, tab_lotes, tab_rel, tab_arq = st.tabs(["🎯 DISCADOR", "⏰ RETORNOS", "📦 LOTES", "📊 RELATÓRIOS", "📁 ARQUIVADOS"])

def filtrar_lista(status_filtro):
    lista = []
    for l in st.session_state.leads:
        if status_filtro == "PENDENTES" and l["status"] != "pendente": continue
        if status_filtro == "ATENDIDOS" and l["status"] != "atendido": continue
        if status_filtro == "NÃO ATENDEU" and l["status"] != "nao_atendeu": continue
        if status_filtro == "RETORNOS" and l["status"] != "retorno_futuro": continue
        if status_filtro == "VENDAS" and l["status"] != "venda_finalizada": continue
        if status_filtro == "ARQUIVADOS" and l["status"] != "arquivado": continue
        if st.session_state.filtro_banco != "TODOS" and l["banco"] != st.session_state.filtro_banco: continue
        if st.session_state.filtro_ddd != "TODOS" and l.get("ddd", "") != st.session_state.filtro_ddd: continue
        busca = st.session_state.busca_global
        if busca and busca.lower() not in l["nome"].lower() and busca.lower() not in l["banco"].lower() and busca.lower() not in l["telefone"]: continue
        lista.append(l)
    if st.session_state.ordenar_por == "NUNCA LIGADOS PRIMEIRO":
        lista = sorted(lista, key=lambda x: (0 if x.get("ultima") == "Nunca" else 1, x.get("tentativas", 0)))
    elif st.session_state.ordenar_por == "MENOS TENTATIVAS":
        lista = sorted(lista, key=lambda x: x.get("tentativas", 0))
    elif st.session_state.ordenar_por == "NOME A-Z":
        lista = sorted(lista, key=lambda x: x["nome"])
    return lista

def mostrar_detalhes_lead(sel):
    if not sel:
        return
    st.markdown(f"### {BANCO_EMOJI.get(sel['banco'], '⚪')} {sel['nome']} | 🏦 {sel['banco']} | T{sel.get('tentativas', 0)}")
    st.markdown(f"**📱 {sel['telefone']}** | CPF: {sel.get('cpf', '')} | DDD: {sel.get('ddd', '')} | Lote: {sel.get('lote', '')[:20]}")

    if sel["telefone"] in st.session_state.blocklist:
        st.error("🚫 Este número está bloqueado — não contatar.")
        if st.button("Remover do bloqueio", key=f"desbloq_{sel['id']}"):
            st.session_state.blocklist.discard(sel["telefone"])
            salvar_dados()
            st.rerun()
        return

    st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:#00ff88;color:#000;padding:12px;border-radius:8px;text-align:center;font-weight:800;text-decoration:none;">📱 LIGAR {sel["telefone"]}</a>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("☎️ Registrar tentativa", key=f"ligar_{sel['id']}", use_container_width=True):
            sel["tentativas"] = sel.get("tentativas", 0) + 1
            sel["ultima"] = datetime.now().strftime("%d/%m %H:%M")
            salvar_dados()
            st.rerun()
    with col2:
        msg = f"Olá {sel['nome']}, A&K FGTS {sel['banco']} liberado"
        msg_enc = urllib.parse.quote(msg)
        st.markdown(f'<a href="https://wa.me/55{sel["telefone"]}?text={msg_enc}" target="_blank" style="display:block;background:#25D366;color:#fff;padding:10px;border-radius:8px;text-align:center;font-weight:700;text-decoration:none">💬 Zap</a>', unsafe_allow_html=True)
    with col3:
        if st.button("🚫 Bloquear", key=f"bloq_{sel['id']}", use_container_width=True):
            st.session_state.blocklist.add(sel["telefone"])
            salvar_dados()
            st.rerun()

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("✅ Atendeu", key=f"at_{sel['id']}", use_container_width=True, type="primary"):
            tabular(sel, "atendido", "Atendeu")
    with c2:
        if st.button("📬 Caixa", key=f"cx_{sel['id']}", use_container_width=True):
            tabular(sel, "nao_atendeu", "Caixa postal")
    with c3:
        if st.button("📵 Desligado", key=f"des_{sel['id']}", use_container_width=True):
            tabular(sel, "nao_atendeu", "Desligado")
    with c4:
        if st.button("💰 Venda", key=f"vd_{sel['id']}", use_container_width=True):
            st.balloons()
            tabular(sel, "venda_finalizada", "Venda FGTS")

    c5, c6, c7 = st.columns(3)
    with c5:
        if st.button("📁 Arquivar - Já liguei", key=f"arq_{sel['id']}", use_container_width=True):
            tabular(sel, "arquivado", "Já liguei - ocultar", extra={"arquivado_motivo": "Já liguei - ocultar"})
    with c6:
        if st.button("🔄 Voltar p/ Pendentes", key=f"vol_{sel['id']}", use_container_width=True):
            sel["status"] = "pendente"
            salvar_dados()
            st.rerun()
    with c7:
        if st.button("❌ Número errado", key=f"err_{sel['id']}", use_container_width=True):
            tabular(sel, "nao_atendeu", "Número errado")

    with st.expander("📅 Agendar Retorno com Data"):
        d1, d2 = st.columns(2)
        with d1:
            data_ret = st.date_input("Data", value=date.today() + timedelta(days=1), min_value=date.today(), key=f"data_ret_{sel['id']}")
        with d2:
            hora_ret = st.time_input("Hora", value=time(14, 0), key=f"hora_ret_{sel['id']}")
        motivo = st.text_input("Motivo", key=f"motivo_{sel['id']}")
        if st.button(f"✅ Agendar {data_ret.strftime('%d/%m')} {hora_ret.strftime('%H:%M')}", key=f"conf_ret_{sel['id']}", type="primary", use_container_width=True):
            tabular(
                sel, "retorno_futuro", f"Retorno {data_ret.strftime('%d/%m/%Y')} {hora_ret.strftime('%H:%M')} {motivo}",
                extra={"retorno_data": data_ret.strftime("%d/%m/%Y"), "retorno_hora": hora_ret.strftim