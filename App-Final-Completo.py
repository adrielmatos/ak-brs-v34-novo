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
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

st.set_page_config(page_title="Discadora Eletrônica A&K", layout="wide", page_icon="📞")

BANCO_EMOJI = {"PAN":"🟢","SAFRA":"🟠","BMG":"🔵","C6":"⚫","ITAU":"🔷","ITAÚ":"🔷","OLE":"🟡","DEFAULT":"⚪"}

try: 
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    GITHUB_REPO = st.secrets["GITHUB_REPO"]
except:
    GITHUB_TOKEN = None
    GITHUB_REPO = None

GITHUB_PATH = "brs_dados.json"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}" if GITHUB_REPO else None

def checar_login():
    if st.session_state.get("logado"): return True
    st.markdown("<div style='text-align:center;padding:40px;'><h1>Discadora Eletrônica<br><span style='color:#00e5ff;'>A&K</span></h1></div>", unsafe_allow_html=True)
    c1,c2,c3=st.columns([1,1,1])
    with c2:
        senha=st.text_input("Senha", type="password", key="senha_login")
        if st.button("Entrar", type="primary", use_container_width=True, key="btn_login"):
            senha_correta = st.secrets.get("APP_PASSWORD", None) if GITHUB_TOKEN else "1234"
            if senha == senha_correta:
                st.session_state.logado=True
                st.rerun()
            else:
                st.error("Senha incorreta")
    return False

if GITHUB_TOKEN:
    if not checar_login(): st.stop()

def carregar_dados():
    if not GITHUB_API or not GITHUB_TOKEN:
        if os.path.exists("brs_dados_local.json"):
            try:
                with open("brs_dados_local.json","r",encoding="utf-8") as f:
                    d=json.load(f)
                    return d.get("leads",[]), d.get("pausas",[]), set(d.get("bloqueados",[])), d.get("lotes",[]), d.get("nao_perturbe",[]), d.get("meta_diaria",20)
            except: return [],[],set(),[],[],20
        return [],[],set(),[],[],20
    try:
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        r=requests.get(GITHUB_API, headers=headers)
        if r.status_code==200:
            conteudo=r.json()
            st.session_state["_gh_sha"]=conteudo["sha"]
            dados=json.loads(base64.b64decode(conteudo["content"]).decode("utf-8"))
            return dados.get("leads",[]), dados.get("pausas",[]), set(dados.get("bloqueados",[])), dados.get("lotes",[]), dados.get("nao_perturbe",[]), dados.get("meta_diaria",20)
        elif r.status_code==404:
            st.session_state["_gh_sha"]=None
            return [],[],set(),[],[],20
    except Exception as e:
        st.error(f"Erro GitHub: {e}")
    return [],[],set(),[],[],20

def salvar_dados():
    try:
        payload={"leads":st.session_state.leads,"pausas":st.session_state.pausas,"bloqueados":list(st.session_state.blocklist),"lotes":st.session_state.lotes,"nao_perturbe":st.session_state.nao_perturbe,"meta_diaria":st.session_state.get("meta_diaria",20)}
        conteudo_str=json.dumps(payload, ensure_ascii=False, indent=2)
        if not GITHUB_API or not GITHUB_TOKEN:
            with open("brs_dados_local.json","w",encoding="utf-8") as f:
                f.write(conteudo_str)
            return
        conteudo_b64=base64.b64encode(conteudo_str.encode("utf-8")).decode("utf-8")
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        body={"message": f"A&K {datetime.now().strftime('%d/%m %H:%M:%S')}","content": conteudo_b64}
        if st.session_state.get("_gh_sha"):
            body["sha"]=st.session_state["_gh_sha"]
        r=requests.put(GITHUB_API, headers=headers, json=body)
        if r.status_code in (200,201):
            st.session_state["_gh_sha"]=r.json()["content"]["sha"]
    except Exception as e:
        st.warning(f"Erro salvar: {e}")

if "leads" not in st.session_state:
    leads,pausas,blocklist,lotes,nao_perturbe,meta_diaria=carregar_dados()
    for l in leads:
        if "notas_cliente" not in l: l["notas_cliente"]=""
        if "arquivado_motivo" not in l: l["arquivado_motivo"]=""
        if "retorno_hora" not in l: l["retorno_hora"]=""
    st.session_state.leads=leads
    st.session_state.pausas=pausas
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

def formatar_tempo(seg):
    if not seg or seg<=0: return "00:00"
    m=int(seg//60); s=int(seg%60)
    if m>=60:
        h=m//60; m=m%60
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def proximo_inteligente(atual_id=None):
    pend=[l for l in st.session_state.leads if l["status"]=="pendente"]
    if not pend: return None
    pend_sorted=sorted(pend, key=lambda x: (0 if x.get("ultima")=="Nunca" else 1, x.get("tentativas",0)))
    if not atual_id: return pend_sorted[0]["id"]
    ids=[l["id"] for l in pend_sorted]
    if atual_id not in ids: return pend_sorted[0]["id"]
    idx=ids.index(atual_id)
    if idx+1 < len(ids): return ids[idx+1]
    return pend_sorted[0]["id"] if len(pend_sorted)>1 else None

total=len(st.session_state.leads)
pend=len([l for l in st.session_state.leads if l["status"]=="pendente"])
nunca=len([l for l in st.session_state.leads if l["status"]=="pendente" and l.get("ultima")=="Nunca"])
vendas=len([l for l in st.session_state.leads if l["status"]=="venda_finalizada"])
vendas_hoje=len([l for l in st.session_state.leads if l["status"]=="venda_finalizada" and datetime.now().strftime("%d/%m") in l.get("ultima","")])
retornos_total=len([l for l in st.session_state.leads if l["status"]=="retorno_futuro"])
arquivados=len([l for l in st.session_state.leads if l["status"]=="arquivado"])
atendidos=len([l for l in st.session_state.leads if l["status"]=="atendido"])
nao_atendeu=len([l for l in st.session_state.leads if l["status"]=="nao_atendeu"])

st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f0c29,#302b63);padding:18px 22px;border-radius:16px;color:white;margin-bottom:12px;border:1px solid rgba(0,255,136,0.15);">
<h1 style="margin:0;font-size:20px;">Discadora Eletrônica <span style="color:#00e5ff;">A&K</span></h1>
<p style="margin:0;opacity:0.6;font-size:11px;">{total} leads • {pend} pendentes • {arquivados} arquivados • {datetime.now().strftime('%d/%m %H:%M')}</p>
</div>
""", unsafe_allow_html=True)

# KPIs SIMPLES - SEM BOTÃO QUEBRADO, SÓ INFO
c1,c2,c3,c4,c5,c6,c7=st.columns(7)
with c1: st.metric("TOTAL", total, f"{atendidos}a {nao_atendeu}na")
with c2: st.metric("PENDENTES", pend)
with c3: st.metric("NUNCA", nunca)
with c4: st.metric("VENDAS", vendas)
with c5: st.metric("HOJE", vendas_hoje)
with c6: st.metric("RETORNOS", retornos_total)
with c7: st.metric("ARQUIV", arquivados)

with st.sidebar:
    st.markdown("### 🔍 Filtros")
    st.session_state.busca_global = st.text_input("Busca", value=st.session_state.busca_global, placeholder="Nome, banco, tel", key="busca_side")
    bancos = sorted(list(set([l["banco"] for l in st.session_state.leads]))) if st.session_state.leads else []
    st.session_state.filtro_banco = st.selectbox("Banco", ["TODOS"]+bancos, key="f_banco_side")
    st.session_state.filtro_status = st.selectbox("Status", ["PENDENTES","ATENDIDOS","NÃO ATENDEU","RETORNOS","VENDAS","ARQUIVADOS","TODOS"], key="f_status_side")
    ddds = sorted(list(set([l.get("ddd","") for l in st.session_state.leads if l.get("ddd")])) ) if st.session_state.leads else []
    st.session_state.filtro_ddd = st.selectbox("DDD", ["TODOS"]+ddds, key="f_ddd_side")
    st.session_state.ordenar_por = st.selectbox("Ordenar", ["NUNCA LIGADOS PRIMEIRO","MENOS TENTATIVAS","NOME A-Z"], key="f_ord_side")
    if st.button("🧹 Limpar Filtros", use_container_width=True, key="clear_side"):
        st.session_state.filtro_banco="TODOS"
        st.session_state.filtro_status="PENDENTES"
        st.session_state.filtro_ddd="TODOS"
        st.session_state.busca_global=""
        st.session_state.selected_id=None
        st.rerun()

# 5 ABAS IGUAIS - COM ARQUIVADOS AGORA
tab1, tab_ret, tab_lotes, tab_rel, tab_arq = st.tabs(["🎯 DISCADOR", "⏰ RETORNOS", "📦 LOTES", "📊 RELATÓRIOS", "📁 ARQUIVADOS"])

def filtrar_lista(status_filtro):
    lista=[]
    for l in st.session_state.leads:
        if status_filtro=="PENDENTES" and l["status"]!="pendente": continue
        if status_filtro=="ATENDIDOS" and l["status"]!="atendido": continue
        if status_filtro=="NÃO ATENDEU" and l["status"]!="nao_atendeu": continue
        if status_filtro=="RETORNOS" and l["status"]!="retorno_futuro": continue
        if status_filtro=="VENDAS" and l["status"]!="venda_finalizada": continue
        if status_filtro=="ARQUIVADOS" and l["status"]!="arquivado": continue
        if st.session_state.filtro_banco!="TODOS" and l["banco"]!=st.session_state.filtro_banco: continue
        if st.session_state.filtro_ddd!="TODOS" and l.get("ddd","")!=st.session_state.filtro_ddd: continue
        busca=st.session_state.busca_global
        if busca and busca.lower() not in l["nome"].lower() and busca.lower() not in l["banco"].lower() and busca.lower() not in l["telefone"]: continue
        lista.append(l)
    if st.session_state.ordenar_por=="NUNCA LIGADOS PRIMEIRO":
        lista=sorted(lista, key=lambda x: (0 if x.get("ultima")=="Nunca" else 1, x.get("tentativas",0)))
    return lista

def mostrar_detalhes_lead(sel):
    if not sel:
        return
    st.markdown(f"### {BANCO_EMOJI.get(sel['banco'],'⚪')} {sel['nome']} | 🏦 {sel['banco']} | T{sel.get('tentativas',0)}")
    st.markdown(f"**📱 {sel['telefone']}** | CPF: {sel.get('cpf','')} | DDD: {sel.get('ddd','')} | Lote: {sel.get('lote','')[:20]}")
    st.code(sel['telefone'])
    
    col1,col2,col3=st.columns([1,1,1])
    with col1:
        if st.button(f"▶️ LIGAR", key=f"ligar_{sel['id']}", type="primary", use_container_width=True):
            st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:#00ff88;color:#000;padding:12px;border-radius:8px;text-align:center;font-weight:800;text-decoration:none;">📱 LIGANDO {sel["telefone"]}</a>', unsafe_allow_html=True)
            sel["tentativas"]=sel.get("tentativas",0)+1
            sel["ultima"]=datetime.now().strftime("%d/%m %H:%M")
            salvar_dados()
    with col2:
        msg=f"Olá {sel['nome']}, A&K FGTS {sel['banco']} liberado"
        msg_enc=urllib.parse.quote(msg)
        st.markdown(f'<a href="https://wa.me/55{sel["telefone"]}?text={msg_enc}" target="_blank" style="display:block;background:#25D366;color:#fff;padding:10px;border-radius:8px;text-align:center;font-weight:700;text-decoration:none">💬 Zap</a>', unsafe_allow_html=True)
    with col3:
        if st.button("🚫 Bloquear", key=f"bloq_{sel['id']}", use_container_width=True):
            st.session_state.blocklist.add(sel["telefone"])
            salvar_dados()
            st.rerun()

    st.divider()
    c1,c2,c3,c4=st.columns(4)
    with c1:
        if st.button("✅ Atendeu", key=f"at_{sel['id']}", use_container_width=True, type="primary"):
            sel["status"]="atendido"; sel["ultima"]=datetime.now().strftime("%d/%m %H:%M"); sel["tentativas"]=sel.get("tentativas",0)+1; sel["historico"]=sel.get("historico",[])+[{"data":datetime.now().strftime("%d/%m %H:%M:%S"),"acao":"atendido","tab":"Atendeu"}]; salvar_dados(); st.session_state.selected_id=proximo_inteligente(sel["id"]); st.rerun()
    with c2:
        if st.button("📬 Caixa", key=f"cx_{sel['id']}", use_container_width=True):
            sel["status"]="nao_atendeu"; sel["ultima"]=datetime.now().strftime("%d/%m %H:%M"); sel["tentativas"]=sel.get("tentativas",0)+1; sel["observacao"]="Caixa postal"; salvar_dados(); st.session_state.selected_id=proximo_inteligente(sel["id"]); st.rerun()
    with c3:
        if st.button("📵 Desligado", key=f"des_{sel['id']}", use_container_width=True):
            sel["status"]="nao_atendeu"; sel["ultima"]=datetime.now().strftime("%d/%m %H:%M"); sel["tentativas"]=sel.get("tentativas",0)+1; salvar_dados(); st.session_state.selected_id=proximo_inteligente(sel["id"]); st.rerun()
    with c4:
        if st.button("💰 Venda", key=f"vd_{sel['id']}", use_container_width=True):
            sel["status"]="venda_finalizada"; sel["ultima"]=datetime.now().strftime("%d/%m %H:%M"); sel["tentativas"]=sel.get("tentativas",0)+1; st.balloons(); salvar_dados(); st.session_state.selected_id=proximo_inteligente(sel["id"]); st.rerun()
    
    c5,c6,c7=st.columns(3)
    with c5:
        if st.button("📁 Arquivar - Já liguei", key=f"arq_{sel['id']}", use_container_width=True):
            sel["status"]="arquivado"; sel["arquivado_motivo"]="Já liguei - ocultar"; sel["ultima"]=datetime.now().strftime("%d/%m %H:%M"); salvar_dados(); st.session_state.selected_id=proximo_inteligente(sel["id"]); st.rerun()
    with c6:
        if st.button("🔄 Voltar p/ Pendentes", key=f"vol_{sel['id']}", use_container_width=True):
            sel["status"]="pendente"; salvar_dados(); st.rerun()
    with c7:
        if st.button("❌ Número errado", key=f"err_{sel['id']}", use_container_width=True):
            sel["status"]="nao_atendeu"; sel["observacao"]="Número errado"; salvar_dados(); st.session_state.selected_id=proximo_inteligente(sel["id"]); st.rerun()

    with st.expander("📅 Agendar Retorno com Data"):
        d1,d2=st.columns(2)
        with d1: data_ret=st.date_input("Data", value=date.today()+timedelta(days=1), min_value=date.today(), key=f"data_ret_{sel['id']}")
        with d2: hora_ret=st.time_input("Hora", value=time(14,0), key=f"hora_ret_{sel['id']}")
        motivo=st.text_input("Motivo", key=f"motivo_{sel['id']}")
        if st.button(f"✅ Agendar {data_ret.strftime('%d/%m')} {hora_ret.strftime('%H:%M')}", key=f"conf_ret_{sel['id']}", type="primary", use_container_width=True):
            sel["status"]="retorno_futuro"; sel["retorno_data"]=data_ret.strftime("%d/%m/%Y"); sel["retorno_hora"]=hora_ret.strftime("%H:%M"); sel["observacao"]=f"Retorno {data_ret.strftime('%d/%m/%Y')} {hora_ret.strftime('%H:%M')} {motivo}"; sel["ultima"]=datetime.now().strftime("%d/%m %H:%M"); salvar_dados(); st.success(f"Agendado para {data_ret.strftime('%d/%m/%Y')}"); st.rerun()

    st.markdown("**📝 Observações**")
    notas=st.text_area("Obs", value=sel.get("notas_cliente",""), placeholder="Ex: Tem 2 cartões", key=f"notas_{sel['id']}", label_visibility="collapsed", height=80)
    if st.button("💾 Salvar Obs", key=f"save_obs_{sel['id']}", use_container_width=True):
        sel["notas_cliente"]=notas; salvar_dados(); st.success("Salvo!")

    hist=sel.get("historico") or []
    if hist:
        st.markdown("**📜 Histórico**")
        for h in hist[::-1][:10]:
            st.caption(f"{h.get('data','')} | {h.get('acao','')} | {h.get('tab','')[:50]}")

with tab1:
    st.markdown(f"**📋 Fila PENDENTES ({pend})** - Clique no lead para ver detalhes")
    lista=filtrar_lista("PENDENTES")
    col_lista,col_det=st.columns([1,2])
    with col_lista:
        if not lista:
            st.info("Nenhum pendente")
        else:
            for lead in lista[:40]:
                is_sel=lead["id"]==st.session_state.selected_id
                label=f"{'👉' if is_sel else '⚪'} {lead['nome'][:12]} | {lead['banco']} | {lead['telefone'][-4:]} | T{lead.get('tentativas',0)}"
                if st.button(label, key=f"list_pend_{lead['id']}", use_container_width=True, type="primary" if is_sel else "secondary"):
                    st.session_state.selected_id=lead["id"]
                    st.rerun()
    with col_det:
        if not st.session_state.selected_id:
            st.info("👈 Selecione um lead na fila")
        else:
            sel=next((l for l in st.session_state.leads if l["id"]==st.session_state.selected_id), None)
            mostrar_detalhes_lead(sel)

with tab_ret:
    st.markdown(f"### ⏰ Retornos Futuros ({retornos_total})")
    lista=filtrar_lista("RETORNOS")
    if not lista:
        st.info("Nenhum retorno agendado")
    else:
        for lead in lista:
            with st.container(border=True):
                st.markdown(f"**{lead['nome']} | {lead['banco']} | {lead['telefone']}**")
                st.caption(f"📅 {lead.get('retorno_data','')} {lead.get('retorno_hora','')} | {lead.get('observacao','')[:60]} | Lote: {lead.get('lote','')}")
                c1,c2=st.columns(2)
                with c1:
                    if st.button("▶️ Ligar Agora", key=f"ligar_ret_{lead['id']}", type="primary", use_container_width=True):
                        st.session_state.selected_id=lead["id"]
                        st.info("Vá em DISCADOR")
                with c2:
                    if st.button("📥 Voltar p/ Pendentes", key=f"pend_ret_{lead['id']}", use_container_width=True):
                        lead["status"]="pendente"
                        salvar_dados()
                        st.rerun()

with tab_arq:
    st.markdown(f"### 📁 Arquivados - Já liguei / Ocultar ({arquivados})")
    st.caption("Aqui ficam os números que você clicou em 📁 Arquivar - Já liguei. Eles não aparecem mais em PENDENTES")
    lista=filtrar_lista("ARQUIVADOS")
    if not lista:
        st.info("📭 Nenhum arquivado ainda. No DISCADOR clique em 📁 Arquivar - Já liguei para ocultar da lista")
    else:
        st.success(f"📁 {len(lista)} números arquivados - não aparecem em PENDENTES")
        for lead in lista[:50]:
            with st.container(border=True):
                st.markdown(f"**📁 {lead['nome']} | 🏦 {lead['banco']} | 📱 {lead['telefone']} | T{lead.get('tentativas',0)}**")
                st.caption(f"Motivo: {lead.get('arquivado_motivo','Já liguei')} | Última: {lead.get('ultima','')} | Lote: {lead.get('lote','')[:20]} | Obs: {lead.get('notas_cliente','')[:50]}")
                c1,c2,c3=st.columns(3)
                with c1:
                    if st.button("🔄 Voltar p/ Pendentes", key=f"voltar_arq_{lead['id']}", use_container_width=True, type="primary"):
                        lead["status"]="pendente"
                        salvar_dados()
                        st.success(f"{lead['nome']} voltou para pendentes")
                        st.rerun()
                with c2:
                    if st.button(f"▶️ Ligar {lead['telefone'][-4:]}", key=f"ligar_arq_{lead['id']}", use_container_width=True):
                        st.markdown(f'<a href="tel:{lead["telefone"]}" style="display:block;background:#00ff88;color:#000;padding:10px;border-radius:8px;text-align:center;font-weight:800;text-decoration:none;">📱 {lead["telefone"]}</a>', unsafe_allow_html=True)
                with c3:
                    if st.button("🗑️ Excluir definitivo", key=f"del_arq_{lead['id']}", use_container_width=True):
                        st.session_state.leads=[l for l in st.session_state.leads if l["id"]!=lead["id"]]
                        salvar_dados()
                        st.rerun()

with tab_lotes:
    st.markdown("### 📦 Lotes")
    arqs=st.file_uploader("Arraste planilhas", type=["csv","xlsx","xls"], accept_multiple_files=True, key="upload_lotes")
    if arqs:
        if st.button("✅ IMPORTAR TUDO", type="primary", use_container_width=True, key="import_all_lotes"):
            st.info("Importando...")
            # Simplificado - implementar se precisar

with tab_rel:
    st.markdown("### 📊 Relatórios")
    if st.session_state.leads:
        df=pd.DataFrame(st.session_state.leads)
        st.bar_chart(df["status"].value_counts())
        csv=df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ CSV Geral", csv, file_name=f"BRS_{datetime.now().strftime('%d%m%Y')}.csv", mime="text/csv", use_container_width=True)
