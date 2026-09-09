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

st.set_page_config(page_title="Discadora Eletrônica A&K", layout="wide", page_icon="📞")

BANCO_EMOJI = {"PAN":"🟢","SAFRA":"🟠","BMG":"🔵","C6":"⚫","ITAU":"🔷","DEFAULT":"⚪"}

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]
except Exception:
    GITHUB_TOKEN = None
    GITHUB_REPO = None

GITHUB_PATH = "brs_dados.json"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}" if GITHUB_REPO else None

def checar_login():
    if st.session_state.get("logado"):
        return True
    st.markdown("<div style='text-align:center;padding:10px;'><h2>Discadora Eletrônica<br><span style='color:#00e5ff;'>A&K</span></h2></div>", unsafe_allow_html=True)
    c1,c2,c3=st.columns([1,3,1])
    with c2:
        senha=st.text_input("Senha", type="password", key="senha_login")
        if st.button("Entrar", type="primary", use_container_width=True, key="btn_login"):
            senha_correta=st.secrets.get("APP_PASSWORD",None) if GITHUB_TOKEN else "1234"
            if senha==senha_correta:
                st.session_state.logado=True
                st.rerun()
            else:
                st.error("Senha incorreta")
    return False

if GITHUB_TOKEN:
    if not checar_login():
        st.stop()

def carregar_dados():
    if not GITHUB_API or not GITHUB_TOKEN:
        if os.path.exists("brs_dados_local.json"):
            try:
                with open("brs_dados_local.json","r",encoding="utf-8") as f:
                    d=json.load(f)
                return d.get("leads",[]), set(d.get("bloqueados",[])), d.get("lotes",[]), d.get("nao_perturbe",[]), d.get("meta_diaria",20)
            except Exception:
                return [], set(), [], [], 20
        return [], set(), [], [], 20
    try:
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        r=requests.get(GITHUB_API, headers=headers)
        if r.status_code==200:
            conteudo=r.json()
            st.session_state["_gh_sha"]=conteudo["sha"]
            dados=json.loads(base64.b64decode(conteudo["content"]).decode("utf-8"))
            return dados.get("leads",[]), set(dados.get("bloqueados",[])), dados.get("lotes",[]), dados.get("nao_perturbe",[]), dados.get("meta_diaria",20)
        elif r.status_code==404:
            st.session_state["_gh_sha"]=None
            return [], set(), [], [], 20
        else:
            return [], set(), [], [], 20
    except Exception:
        return [], set(), [], [], 20

def salvar_dados():
    try:
        payload={"leads":st.session_state.leads,"bloqueados":list(st.session_state.blocklist),"lotes":st.session_state.lotes,"nao_perturbe":st.session_state.nao_perturbe,"meta_diaria":st.session_state.get("meta_diaria",20)}
        conteudo_str=json.dumps(payload, ensure_ascii=False, indent=2)
        if not GITHUB_API or not GITHUB_TOKEN:
            with open("brs_dados_local.json","w",encoding="utf-8") as f:
                f.write(conteudo_str)
            return
        conteudo_b64=base64.b64encode(conteudo_str.encode("utf-8")).decode("utf-8")
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        body={"message": f"A&K {datetime.now().strftime('%d/%m %H:%M:%S')}", "content": conteudo_b64}
        if st.session_state.get("_gh_sha"):
            body["sha"]=st.session_state["_gh_sha"]
        r=requests.put(GITHUB_API, headers=headers, json=body)
        if r.status_code in (200,201):
            st.session_state["_gh_sha"]=r.json()["content"]["sha"]
    except Exception as e:
        st.warning(f"Erro salvar: {e}")

if "leads" not in st.session_state:
    leads, blocklist, lotes, nao_perturbe, meta_diaria = carregar_dados()
    for l in leads:
        l.setdefault("notas_cliente","")
        l.setdefault("arquivado_motivo","")
        l.setdefault("retorno_hora","")
        l.setdefault("ddd", l.get("telefone","")[:2] if len(l.get("telefone",""))>=10 else "")
        l.setdefault("lote","")
        l.setdefault("tentativas",0)
        l.setdefault("ultima","Nunca")
        l.setdefault("historico",[])
    st.session_state.leads=leads
    st.session_state.blocklist=blocklist
    st.session_state.lotes=lotes
    st.session_state.nao_perturbe=nao_perturbe
    st.session_state.meta_diaria=meta_diaria
    st.session_state.selected_id=None
    st.session_state.filtro_banco="TODOS"
    st.session_state.filtro_status="PENDENTES"
    st.session_state.filtro_ddd="TODOS"
    st.session_state.busca_global=""
    st.session_state.ordenar_por="NUNCA LIGADOS PRIMEIRO"

def tabular(sel, status_final, obs):
    sel["status"]=status_final
    sel["ultima"]=datetime.now().strftime("%d/%m %H:%M")
    sel["tentativas"]=sel.get("tentativas",0)+1
    sel["observacao"]=obs
    hist=sel.get("historico") or []
    hist.append({"data":datetime.now().strftime("%d/%m %H:%M:%S"),"acao":status_final,"tab":obs})
    sel["historico"]=hist
    salvar_dados()
    st.rerun()

total=len(st.session_state.leads)
pend=len([l for l in st.session_state.leads if l["status"]=="pendente"])
arquivados=len([l for l in st.session_state.leads if l["status"]=="arquivado"])
vendas=len([l for l in st.session_state.leads if l["status"]=="venda_finalizada"])
retornos_total=len([l for l in st.session_state.leads if l["status"]=="retorno_futuro"])

st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f0c29,#302b63);padding:16px;border-radius:12px;color:white;margin-bottom:10px;">
<h1 style="margin:0;font-size:19px;">Discadora Eletrônica <span style="color:#00e5ff;">A&K</span></h1>
<p style="margin:0;opacity:0.6;font-size:11px;">{total} leads • {pend} pendentes • {arquivados} arquivados • {datetime.now().strftime('%d/%m %H:%M')}</p>
</div>
""", unsafe_allow_html=True)

c1,c2,c3,c4,c5=st.columns(5)
with c1: st.metric("TOTAL", total)
with c2: st.metric("PENDENTES", pend)
with c3: st.metric("VENDAS", vendas)
with c4: st.metric("RETORNOS", retornos_total)
with c5: st.metric("ARQUIV", arquivados)

with st.sidebar:
    st.markdown("### 🔍 Filtros")
    st.session_state.busca_global=st.text_input("Busca", value=st.session_state.busca_global, key="busca_side")
    bancos=sorted(list(set([l["banco"] for l in st.session_state.leads]))) if st.session_state.leads else []
    st.session_state.filtro_banco=st.selectbox("Banco", ["TODOS"]+bancos, key="f_banco_side")
    st.session_state.filtro_status=st.selectbox("Status", ["PENDENTES","ATENDIDOS","NÃO ATENDEU","RETORNOS","VENDAS","ARQUIVADOS","TODOS"], key="f_status_side")
    ddds=sorted(list(set([l.get("ddd","") for l in st.session_state.leads if l.get("ddd")]))) if st.session_state.leads else []
    st.session_state.filtro_ddd=st.selectbox("DDD", ["TODOS"]+ddds, key="f_ddd_side")
    if st.button("🧹 Limpar Filtros", use_container_width=True, key="clear_side"):
        st.session_state.filtro_banco="TODOS"
        st.session_state.filtro_status="PENDENTES"
        st.session_state.filtro_ddd="TODOS"
        st.session_state.busca_global=""
        st.session_state.selected_id=None
        st.rerun()

tab1, tab_ret, tab_lotes, tab_rel, tab_arq = st.tabs(["🎯 DISCADOR", "⏰ RETORNOS", "📦 LOTES", "📊 RELATÓRIOS", "📁 ARQUIVADOS"])

def filtrar_lista(status_filtro):
    lista=[]
    for l in st.session_state.leads:
        if status_filtro!="TODOS":
            if status_filtro=="PENDENTES" and l["status"]!="pendente":
                continue
            if status_filtro=="ATENDIDOS" and l["status"]!="atendido":
                continue
            if status_filtro=="NÃO ATENDEU" and l["status"]!="nao_atendeu":
                continue
            if status_filtro=="RETORNOS" and l["status"]!="retorno_futuro":
                continue
            if status_filtro=="VENDAS" and l["status"]!="venda_finalizada":
                continue
            if status_filtro=="ARQUIVADOS" and l["status"]!="arquivado":
                continue
        if st.session_state.filtro_banco!="TODOS" and l["banco"]!=st.session_state.filtro_banco:
            continue
        if st.session_state.filtro_ddd!="TODOS" and l.get("ddd","")!=st.session_state.filtro_ddd:
            continue
        busca=st.session_state.busca_global
        if busca and busca.lower() not in l["nome"].lower() and busca.lower() not in l["banco"].lower() and busca.lower() not in l["telefone"]:
            continue
        lista.append(l)
    return lista

with tab1:
    lista=filtrar_lista(st.session_state.filtro_status)
    st.markdown(f"**📋 Fila {st.session_state.filtro_status} ({len(lista)})**")
    col_lista,col_det=st.columns([1,2])
    with col_lista:
        if not lista:
            st.info("Nenhum lead")
        else:
            for lead in lista[:40]:
                is_sel=lead["id"]==st.session_state.selected_id
                label=f"{'👉' if is_sel else '⚪'} {lead['nome'][:12]} | {lead['banco']} | T{lead.get('tentativas',0)}"
                if st.button(label, key=f"tab1_{lead['id']}", use_container_width=True, type="primary" if is_sel else "secondary"):
                    st.session_state.selected_id=lead["id"]
                    st.rerun()
    with col_det:
        if not st.session_state.selected_id:
            st.info("Selecione um lead")
        else:
            sel=next((l for l in st.session_state.leads if l["id"]==st.session_state.selected_id), None)
            if sel:
                st.markdown(f"### {sel['nome']} | {sel['banco']} | {sel['telefone']}")
                st.code(sel['telefone'])
                st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:#00ff88;color:#000;padding:12px;border-radius:8px;text-align:center;font-weight:800;text-decoration:none;">📱 LIGAR {sel["telefone"]}</a>', unsafe_allow_html=True)
                c1,c2,c3,c4=st.columns(4)
                with c1:
                    if st.button("✅ Atendeu", key=f"at_{sel['id']}", use_container_width=True, type="primary"):
                        tabular(sel,"atendido","Atendeu")
                with c2:
                    if st.button("📬 Caixa", key=f"cx_{sel['id']}", use_container_width=True):
                        tabular(sel,"nao_atendeu","Caixa postal")
                with c3:
                    if st.button("📵 Desligado", key=f"des_{sel['id']}", use_container_width=True):
                        tabular(sel,"nao_atendeu","Desligado")
                with c4:
                    if st.button("💰 Venda", key=f"vd_{sel['id']}", use_container_width=True):
                        tabular(sel,"venda_finalizada","Venda")
                c5,c6=st.columns(2)
                with c5:
                    if st.button("📁 Arquivar", key=f"arq_{sel['id']}", use_container_width=True):
                        sel["status"]="arquivado"
                        salvar_dados()
                        st.rerun()
                with c6:
                    if st.button("🔄 Pendentes", key=f"vol_{sel['id']}", use_container_width=True):
                        sel["status"]="pendente"
                        salvar_dados()
                        st.rerun()
                # Observacoes - FIX INDENTACAO
                st.markdown("**📝 Observacoes**")
                notas_val=sel.get("notas_cliente","")
                novas_notas=st.text_area("Obs", value=notas_val, key=f"notas_{sel['id']}", label_visibility="collapsed", height=80)
                if st.button("💾 Salvar Obs", key=f"save_obs_{sel['id']}", use_container_width=True):
                    sel["notas_cliente"]=novas_notas
                    salvar_dados()
                    st.success("Salvo!")

with tab_ret:
    st.markdown(f"### ⏰ Retornos ({retornos_total})")
    lista=filtrar_lista("RETORNOS")
    if not lista:
        st.info("Nenhum retorno")
    else:
        for lead in lista:
            with st.container(border=True):
                st.markdown(f"**{lead['nome']} | {lead['banco']} | {lead['telefone']}**")
                st.caption(f"{lead.get('observacao','')[:60]}")
                if st.button("📥 Voltar p/ Pendentes", key=f"ret_{lead['id']}", use_container_width=True):
                    lead["status"]="pendente"
                    salvar_dados()
                    st.rerun()

with tab_arq:
    st.markdown(f"### 📁 Arquivados ({arquivados})")
    lista=filtrar_lista("ARQUIVADOS")
    if not lista:
        st.info("Nenhum arquivado")
    else:
        for lead in lista[:50]:
            with st.container(border=True):
                st.markdown(f"**📁 {lead['nome']} | {lead['banco']} | {lead['telefone']}**")
                if st.button("🔄 Voltar", key=f"arq_voltar_{lead['id']}", use_container_width=True, type="primary"):
                    lead["status"]="pendente"
                    salvar_dados()
                    st.rerun()

with tab_lotes:
    st.markdown("### 📦 Lotes")
    st.info("Upload de planilhas aqui")

with tab_rel:
    st.markdown("### 📊 Relatórios")
    if st.session_state.leads:
        df=pd.DataFrame(st.session_state.leads)
        st.bar_chart(df["status"].value_counts())
