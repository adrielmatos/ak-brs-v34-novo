import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
import json
import os
from io import BytesIO
import time
import urllib.parse

st.set_page_config(page_title="A&K BRS v5.2 CLEAN PRO", layout="wide", page_icon="📱")

ARQUIVO_BASE = "brs_base_persistente.json"
ARQUIVO_PAUSAS = "brs_pausas.json"

def salvar_base():
    try:
        with open(ARQUIVO_BASE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.leads, f, ensure_ascii=False, indent=2)
    except: pass

def carregar_base():
    if os.path.exists(ARQUIVO_BASE):
        try:
            with open(ARQUIVO_BASE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

def salvar_pausas(pausas):
    try:
        with open(ARQUIVO_PAUSAS, 'w', encoding='utf-8') as f:
            json.dump(pausas, f, ensure_ascii=False, indent=2)
    except: pass

def carregar_pausas():
    if os.path.exists(ARQUIVO_PAUSAS):
        try:
            with open(ARQUIVO_PAUSAS, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

if 'leads' not in st.session_state:
    st.session_state.leads = carregar_base()
    st.session_state.pausas = carregar_pausas()
    st.session_state.selected_id = None
    st.session_state.auto_next = True
    st.session_state.call_start = {}
    st.session_state.filtro_banco = "TODOS"
    st.session_state.filtro_status = "PENDENTES"
    st.session_state.modo_discador = "POWER (chip) - Auto 3s"
    st.session_state.em_pausa = None
    st.session_state.pausa_inicio = None
    st.session_state.modo_foco = False

def formatar_tempo(seg):
    if not seg or seg<=0: return "00:00"
    m=int(seg//60); s=int(seg%60)
    if m>=60:
        h=m//60; m=m%60
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def proximo_inteligente(atual_id=None):
    pend = [l for l in st.session_state.leads if l['status']=='pendente']
    if not pend:
        return None
    vendas_por_banco = {}
    for l in st.session_state.leads:
        if l['status']=='venda_finalizada':
            vendas_por_banco[l['banco']] = vendas_por_banco.get(l['banco'],0)+1
    def score(l):
        tent = l.get('tentativas',0)*10
        nunca = 0 if l.get('ultima')=='Nunca' else 5
        banco_bonus = -2 if vendas_por_banco.get(l['banco'],0) >= max(vendas_por_banco.values(), default=0) and vendas_por_banco else 0
        return tent + nunca + banco_bonus
    pend_sorted = sorted(pend, key=score)
    if not atual_id:
        return pend_sorted[0]['id']
    ids = [l['id'] for l in pend_sorted]
    if atual_id not in ids:
        return pend_sorted[0]['id']
    idx = ids.index(atual_id)
    if idx+1 < len(ids):
        return ids[idx+1]
    return pend_sorted[0]['id'] if len(pend_sorted)>1 else None

st.markdown("""
<style>
.mini-dash {
  position: fixed;
  bottom: 12px;
  right: 12px;
  background: rgba(255,255,255,0.95);
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  padding: 8px 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
  z-index: 9999;
  font-size: 12px;
}
.foco-overlay {
  background: #f8fafc;
  border: 2px solid #00c853;
  border-radius: 16px;
  padding: 20px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("## 📱 A&K BRS v5.2 CLEAN PRO | Leve sem openpyxl")
col_h1,col_h2,col_h3,col_h4,col_h5 = st.columns([2.5,1,1,1,1])
with col_h1:
    total=len(st.session_state.leads)
    pend=len([l for l in st.session_state.leads if l['status']=='pendente'])
    st.caption(f"📱 {total} | 📥 {pend} pendentes | 🧠 Fila Inteligente | Sem openpyxl")
with col_h2:
    st.session_state.modo_discador = st.selectbox("Modo", ["POWER (chip) - Auto 3s","PREVIEW (chip) - 5s","MANUAL (chip)"], label_visibility="collapsed")
with col_h3:
    st.session_state.auto_next = st.checkbox("⏭️ Auto", value=True)
with col_h4:
    if st.button("🧠 Próximo Inteligente", use_container_width=True, type="primary"):
        nxt = proximo_inteligente(st.session_state.selected_id)
        if nxt:
            st.session_state.selected_id=nxt
            st.session_state.modo_foco=False
            st.rerun()
with col_h5:
    if st.button("🗑️ Reset", use_container_width=True):
        if os.path.exists(ARQUIVO_BASE): os.remove(ARQUIVO_BASE)
        st.session_state.leads=[]; st.session_state.selected_id=None; st.rerun()

with st.sidebar:
    st.markdown("### 🎯 Filtros")
    banco_list = ["TODOS"] + sorted(list(set([l['banco'] for l in st.session_state.leads]))) if st.session_state.leads else ["TODOS"]
    st.session_state.filtro_banco = st.selectbox("🏦 Banco", banco_list)
    st.session_state.filtro_status = st.selectbox("📊 Status", ["PENDENTES","ATENDIDOS","NÃO ATENDEU","RETORNOS","VENDAS","TODOS"])
    busca = st.text_input("🔍 Buscar", placeholder="Nome, banco...")
    st.markdown("---")
    st.markdown("### ⏸️ Pausas")
    em_pausa = st.session_state.em_pausa is not None
    if not em_pausa:
        c1,c2=st.columns(2)
        with c1:
            if st.button("☕ Almoço", use_container_width=True):
                st.session_state.em_pausa="Almoço"; st.session_state.pausa_inicio=datetime.now(); st.rerun()
            if st.button("📚 Feedback", use_container_width=True):
                st.session_state.em_pausa="Feedback"; st.session_state.pausa_inicio=datetime.now(); st.rerun()
        with c2:
            if st.button("🚻 Banheiro", use_container_width=True):
                st.session_state.em_pausa="Banheiro"; st.session_state.pausa_inicio=datetime.now(); st.rerun()
            if st.button("💤 Pausa", use_container_width=True):
                st.session_state.em_pausa="Pausa"; st.session_state.pausa_inicio=datetime.now(); st.rerun()
        st.success("🟢 Disponível")
    else:
        decorrido = (datetime.now()-st.session_state.pausa_inicio).total_seconds()
        st.warning(f"⏸️ {st.session_state.em_pausa} {formatar_tempo(decorrido)}")
        if st.button("▶️ Voltar", type="primary", use_container_width=True):
            fim=datetime.now(); duracao=(fim-st.session_state.pausa_inicio).total_seconds()
            st.session_state.pausas.append({"tipo":st.session_state.em_pausa,"inicio":st.session_state.pausa_inicio.strftime("%d/%m %H:%M:%S"),"fim":fim.strftime("%d/%m %H:%M:%S"),"duracao_seg":int(duracao),"duracao_txt":formatar_tempo(duracao)})
            salvar_pausas(st.session_state.pausas)
            st.session_state.em_pausa=None; st.session_state.pausa_inicio=None; st.rerun()

modo_foco_ativo = st.session_state.modo_foco and st.session_state.selected_id in st.session_state.call_start if st.session_state.selected_id else False

if not st.session_state.leads:
    st.info("📥 Importe base CSV - XLSX agora funciona sem openpyxl (usando modo compatível)")
    tab_csv, tab_xlsx = st.tabs(["📄 CSV (recomendado)", "📊 XLSX sem openpyxl"])
    with tab_csv:
        up=st.file_uploader("CSV", type=["csv"], key="csv_import")
        if up:
            df=pd.read_csv(up)
            df.columns=[str(c).upper().strip() for c in df.columns]
            col_nome=next((c for c in df.columns if 'NOME' in c), df.columns[0])
            col_cpf=next((c for c in df.columns if 'CPF' in c), None)
            col_tel=next((c for c in df.columns if 'TELEFONE' in c or c=='TEL' or 'CEL' in c), None)
            col_banco=next((c for c in df.columns if 'BANCO' in c), None)
            existentes=set([l['id'] for l in st.session_state.leads])
            novos=[]
            for idx, row in df.iterrows():
                cpf=str(row.get(col_cpf,'')).strip() if col_cpf else f"semcpf{idx}"
                tel=str(row.get(col_tel,'')).strip() if col_tel else ''
                if not tel or str(tel).lower()=='nan' or len(str(tel))<8: continue
                h=hashlib.sha256(f"{cpf}{tel}".encode()).hexdigest()[:12]
                if h in existentes: continue
                existentes.add(h)
                novos.append({"id":h,"nome":str(row.get(col_nome,f'Lead {idx}'))[:40],"cpf":cpf,"telefone":str(tel),"banco":str(row.get(col_banco,'PAN')).upper()[:20] if col_banco else 'PAN',"produto":"FGTS","status":"pendente","tentativas":0,"ultima":"Nunca","duracao_seg":0,"duracao_txt":"00:00","historico":[],"tabulacao":"","observacao":"","canal":"chip","custo_estimado":0.0})
            st.session_state.leads.extend(novos); salvar_base()
            st.success(f"✅ {len(novos)} importados")
            if novos: st.session_state.selected_id=novos[0]['id']; st.rerun()
    with tab_xlsx:
        st.warning("Seu ambiente não tem openpyxl, mas vou tentar com xlrd / modo nativo")
        up=st.file_uploader("XLSX/XLS", type=["xlsx","xls"], key="xlsx_import")
        if up:
            try:
                # tenta sem engine especifico - pandas tenta achar
                df=pd.read_excel(up)
                df.columns=[str(c).upper().strip() for c in df.columns]
                col_nome=next((c for c in df.columns if 'NOME' in c), df.columns[0])
                col_cpf=next((c for c in df.columns if 'CPF' in c), None)
                col_tel=next((c for c in df.columns if 'TELEFONE' in c or c=='TEL' or 'CEL' in c), None)
                col_banco=next((c for c in df.columns if 'BANCO' in c), None)
                existentes=set([l['id'] for l in st.session_state.leads])
                novos=[]
                for idx, row in df.iterrows():
                    cpf=str(row.get(col_cpf,'')).strip() if col_cpf else f"semcpf{idx}"
                    tel=str(row.get(col_tel,'')).strip() if col_tel else ''
                    if not tel or str(tel).lower()=='nan' or len(str(tel))<8: continue
                    h=hashlib.sha256(f"{cpf}{tel}".encode()).hexdigest()[:12]
                    if h in existentes: continue
                    existentes.add(h)
                    novos.append({"id":h,"nome":str(row.get(col_nome,f'Lead {idx}'))[:40],"cpf":cpf,"telefone":str(tel),"banco":str(row.get(col_banco,'PAN')).upper()[:20] if col_banco else 'PAN',"produto":"FGTS","status":"pendente","tentativas":0,"ultima":"Nunca","duracao_seg":0,"duracao_txt":"00:00","historico":[],"tabulacao":"","observacao":"","canal":"chip","custo_estimado":0.0})
                st.session_state.leads.extend(novos); salvar_base()
                st.success(f"✅ {len(novos)} importados")
                if novos: st.session_state.selected_id=novos[0]['id']; st.rerun()
            except Exception as e:
                st.error(f"Erro XLSX: {e} - Salve como CSV e importe na aba CSV")
                st.info("Dica: Abra seu Excel > Salvar Como > CSV > importe aqui")
else:
    lista=[]
    for l in st.session_state.leads:
        if st.session_state.filtro_banco!="TODOS" and l['banco']!=st.session_state.filtro_banco: continue
        if st.session_state.filtro_status=="PENDENTES" and l['status']!='pendente': continue
        if st.session_state.filtro_status=="ATENDIDOS" and l['status']!='atendido': continue
        if st.session_state.filtro_status=="NÃO ATENDEU" and l['status']!='nao_atendeu': continue
        if st.session_state.filtro_status=="RETORNOS" and l['status']!='retorno_futuro': continue
        if st.session_state.filtro_status=="VENDAS" and l['status']!='venda_finalizada': continue
        if busca and busca.lower() not in l['nome'].lower() and busca.lower() not in l['banco'].lower(): continue
        lista.append(l)
    
    if modo_foco_ativo:
        sel = next((l for l in st.session_state.leads if l['id']==st.session_state.selected_id), None)
        if sel:
            st.markdown(f'<div class="foco-overlay">', unsafe_allow_html=True)
            st.markdown(f"## 🎯 MODO FOCO | {sel['nome']} | 🏦 {sel['banco']}")
            decorrido = (datetime.now()-st.session_state.call_start[sel['id']]).total_seconds()
            st.markdown(f"### ⏱️ {formatar_tempo(decorrido)} | 📱 {sel['telefone']}")
            numero=''.join(filter(str.isdigit, sel['telefone']))
            st.markdown(f'<a href="tel:{numero}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:22px;border-radius:14px;text-align:center;font-weight:900;text-decoration:none;font-size:24px">📱 {sel["telefone"]} • EM LIGAÇÃO</a>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            def finalizar_foco(status_final, obs_pronta):
                fim=datetime.now(); dur=0
                if sel['id'] in st.session_state.call_start:
                    dur=(fim-st.session_state.call_start[sel['id']]).total_seconds()
                    del st.session_state.call_start[sel['id']]
                custo=(dur/60)*0.15
                sel['status']=status_final; sel['tentativas']+=1; sel['ultima']=fim.strftime("%d/%m %H:%M"); sel['duracao_seg']=int(dur); sel['duracao_txt']=formatar_tempo(dur); sel['observacao']=obs_pronta; sel['tabulacao']=obs_pronta[:30]; sel['custo_estimado']=sel.get('custo_estimado',0)+custo
                sel['historico'].append({"data":fim.strftime("%d/%m %H:%M:%S"),"acao":status_final,"tempo":formatar_tempo(dur),"tab":obs_pronta})
                salvar_base()
                st.session_state.modo_foco=False
                if st.session_state.auto_next:
                    st.session_state.selected_id=proximo_inteligente(sel['id'])
                st.rerun()
            c1,c2,c3,c4=st.columns(4)
            with c1:
                if st.button("✅ Interessado", use_container_width=True, type="primary", key=f"foco_at1_{sel['id']}"): finalizar_foco('atendido','Atendeu - interessado')
            with c2:
                if st.button("🔴 Caixa", use_container_width=True, key=f"foco_cx_{sel['id']}"): finalizar_foco('nao_atendeu','Caixa postal')
            with c3:
                if st.button("📵 Desligado", use_container_width=True, key=f"foco_des_{sel['id']}"): finalizar_foco('nao_atendeu','Desligado')
            with c4:
                if st.button("💰 Venda!", use_container_width=True, key=f"foco_vd_{sel['id']}"): st.balloons(); finalizar_foco('venda_finalizada','Venda FGTS')
            if st.button("🔙 Sair do Foco", use_container_width=True, key=f"foco_sair_{sel['id']}"): st.session_state.modo_foco=False; st.rerun()
    else:
        col_lista, col_atend = st.columns([1,2.2])
        with col_lista:
            st.markdown(f"#### 📋 Fila Inteligente: {st.session_state.filtro_banco} ({len(lista)})")
            for lead in lista[:80]:
                dot={"pendente":"⚪","atendido":"🟢","nao_atendeu":"🔴","retorno_futuro":"🟠","venda_finalizada":"💰"}[lead['status']]
                is_sel = lead['id']==st.session_state.selected_id
                tent_txt = f" T{lead.get('tentativas',0)}"
                if st.button(f"{'👉' if is_sel else ''}{dot} {lead['nome'][:14]} • {lead['banco']}{tent_txt}", key=f"list_{lead['id']}", use_container_width=True, type="primary" if is_sel else "secondary"):
                    st.session_state.selected_id=lead['id']
                    st.session_state.modo_foco=False
                    st.rerun()
        with col_atend:
            if not st.session_state.selected_id:
                st.info(f"👈 Selecione cliente ou clique 🧠 Próximo Inteligente")
            else:
                sel = next((l for l in st.session_state.leads if l['id']==st.session_state.selected_id), None)
                if sel:
                    st.markdown(f"### 👤 {sel['nome']} | 🏦 {sel['banco']} | 📱 {sel['telefone']}")
                    numero=''.join(filter(str.isdigit, sel['telefone']))
                    em_ligacao = sel['id'] in st.session_state.call_start
                    em_pausa = st.session_state.em_pausa is not None
                    if em_pausa:
                        st.error(f"⏸️ Em pausa: {st.session_state.em_pausa}")
                    elif not em_ligacao:
                        col_d1,col_d2,col_d3 = st.columns([2,1,1])
                        with col_d1:
                            if st.button(f"▶️ LIGAR CHIP • {sel['telefone']}", key=f"discar_{sel['id']}", type="primary", use_container_width=True):
                                st.session_state.call_start[sel['id']]=datetime.now()
                                st.session_state.modo_foco=True
                                st.rerun()
                        with col_d2:
                            msg_map = {
                                "PAN": f"Olá {sel['nome']}, aqui é da A&K sobre seu FGTS BANCO PAN liberado. Posso te explicar em 1 min?",
                                "BMG": f"Olá {sel['nome']}, BMG liberou saque FGTS pra você. Quer saber valor?",
                                "C6": f"Olá {sel['nome']}, C6 BANK liberou FGTS. Te explico rapidinho?"
                            }
                            msg = msg_map.get(sel['banco'], f"Olá {sel['nome']}, aqui é da A&K sobre FGTS {sel['banco']} liberado")
                            msg_enc = urllib.parse.quote(msg)
                            st.markdown(f'<a href="https://wa.me/55{numero}?text={msg_enc}" target="_blank" style="display:block;background:#25D366;color:#fff;padding:12px;border-radius:8px;text-align:center;font-weight:700;text-decoration:none">💬 Zap {sel["banco"]}</a>', unsafe_allow_html=True)
                        with col_d3:
                            if st.button("🎯 Foco ON", key=f"foco_on_{sel['id']}", use_container_width=True):
                                st.session_state.modo_foco=True; st.rerun()
                    else:
                        decorrido = (datetime.now()-st.session_state.call_start[sel['id']]).total_seconds()
                        st.warning(f"📱 EM LIGAÇÃO: {formatar_tempo(decorrido)}")
                        st.markdown(f'<a href="tel:{numero}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:18px;border-radius:12px;text-align:center;font-weight:900;text-decoration:none;font-size:20px">📱 {sel["telefone"]} • ⏱️ {formatar_tempo(decorrido)}</a>', unsafe_allow_html=True)
                        if st.button("🔍 Ver Modo Foco grande", key=f"ver_foco_{sel['id']}", type="primary", use_container_width=True):
                            st.session_state.modo_foco=True; st.rerun()
                    
                    st.markdown("#### ⚡ Tabulação 1 clique")
                    def finalizar(status_final, obs_pronta):
                        fim=datetime.now(); dur=0
                        if sel['id'] in st.session_state.call_start:
                            dur=(fim-st.session_state.call_start[sel['id']]).total_seconds()
                            del st.session_state.call_start[sel['id']]
                        custo=(dur/60)*0.15
                        sel['status']=status_final; sel['tentativas']+=1; sel['ultima']=fim.strftime("%d/%m %H:%M"); sel['duracao_seg']=int(dur); sel['duracao_txt']=formatar_tempo(dur); sel['observacao']=obs_pronta; sel['tabulacao']=obs_pronta[:30]; sel['custo_estimado']=sel.get('custo_estimado',0)+custo
                        sel['historico'].append({"data":fim.strftime("%d/%m %H:%M:%S"),"acao":status_final,"tempo":formatar_tempo(dur),"tab":obs_pronta})
                        salvar_base()
                        st.session_state.modo_foco=False
                        if st.session_state.auto_next:
                            st.session_state.selected_id=proximo_inteligente(sel['id'])
                        st.rerun()
                    c1,c2,c3,c4=st.columns(4)
                    with c1:
                        if st.button("✅ Atendeu", use_container_width=True, type="primary", key=f"fin_at_{sel['id']}"): finalizar('atendido','Atendeu - interessado')
                    with c2:
                        if st.button("🔴 Caixa", use_container_width=True, key=f"fin_cx_{sel['id']}"): finalizar('nao_atendeu','Caixa postal')
                    with c3:
                        if st.button("📵 Deslig", use_container_width=True, key=f"fin_des_{sel['id']}"): finalizar('nao_atendeu','Desligado')
                    with c4:
                        if st.button("💰 Venda", use_container_width=True, key=f"fin_ve_{sel['id']}"): st.balloons(); finalizar('venda_finalizada','Venda FGTS')
                    c5,c6,c7=st.columns(3)
                    with c5:
                        if st.button("🤔 Sem interesse", use_container_width=True, key=f"fin_si_{sel['id']}"): finalizar('atendido','Sem interesse no momento')
                    with c6:
                        if st.button("📅 Retorno 14h", use_container_width=True, key=f"fin_rt_{sel['id']}"): finalizar('retorno_futuro','Retornar amanhã 14h')
                    with c7:
                        if st.button("❌ Erro número", use_container_width=True, key=f"fin_er_{sel['id']}"): finalizar('nao_atendeu','Número errado')

if st.session_state.leads:
    df_all = pd.DataFrame(st.session_state.leads)
    pend = len(df_all[df_all['status']=='pendente'])
    vendas = len(df_all[df_all['status']=='venda_finalizada'])
    tempo_total = df_all['duracao_seg'].sum()
    tmo = tempo_total / max(len(df_all[df_all['status']!='pendente']),1)
    st.markdown(f"""
    <div class="mini-dash">
      📥 {pend} | ⏱️ TMO {formatar_tempo(tmo)} | 💰 {vendas} vendas
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
with st.expander("📥 Exportar CSV (sem precisar openpyxl)", expanded=False):
    if st.session_state.leads:
        df_all = pd.DataFrame(st.session_state.leads)
        csv = df_all.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Baixar CSV", csv, file_name=f"BRS_v5_2_CLEAN_PRO_{datetime.now().strftime('%d%m%Y_%H%M')}.csv", mime="text/csv", use_container_width=True)
        st.caption("CSV abre no Excel normal, sem precisar openpyxl")

# FIX requirements.txt
with st.expander("🔧 Como corrigir openpyxl no seu Streamlit Cloud"):
    st.code("Adicione no seu requirements.txt:\nstreamlit\npandas\nopenpyxl\n", language="text")
    st.markdown("Depois: GitHub > commit > Streamlit Cloud vai reinstalar automaticamente e o erro some")
