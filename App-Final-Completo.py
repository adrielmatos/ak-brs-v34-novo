import streamlit as st
import pandas as pd
import hashlib
import base64
import json
import requests
from datetime import datetime, timedelta
from io import BytesIO
import urllib.parse
from collections import Counter

st.set_page_config(page_title="A&K BRS", layout="wide", page_icon="📱")

# =========================================================
# CONFIGURAÇÃO GITHUB (usado como banco de dados)
# =========================================================
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]  # ex: "adrielmatos/ak-brs-v34-novo"
except Exception:
    st.error("Configuração ausente. Vá em Settings > Secrets no Streamlit Cloud e adicione GITHUB_TOKEN e GITHUB_REPO.")
    st.stop()

GITHUB_PATH = "brs_dados.json"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

# =========================================================
# LOGIN SIMPLES
# =========================================================
def checar_login():
    if st.session_state.get("logado"):
        return True
    st.markdown("## 🔒 A&K BRS")
    senha = st.text_input("Senha de acesso", type="password")
    if st.button("Entrar", type="primary"):
        senha_correta = st.secrets.get("APP_PASSWORD", None)
        if senha_correta is None:
            st.error("APP_PASSWORD não configurada nos Secrets.")
        elif senha == senha_correta:
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False

if not checar_login():
    st.stop()

# =========================================================
# PERSISTÊNCIA VIA GITHUB (leads + pausas + bloqueados num único JSON)
# =========================================================
def carregar_dados():
    r = requests.get(GITHUB_API, headers=HEADERS)
    if r.status_code == 200:
        conteudo = r.json()
        st.session_state["_gh_sha"] = conteudo["sha"]
        dados = json.loads(base64.b64decode(conteudo["content"]).decode("utf-8"))
        return dados.get("leads", []), dados.get("pausas", []), set(dados.get("bloqueados", []))
    elif r.status_code == 404:
        st.session_state["_gh_sha"] = None
        return [], [], set()
    else:
        st.error(f"Erro ao ler dados do GitHub: {r.status_code} — verifique o token e o nome do repositório.")
        return [], [], set()

def salvar_dados():
    payload = {
        "leads": st.session_state.leads,
        "pausas": st.session_state.pausas,
        "bloqueados": list(st.session_state.blocklist),
    }
    conteudo_str = json.dumps(payload, ensure_ascii=False, indent=2)
    conteudo_b64 = base64.b64encode(conteudo_str.encode("utf-8")).decode("utf-8")
    body = {
        "message": f"Atualização automática {datetime.now().strftime('%d/%m %H:%M:%S')}",
        "content": conteudo_b64,
    }
    if st.session_state.get("_gh_sha"):
        body["sha"] = st.session_state["_gh_sha"]
    r = requests.put(GITHUB_API, headers=HEADERS, json=body)
    if r.status_code in (200, 201):
        st.session_state["_gh_sha"] = r.json()["content"]["sha"]
    else:
        st.warning(f"Não consegui salvar no GitHub agora (código {r.status_code}). Tente de novo.")

# =========================================================
# ESTADO INICIAL
# =========================================================
if "leads" not in st.session_state:
    leads, pausas, blocklist = carregar_dados()
    st.session_state.leads = leads
    st.session_state.pausas = pausas
    st.session_state.blocklist = blocklist
    st.session_state.selected_id = None
    st.session_state.auto_next = True
    st.session_state.call_start = {}
    st.session_state.filtro_banco = "TODOS"
    st.session_state.filtro_status = "PENDENTES"
    st.session_state.em_pausa = None
    st.session_state.pausa_inicio = None
    st.session_state.modo_foco = False
    st.session_state.preview_df = None

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
    vendas_por_banco = {}
    for l in st.session_state.leads:
        if l["status"] == "venda_finalizada":
            vendas_por_banco[l["banco"]] = vendas_por_banco.get(l["banco"], 0) + 1

    def score(l):
        tent = l.get("tentativas", 0) * 10
        nunca = 0 if l.get("ultima") == "Nunca" else 5
        banco_bonus = -2 if vendas_por_banco.get(l["banco"], 0) >= max(vendas_por_banco.values(), default=0) and vendas_por_banco else 0
        return tent + nunca + banco_bonus

    pend_sorted = sorted(pend, key=score)
    if not atual_id:
        return pend_sorted[0]["id"]
    ids = [l["id"] for l in pend_sorted]
    if atual_id not in ids:
        return pend_sorted[0]["id"]
    idx = ids.index(atual_id)
    if idx + 1 < len(ids):
        return ids[idx + 1]
    return pend_sorted[0]["id"] if len(pend_sorted) > 1 else None

def melhor_horario():
    horas = []
    for l in st.session_state.leads:
        for h in l.get("historico", []) or []:
            if h.get("acao") in ("atendido", "venda_finalizada"):
                try:
                    hora = int(h["data"].split(" ")[1].split(":")[0])
                    horas.append(hora)
                except Exception:
                    continue
    if len(horas) < 5:
        return None
    faixa = Counter([h - (h % 2) for h in horas])
    melhor = faixa.most_common(1)[0][0]
    return f"{melhor:02d}h-{melhor+2:02d}h"

def retornos_hoje():
    hoje = datetime.now().strftime("%d/%m/%Y")
    return len([l for l in st.session_state.leads if l.get("status") == "retorno_futuro" and l.get("retorno_data") == hoje])

# =========================================================
# LEITURA ROBUSTA DE PLANILHA
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
    raise ValueError("Não consegui identificar o formato do CSV automaticamente (encoding/separador).")

def montar_novos_leads(df, existentes, bloqueados):
    df.columns = [str(c).upper().strip() for c in df.columns]
    col_nome = next((c for c in df.columns if "NOME" in c), df.columns[0])
    col_cpf = next((c for c in df.columns if "CPF" in c), None)
    col_tel = next((c for c in df.columns if "TELEFONE" in c or c == "TEL" or "CEL" in c), None)
    col_banco = next((c for c in df.columns if "BANCO" in c), None)

    novos, ignorados_tel, ignorados_bloq, ignorados_dup = [], 0, 0, 0
    for idx, row in df.iterrows():
        cpf = str(row.get(col_cpf, "")).strip() if col_cpf else f"semcpf{idx}"
        tel_raw = str(row.get(col_tel, "")).strip() if col_tel else ""
        tel = "".join(filter(str.isdigit, tel_raw))
        if not tel or len(tel) < 8:
            ignorados_tel += 1
            continue
        if tel in bloqueados:
            ignorados_bloq += 1
            continue
        h = hashlib.sha256(f"{cpf}{tel}".encode()).hexdigest()[:12]
        if h in existentes:
            ignorados_dup += 1
            continue
        existentes.add(h)
        novos.append({
            "id": h, "nome": str(row.get(col_nome, f"Lead {idx}"))[:40], "cpf": cpf,
            "telefone": tel, "banco": str(row.get(col_banco, "PAN")).upper()[:20] if col_banco else "PAN",
            "produto": "FGTS", "status": "pendente", "tentativas": 0, "ultima": "Nunca",
            "duracao_seg": 0, "duracao_txt": "00:00", "historico": [], "tabulacao": "",
            "observacao": "", "canal": "chip", "custo_estimado": 0.0, "retorno_data": None
        })
    return novos, ignorados_tel, ignorados_bloq, ignorados_dup

# =========================================================
# ESTILO
# =========================================================
st.markdown("""
<style>
.mini-dash {position:fixed;bottom:12px;right:12px;background:rgba(255,255,255,0.95);
border:1px solid #e0e0e0;border-radius:12px;padding:8px 12px;box-shadow:0 4px 12px rgba(0,0,0,0.12);
z-index:9999;font-size:12px;}
.foco-overlay {background:#f8fafc;border:2px solid #00c853;border-radius:16px;padding:20px;}
.alerta {padding:10px 14px;border-radius:10px;margin-bottom:8px;font-size:13px;}
.alerta-retorno {background:#fff4e5;color:#8a5300;}
.alerta-horario {background:#e6f7ee;color:#0a6b3d;}
</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER
# =========================================================
st.markdown("## 📱 A&K BRS")
col_h1, col_h2, col_h3, col_h4 = st.columns([2.5, 1, 1, 1])
with col_h1:
    total = len(st.session_state.leads)
    pend = len([l for l in st.session_state.leads if l["status"] == "pendente"])
    st.caption(f"📱 {total} | 📥 {pend} pendentes")
with col_h2:
    st.session_state.auto_next = st.checkbox("⏭️ Auto", value=True)
with col_h3:
    if st.button("🧠 Próximo Inteligente", use_container_width=True, type="primary"):
        nxt = proximo_inteligente(st.session_state.selected_id)
        if nxt:
            st.session_state.selected_id = nxt
            st.session_state.modo_foco = False
            st.rerun()
with col_h4:
    if st.button("🔄 Sair", use_container_width=True):
        st.session_state.logado = False
        st.rerun()

ret = retornos_hoje()
if ret > 0:
    st.markdown(f'<div class="alerta alerta-retorno">⏰ {ret} retorno(s) agendado(s) para hoje</div>', unsafe_allow_html=True)
mh = melhor_horario()
if mh:
    st.markdown(f'<div class="alerta alerta-horario">📈 Seu melhor horário de conversão: {mh}</div>', unsafe_allow_html=True)

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown("### 🎯 Filtros")
    banco_list = ["TODOS"] + sorted(list(set([l["banco"] for l in st.session_state.leads]))) if st.session_state.leads else ["TODOS"]
    st.session_state.filtro_banco = st.selectbox("🏦 Banco", banco_list)
    st.session_state.filtro_status = st.selectbox("📊 Status", ["PENDENTES", "ATENDIDOS", "NÃO ATENDEU", "RETORNOS", "VENDAS", "TODOS"])
    busca = st.text_input("🔍 Buscar", placeholder="Nome, banco...")
    st.markdown("---")
    st.markdown("### ⏸️ Pausas")
    em_pausa = st.session_state.em_pausa is not None
    if not em_pausa:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("☕ Almoço", use_container_width=True):
                st.session_state.em_pausa = "Almoço"; st.session_state.pausa_inicio = datetime.now(); st.rerun()
            if st.button("📚 Feedback", use_container_width=True):
                st.session_state.em_pausa = "Feedback"; st.session_state.pausa_inicio = datetime.now(); st.rerun()
        with c2:
            if st.button("🚻 Banheiro", use_container_width=True):
                st.session_state.em_pausa = "Banheiro"; st.session_state.pausa_inicio = datetime.now(); st.rerun()
            if st.button("💤 Pausa", use_container_width=True):
                st.session_state.em_pausa = "Pausa"; st.session_state.pausa_inicio = datetime.now(); st.rerun()
        st.success("🟢 Disponível")
    else:
        decorrido = (datetime.now() - st.session_state.pausa_inicio).total_seconds()
        st.warning(f"⏸️ {st.session_state.em_pausa} {formatar_tempo(decorrido)}")
        if st.button("▶️ Voltar", type="primary", use_container_width=True):
            fim = datetime.now(); duracao = (fim - st.session_state.pausa_inicio).total_seconds()
            st.session_state.pausas.append({"tipo": st.session_state.em_pausa, "inicio": st.session_state.pausa_inicio.strftime("%d/%m %H:%M:%S"),
                      "fim": fim.strftime("%d/%m %H:%M:%S"), "duracao_seg": int(duracao), "duracao_txt": formatar_tempo(duracao)})
            salvar_dados()
            st.session_state.em_pausa = None; st.session_state.pausa_inicio = None; st.rerun()

modo_foco_ativo = st.session_state.modo_foco and st.session_state.selected_id in st.session_state.call_start if st.session_state.selected_id else False

# =========================================================
# IMPORTAÇÃO
# =========================================================
if not st.session_state.leads:
    st.info("📥 Suba uma ou várias planilhas de uma vez — aceita .csv, .xlsx e .xls")
    arquivos = st.file_uploader("Planilha(s)", type=["csv", "xlsx", "xls"], key="import_file", accept_multiple_files=True)
    if arquivos and st.session_state.preview_df is None:
        dfs, erros = [], []
        for arq in arquivos:
            try:
                df_arq = ler_planilha(arq)
                df_arq.columns = [str(c).upper().strip() for c in df_arq.columns]
                dfs.append(df_arq)
            except Exception as e:
                erros.append(f"{arq.name}: {e}")
        if erros:
            st.error("Alguns arquivos não puderam ser lidos: " + " | ".join(erros))
        if dfs:
            st.session_state.preview_df = pd.concat(dfs, ignore_index=True)
            st.caption(f"{len(dfs)} planilha(s) combinada(s), {len(st.session_state.preview_df)} linhas no total")

    if st.session_state.preview_df is not None:
        st.markdown("#### 👀 Prévia (10 primeiras linhas)")
        st.dataframe(st.session_state.preview_df.head(10), use_container_width=True)
        if st.button("✅ Confirmar importação", type="primary"):
            existentes = set([l["id"] for l in st.session_state.leads])
            novos, ig_tel, ig_bloq, ig_dup = montar_novos_leads(
                st.session_state.preview_df.copy(), existentes, st.session_state.blocklist
            )
            st.session_state.leads.extend(novos)
            salvar_dados()
            st.session_state.preview_df = None
            msg = f"✅ {len(novos)} importados."
            if ig_tel: msg += f" {ig_tel} ignorados (telefone inválido)."
            if ig_bloq: msg += f" {ig_bloq} ignorados (bloqueados)."
            if ig_dup: msg += f" {ig_dup} ignorados (duplicados)."
            st.success(msg)
            if novos:
                st.session_state.selected_id = novos[0]["id"]
            st.rerun()
else:
    lista = []
    for l in st.session_state.leads:
        if st.session_state.filtro_banco != "TODOS" and l["banco"] != st.session_state.filtro_banco:
            continue
        if st.session_state.filtro_status == "PENDENTES" and l["status"] != "pendente":
            continue
        if st.session_state.filtro_status == "ATENDIDOS" and l["status"] != "atendido":
            continue
        if st.session_state.filtro_status == "NÃO ATENDEU" and l["status"] != "nao_atendeu":
            continue
        if st.session_state.filtro_status == "RETORNOS" and l["status"] != "retorno_futuro":
            continue
        if st.session_state.filtro_status == "VENDAS" and l["status"] != "venda_finalizada":
            continue
        if busca and busca.lower() not in l["nome"].lower() and busca.lower() not in l["banco"].lower():
            continue
        lista.append(l)

    def registrar_evento(sel, status_final, obs_pronta, retorno_data=None):
        fim = datetime.now(); dur = 0
        if sel["id"] in st.session_state.call_start:
            dur = (fim - st.session_state.call_start[sel["id"]]).total_seconds()
            del st.session_state.call_start[sel["id"]]
        custo = (dur / 60) * 0.15
        sel["status"] = status_final
        sel["tentativas"] = sel.get("tentativas", 0) + 1
        sel["ultima"] = fim.strftime("%d/%m %H:%M")
        sel["duracao_seg"] = int(dur)
        sel["duracao_txt"] = formatar_tempo(dur)
        sel["observacao"] = obs_pronta
        sel["tabulacao"] = obs_pronta[:30]
        sel["custo_estimado"] = sel.get("custo_estimado", 0) + custo
        sel["retorno_data"] = retorno_data
        historico = sel.get("historico") or []
        historico.append({"data": fim.strftime("%d/%m %H:%M:%S"), "acao": status_final, "tempo": formatar_tempo(dur), "tab": obs_pronta})
        sel["historico"] = historico
        salvar_dados()
        st.session_state.modo_foco = False
        if st.session_state.auto_next:
            st.session_state.selected_id = proximo_inteligente(sel["id"])
        st.rerun()

    if modo_foco_ativo:
        sel = next((l for l in st.session_state.leads if l["id"] == st.session_state.selected_id), None)
        if sel:
            st.markdown('<div class="foco-overlay">', unsafe_allow_html=True)
            st.markdown(f"## 🎯 MODO FOCO | {sel['nome']} | 🏦 {sel['banco']}")
            decorrido = (datetime.now() - st.session_state.call_start[sel["id"]]).total_seconds()
            st.markdown(f"### ⏱️ {formatar_tempo(decorrido)} | 📱 {sel['telefone']}")
            st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:22px;border-radius:14px;text-align:center;font-weight:900;text-decoration:none;font-size:24px">📱 {sel["telefone"]} • EM LIGAÇÃO</a>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("✅ Interessado", use_container_width=True, type="primary", key=f"foco_at1_{sel['id']}"):
                    registrar_evento(sel, "atendido", "Atendeu - interessado")
            with c2:
                if st.button("🔴 Caixa", use_container_width=True, key=f"foco_cx_{sel['id']}"):
                    registrar_evento(sel, "nao_atendeu", "Caixa postal")
            with c3:
                if st.button("📵 Desligado", use_container_width=True, key=f"foco_des_{sel['id']}"):
                    registrar_evento(sel, "nao_atendeu", "Desligado")
            with c4:
                if st.button("💰 Venda!", use_container_width=True, key=f"foco_vd_{sel['id']}"):
                    st.balloons(); registrar_evento(sel, "venda_finalizada", "Venda FGTS")
            if st.button("🔙 Sair do Foco", use_container_width=True, key=f"foco_sair_{sel['id']}"):
                st.session_state.modo_foco = False; st.rerun()
    else:
        col_lista, col_atend = st.columns([1, 2.2])
        with col_lista:
            st.markdown(f"#### 📋 Fila: {st.session_state.filtro_banco} ({len(lista)})")
            for lead in lista[:80]:
                bloqueado = lead["telefone"] in st.session_state.blocklist
                dot = "🚫" if bloqueado else {"pendente": "⚪", "atendido": "🟢", "nao_atendeu": "🔴", "retorno_futuro": "🟠", "venda_finalizada": "💰"}[lead["status"]]
                is_sel = lead["id"] == st.session_state.selected_id
                tent_txt = f" T{lead.get('tentativas', 0)}"
                if st.button(f"{'👉' if is_sel else ''}{dot} {lead['nome'][:14]} • {lead['banco']}{tent_txt}", key=f"list_{lead['id']}", use_container_width=True, type="primary" if is_sel else "secondary"):
                    st.session_state.selected_id = lead["id"]; st.session_state.modo_foco = False; st.rerun()
        with col_atend:
            if not st.session_state.selected_id:
                st.info("👈 Selecione cliente ou 🧠 Próximo Inteligente")
            else:
                sel = next((l for l in st.session_state.leads if l["id"] == st.session_state.selected_id), None)
                if sel:
                    bloqueado = sel["telefone"] in st.session_state.blocklist
                    st.markdown(f"### 👤 {sel['nome']} | 🏦 {sel['banco']} | 📱 {sel['telefone']}")
                    if bloqueado:
                        st.error("🚫 Este número está na blocklist — não contatar.")
                    else:
                        em_ligacao = sel["id"] in st.session_state.call_start
                        em_pausa = st.session_state.em_pausa is not None
                        if em_pausa:
                            st.error(f"⏸️ Em pausa: {st.session_state.em_pausa}")
                        elif not em_ligacao:
                            col_d1, col_d2, col_d3 = st.columns([1.5, 1, 1])
                            with col_d1:
                                if st.button(f"▶️ LIGAR CHIP • {sel['telefone']}", key=f"discar_{sel['id']}", type="primary", use_container_width=True):
                                    st.session_state.call_start[sel["id"]] = datetime.now(); st.session_state.modo_foco = True; st.rerun()
                            with col_d2:
                                msg_map = {
                                    "PAN": f"Olá {sel['nome']}, A&K sobre FGTS PAN liberado. Explico 1 min?",
                                    "BMG": f"Olá {sel['nome']}, BMG liberou FGTS. Quer saber valor?",
                                    "C6": f"Olá {sel['nome']}, C6 liberou FGTS. Explico rapidinho?"
                                }
                                msg = msg_map.get(sel["banco"], f"Olá {sel['nome']}, A&K FGTS {sel['banco']} liberado")
                                msg_enc = urllib.parse.quote(msg)
                                st.markdown(f'<a href="https://wa.me/55{sel["telefone"]}?text={msg_enc}" target="_blank" style="display:block;background:#25D366;color:#fff;padding:12px;border-radius:8px;text-align:center;font-weight:700;text-decoration:none">💬 Zap</a>', unsafe_allow_html=True)
                            with col_d3:
                                if st.button("🚫 Não ligar mais", key=f"bloq_{sel['id']}", use_container_width=True):
                                    st.session_state.blocklist.add(sel["telefone"])
                                    salvar_dados()
                                    st.rerun()
                        else:
                            decorrido = (datetime.now() - st.session_state.call_start[sel["id"]]).total_seconds()
                            st.warning(f"📱 EM LIGAÇÃO: {formatar_tempo(decorrido)}")
                            st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:18px;border-radius:12px;text-align:center;font-weight:900;text-decoration:none;font-size:20px">📱 {sel["telefone"]} • ⏱️ {formatar_tempo(decorrido)}</a>', unsafe_allow_html=True)
                            if st.button("🔍 Ver Modo Foco grande", key=f"ver_foco_{sel['id']}", type="primary", use_container_width=True):
                                st.session_state.modo_foco = True; st.rerun()

                        st.markdown("#### ⚡ Tabulação 1 clique")
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            if st.button("✅ Atendeu", use_container_width=True, type="primary", key=f"fin_at_{sel['id']}"):
                                registrar_evento(sel, "atendido", "Atendeu - interessado")
                        with c2:
                            if st.button("🔴 Caixa", use_container_width=True, key=f"fin_cx_{sel['id']}"):
                                registrar_evento(sel, "nao_atendeu", "Caixa postal")
                        with c3:
                            if st.button("📵 Deslig", use_container_width=True, key=f"fin_des_{sel['id']}"):
                                registrar_evento(sel, "nao_atendeu", "Desligado")
                        with c4:
                            if st.button("💰 Venda", use_container_width=True, key=f"fin_ve_{sel['id']}"):
                                st.balloons(); registrar_evento(sel, "venda_finalizada", "Venda FGTS")
                        c5, c6, c7 = st.columns(3)
                        with c5:
                            if st.button("🤔 Sem interesse", use_container_width=True, key=f"fin_si_{sel['id']}"):
                                registrar_evento(sel, "atendido", "Sem interesse no momento")
                        with c6:
                            if st.button("📅 Retorno amanhã", use_container_width=True, key=f"fin_rt_{sel['id']}"):
                                amanha = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
                                registrar_evento(sel, "retorno_futuro", "Retornar amanhã 14h", retorno_data=amanha)
                        with c7:
                            if st.button("❌ Erro número", use_container_width=True, key=f"fin_er_{sel['id']}"):
                                registrar_evento(sel, "nao_atendeu", "Número errado")

# =========================================================
# MINI DASH + EXPORTAR
# =========================================================
if st.session_state.leads:
    df_all = pd.DataFrame(st.session_state.leads)
    pend = len(df_all[df_all["status"] == "pendente"])
    vendas = len(df_all[df_all["status"] == "venda_finalizada"])
    tempo_total = df_all["duracao_seg"].sum()
    tmo = tempo_total / max(len(df_all[df_all["status"] != "pendente"]), 1)
    st.markdown(f'<div class="mini-dash">📥 {pend} | ⏱️ TMO {formatar_tempo(tmo)} | 💰 {vendas} vendas</div>', unsafe_allow_html=True)

st.markdown("---")
with st.expander("📥 Exportar CSV"):
    if st.session_state.leads:
        df_all = pd.DataFrame(st.session_state.leads)
        csv = df_all.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Baixar CSV", csv, file_name=f"BRS_{datetime.now().strftime('%d%m%Y_%H%M')}.csv", mime="text/csv", use_container_width=True)
