import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, timedelta
import json
import os
from io import BytesIO
import time

st.set_page_config(page_title="A&K BRS v5.1 CHIP", layout="wide", page_icon="📱")

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
    st.session_state.modo_discador = "POWER (chip) - Auto 3s"
    st.session_state.em_pausa = None
    st.session_state.pausa_inicio = None
    st.session_state.preview_timer = None

try:
    import openpyxl
    OPENPYXL_OK = True
except:
    OPENPYXL_OK = False

def formatar_tempo(seg):
    if not seg or seg<=0: return "00:00"
    m=int(seg//60); s=int(seg%60)
    if m>=60:
        h=m//60; m=m%60
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def proximo_pendente(atual_id=None, banco_filtro="TODOS"):
    pend=[l for l in st.session_state.leads if l['status']=='pendente' and (banco_filtro=="TODOS" or l['banco']==banco_filtro)]
    if not pend:
        pend=[l for l in st.session_state.leads if l['status']=='pendente']
    if not pend: return None
    if not atual_id: return pend[0]['id']
    ids=[l['id'] for l in pend]
    if atual_id not in ids: return pend[0]['id']
    idx=ids.index(atual_id)
    if idx+1 < len(ids): return ids[idx+1]
    return pend[0]['id'] if len(pend)>1 else None

# HEADER v5.1 SEM PREDITIVO
st.markdown("### 📱 A&K BRS v5.1 **CHIP SAFE** | Power + Preview | Sem Preditivo (100% Seguro Chip Solo)")
col_h1,col_h2,col_h3,col_h4,col_h5 = st.columns([2,1,1,1,1])
with col_h1:
    st.caption(f"📱 {len(st.session_state.leads)} | 🔥 POWER 3s | 👁️ PREVIEW 5s | ⏱️ TMO/TMA/CPC | 🏦 URA Skill | 100% CHIP")
with col_h2:
    # SEM PREDITIVO
    st.session_state.modo_discador = st.selectbox("Discador CHIP", ["POWER (chip) - Auto 3s","PREVIEW (chip) - 5s p/ ler","MANUAL (chip)"], label_visibility="collapsed")
with col_h3:
    st.session_state.auto_next = st.checkbox("⏭️ Auto-pula", value=True)
with col_h4:
    banco_list = ["TODOS"] + sorted(list(set([l['banco'] for l in st.session_state.leads]))) if st.session_state.leads else ["TODOS"]
    st.session_state.filtro_banco = st.selectbox("🏦 URA Skill", banco_list, label_visibility="collapsed")
with col_h5:
    if st.button("🗑️ RESET", use_container_width=True):
        if os.path.exists(ARQUIVO_BASE): os.remove(ARQUIVO_BASE)
        st.session_state.leads=[]; st.session_state.selected_id=None; st.rerun()

# PAUSAS
st.markdown("#### ⏸️ PAUSAS (Joytec) - 100% CHIP")
col_pausa1, col_pausa2, col_pausa3, col_pausa4, col_pausa5, col_pausa_status = st.columns([1,1,1,1,1,2])
em_pausa = st.session_state.em_pausa is not None

with col_pausa1:
    if st.button("☕ Almoço", disabled=em_pausa, use_container_width=True):
        st.session_state.em_pausa="Almoço"; st.session_state.pausa_inicio=datetime.now(); st.rerun()
with col_pausa2:
    if st.button("🚻 Banheiro", disabled=em_pausa, use_container_width=True):
        st.session_state.em_pausa="Banheiro"; st.session_state.pausa_inicio=datetime.now(); st.rerun()
with col_pausa3:
    if st.button("📚 Feedback", disabled=em_pausa, use_container_width=True):
        st.session_state.em_pausa="Feedback"; st.session_state.pausa_inicio=datetime.now(); st.rerun()
with col_pausa4:
    if st.button("💤 Pausa", disabled=em_pausa, use_container_width=True):
        st.session_state.em_pausa="Pausa"; st.session_state.pausa_inicio=datetime.now(); st.rerun()
with col_pausa5:
    if em_pausa:
        if st.button("▶️ Voltar", type="primary", use_container_width=True):
            fim=datetime.now()
            duracao=(fim-st.session_state.pausa_inicio).total_seconds()
            st.session_state.pausas.append({
                "tipo": st.session_state.em_pausa,
                "inicio": st.session_state.pausa_inicio.strftime("%d/%m %H:%M:%S"),
                "fim": fim.strftime("%d/%m %H:%M:%S"),
                "duracao_seg": int(duracao),
                "duracao_txt": formatar_tempo(duracao)
            })
            salvar_pausas(st.session_state.pausas)
            st.session_state.em_pausa=None; st.session_state.pausa_inicio=None; st.rerun()
    else:
        st.button("🟢 Disponível", disabled=True, use_container_width=True)

with col_pausa_status:
    if em_pausa:
        decorrido = (datetime.now()-st.session_state.pausa_inicio).total_seconds()
        st.warning(f"⏸️ EM PAUSA: {st.session_state.em_pausa} há {formatar_tempo(decorrido)}")
    else:
        total_pausas = sum([p['duracao_seg'] for p in st.session_state.pausas])
        st.success(f"🟢 DISPONÍVEL | Pausas hoje: {formatar_tempo(total_pausas)} | Chip pronto")

# IMPORT
st.markdown("#### 1️⃣ IMPORTAÇÃO")
tab_csv, tab_xlsx = st.tabs(["📄 CSV", "📊 XLSX"])
def processar_df(df):
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
        if not tel or tel.lower()=='nan' or len(tel)<8: continue
        h=hashlib.sha256(f"{cpf}{tel}".encode()).hexdigest()[:12]
        if h in existentes: continue
        existentes.add(h)
        novos.append({
            "id":h,"nome":str(row.get(col_nome,f'Lead {idx}'))[:40],"cpf":cpf,"telefone":tel,
            "banco":str(row.get(col_banco,'PAN')).upper()[:20] if col_banco else 'PAN',
            "produto":str(row.get('PRODUTO','FGTS')),"status":"pendente","tentativas":0,"ultima":"Nunca",
            "duracao_seg":0,"duracao_txt":"00:00","inicio_lig":"","fim_lig":"",
            "historico":[],"etiquetas":[],"tabulacao":"","observacao":"","retorno_data":"","canal":"chip",
            "score_ia": 75, "bina_info": f"{str(row.get(col_banco,'PAN')).upper()} - Cliente",
            "custo_estimado": 0.0
        })
    return novos

with tab_csv:
    up=st.file_uploader("CSV", type=["csv"], key="csv")
    if up:
        df=pd.read_csv(up); novos=processar_df(df)
        st.session_state.leads.extend(novos); salvar_base()
        st.success(f"✅ {len(novos)} novos | Chip Safe | Total {len(st.session_state.leads)}")
        if novos: st.session_state.selected_id=novos[0]['id']
with tab_xlsx:
    if not OPENPYXL_OK: st.error("Use CSV")
    else:
        up=st.file_uploader("XLSX", type=["xlsx","xls"], key="xlsx")
        if up:
            df=pd.read_excel(up, engine='openpyxl'); novos=processar_df(df)
            st.session_state.leads.extend(novos); salvar_base()
            st.success(f"✅ {len(novos)} novos")

# KANBAN
st.markdown("#### 2️⃣ KANBAN + URA Skill - CHIP SAFE (Sem risco 2 atenderem)")
if not st.session_state.leads:
    st.warning("Importe leads")
else:
    leads_filtrados = st.session_state.leads
    if st.session_state.filtro_banco != "TODOS":
        leads_filtrados = [l for l in st.session_state.leads if l['banco']==st.session_state.filtro_banco]
    
    total = len(st.session_state.leads)
    pend = len([l for l in st.session_state.leads if l['status']=='pendente'])
    atend = len([l for l in st.session_state.leads if l['status']=='atendido'])
    vendas = len([l for l in st.session_state.leads if l['status']=='venda_finalizada'])
    tempo_total = sum([l.get('duracao_seg',0) for l in st.session_state.leads])
    tmo = tempo_total / max(atend+vendas,1) if total>0 else 0
    cpc = (atend+vendas) / max(total-pend,1) *100 if (total-pend)>0 else 0
    
    c_wall1,c_wall2,c_wall3,c_wall4,c_wall5,c_wall6 = st.columns(6)
    c_wall1.metric("📥 Fila URA", f"{pend} ({st.session_state.filtro_banco})")
    c_wall2.metric("⏱️ TMO", formatar_tempo(tmo))
    c_wall3.metric("📞 TMA", formatar_tempo(tempo_total/max(total-pend,1) if (total-pend)>0 else 0))
    c_wall4.metric("🎯 CPC", f"{cpc:.0f}%")
    c_wall5.metric("📱 Chip", "Online" if not em_pausa else "Pausa")
    c_wall6.metric("⏱️ Falado", formatar_tempo(tempo_total))
    
    kanban_cols = st.columns(5)
    statuses = [("pendente","📥 Fila URA"), ("atendido","✅ Atendidos"), ("nao_atendeu","❌ Caixa/Deslig"), ("retorno_futuro","🟠 Retornos"), ("venda_finalizada","💰 Vendas")]
    for idx, (status_key, status_label) in enumerate(statuses):
        with kanban_cols[idx]:
            lista_status = [l for l in leads_filtrados if l['status']==status_key]
            st.markdown(f"**{status_label}** ({len(lista_status)})")
            for lead in lista_status[:15]:
                is_sel = lead['id']==st.session_state.selected_id
                tempo = f" ⏱️{lead.get('duracao_txt','')}" if lead.get('duracao_seg',0)>0 else ""
                if st.button(f"{lead['nome'][:14]} • {lead['banco']}{tempo}", key=f"kanban_{lead['id']}_{status_key}_{idx}", use_container_width=True, type="primary" if is_sel else "secondary"):
                    st.session_state.selected_id=lead['id']
                    if "PREVIEW" in st.session_state.modo_discador:
                        st.session_state.preview_timer=datetime.now()
                    st.rerun()

# ATENDIMENTO CHIP SAFE
st.markdown("#### 3️⃣ ATENDIMENTO CHIP SAFE - Power 3s + Preview 5s (Sem risco)")
col_list, col_context = st.columns([1,2])

with col_list:
    st.markdown(f"##### 📋 Fila: {st.session_state.filtro_banco} | {st.session_state.modo_discador}")
    filtro_status = st.radio("Status", ["PENDENTES","ATENDIDOS","NÃO ATENDEU","RETORNOS","VENDAS","TODOS"], label_visibility="collapsed", index=0)
    busca = st.text_input("Buscar", placeholder="Nome, banco", label_visibility="collapsed")
    lista=[]
    for l in st.session_state.leads:
        if st.session_state.filtro_banco!="TODOS" and l['banco']!=st.session_state.filtro_banco: continue
        if filtro_status=="PENDENTES" and l['status']!='pendente': continue
        if filtro_status=="ATENDIDOS" and l['status']!='atendido': continue
        if filtro_status=="NÃO ATENDEU" and l['status']!='nao_atendeu': continue
        if filtro_status=="RETORNOS" and l['status']!='retorno_futuro': continue
        if filtro_status=="VENDAS" and l['status']!='venda_finalizada': continue
        if busca and busca.lower() not in l['nome'].lower() and busca.lower() not in l['banco'].lower(): continue
        lista.append(l)
    st.caption(f"{len(lista)} na fila")
    for lead in lista[:120]:
        dot={"pendente":"⚪","atendido":"🟢","nao_atendeu":"🔴","retorno_futuro":"🟠","venda_finalizada":"💰"}[lead['status']]
        is_sel = lead['id']==st.session_state.selected_id
        if st.button(f"{'👉' if is_sel else ''}{dot} {lead['nome'][:16]} • {lead['banco']}", key=f"list_{lead['id']}", use_container_width=True, type="primary" if is_sel else "secondary"):
            st.session_state.selected_id=lead['id']
            if "PREVIEW" in st.session_state.modo_discador:
                st.session_state.preview_timer=datetime.now()
            st.rerun()

with col_context:
    if not st.session_state.selected_id:
        st.info("👈 Clique cliente - Power 3s disca próximo automático com chip, sem risco de 2 atenderem")
    else:
        sel = next((l for l in st.session_state.leads if l['id']==st.session_state.selected_id), None)
        if sel:
            st.markdown(f"##### 📞 **BINA:** **{sel['nome']}** | 🏦 {sel['banco']} | Score {sel.get('score_ia',0)}")
            st.info(f"🔍 BINA: {sel['banco']} - {sel['telefone']} | Tent: {sel['tentativas']} | Última: {sel['ultima']}")
            
            if "PREVIEW" in st.session_state.modo_discador and st.session_state.preview_timer:
                decorrido_preview = (datetime.now()-st.session_state.preview_timer).total_seconds()
                if decorrido_preview < 5:
                    st.warning(f"👁️ PREVIEW CHIP - Lendo script por {5-int(decorrido_preview)}s... Olá {sel['nome']}, sobre {sel['banco']} FGTS...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.success("✅ Preview lido - Pode ligar!")
            
            numero = ''.join(filter(str.isdigit, sel['telefone']))
            em_ligacao = sel['id'] in st.session_state.call_start
            
            if em_pausa:
                st.error(f"⏸️ Em pausa {st.session_state.em_pausa}")
            elif not em_ligacao:
                col_d1, col_d2 = st.columns([1,1])
                with col_d1:
                    if st.button(f"▶️ LIGAR CHIP + ⏱️ ({st.session_state.modo_discador})", key=f"discar_{sel['id']}", type="primary", use_container_width=True):
                        if em_pausa:
                            st.error("Saia da pausa")
                        else:
                            st.session_state.call_start[sel['id']]=datetime.now()
                            st.toast(f"📱 CHIP: {sel['nome']} - {sel['telefone']}", icon="📱")
                            st.rerun()
                with col_d2:
                    st.markdown(f'<a href="https://wa.me/55{numero}?text=Olá {sel["nome"]}, A&K sobre {sel["banco"]}" target="_blank" style="display:block;background:#25D366;color:#fff;padding:10px;border-radius:8px;text-align:center;font-weight:700;text-decoration:none">💬 WhatsApp Chip</a>', unsafe_allow_html=True)
            else:
                decorrido = (datetime.now()-st.session_state.call_start[sel['id']]).total_seconds()
                st.warning(f"📱 CHIP EM LIGAÇÃO: {formatar_tempo(decorrido)} | {sel['nome']} | {sel['banco']}")
                st.markdown(f'<a href="tel:{numero}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:16px;border-radius:12px;text-align:center;font-weight:900;text-decoration:none;font-size:18px">📱 CHIP • {sel["telefone"]} • ⏱️ {formatar_tempo(decorrido)}</a>', unsafe_allow_html=True)
                if st.button("🔄 Atualizar", key=f"ref_{sel['id']}"):
                    st.rerun()

            st.markdown("**📝 Obs + Finalizar (100% CHIP - 1 ligação por vez, sem abandono):**")
            obs = st.text_area("Obs chip", value=sel.get('observacao',''), key=f"obs_{sel['id']}", height=70, placeholder="Atendeu, interessado, caixa, desligado...")
            
            def finalizar_chip(status_final, tabulacao_auto=""):
                fim=datetime.now(); duracao=0; inicio_str=""
                if sel['id'] in st.session_state.call_start:
                    inicio=st.session_state.call_start[sel['id']]
                    duracao=(fim-inicio).total_seconds()
                    inicio_str=inicio.strftime("%d/%m %H:%M:%S")
                    del st.session_state.call_start[sel['id']]
                
                custo = (duracao/60) * 0.15
                sel['status']=status_final
                sel['tentativas']+=1
                sel['ultima']=fim.strftime("%d/%m %H:%M")
                sel['duracao_seg']=int(duracao)
                sel['duracao_txt']=formatar_tempo(duracao)
                sel['inicio_lig']=inicio_str
                sel['fim_lig']=fim.strftime("%d/%m %H:%M:%S")
                sel['observacao']=obs
                sel['tabulacao']=tabulacao_auto if tabulacao_auto else sel.get('tabulacao','')
                sel['custo_estimado']=sel.get('custo_estimado',0)+custo
                sel['canal']='chip'
                
                if 'historico' not in sel: sel['historico']=[]
                sel['historico'].append({
                    "data": fim.strftime("%d/%m %H:%M:%S"),
                    "canal": f"CHIP {sel['banco']} - {st.session_state.modo_discador}",
                    "acao": status_final,
                    "tempo": formatar_tempo(duracao),
                    "obs": obs[:60],
                    "custo": f"R$ {custo:.2f}",
                    "tabulacao": tabulacao_auto
                })
                
                if status_final in ['atendido','venda_finalizada']:
                    sel['score_ia']=min(100, sel.get('score_ia',0)+5)
                
                salvar_base()
                
                if "POWER" in st.session_state.modo_discador and st.session_state.auto_next:
                    st.toast(f"🔥 POWER CHIP: {formatar_tempo(duracao)} | Próximo em 3s...", icon="⚡")
                    time.sleep(3)
                    st.session_state.selected_id=proximo_pendente(sel['id'], st.session_state.filtro_banco)
                    if "PREVIEW" in st.session_state.modo_discador:
                        st.session_state.preview_timer=datetime.now()
                elif st.session_state.auto_next:
                    st.session_state.selected_id=proximo_pendente(sel['id'], st.session_state.filtro_banco)
                    if "PREVIEW" in st.session_state.modo_discador:
                        st.session_state.preview_timer=datetime.now()
                    st.toast(f"📱 CHIP: {status_final} • ⏱️ {formatar_tempo(duracao)} • R$ {custo:.2f}", icon="📱")
                
                st.rerun()

            c1,c2,c3,c4 = st.columns(4)
            with c1:
                if st.button("✅ ATENDEU", key=f"fin_at_{sel['id']}", use_container_width=True, type="primary"):
                    finalizar_chip('atendido', 'Atendeu - Humano')
            with c2:
                if st.button("🔴 CX POSTAL", key=f"fin_cx_{sel['id']}", use_container_width=True):
                    finalizar_chip('nao_atendeu', 'Caixa Postal')
            with c3:
                if st.button("📵 DESLIGADO", key=f"fin_des_{sel['id']}", use_container_width=True):
                    finalizar_chip('nao_atendeu', 'Desligado/Inválido')
            with c4:
                if st.button("💰 VENDA", key=f"fin_ve_{sel['id']}", use_container_width=True):
                    st.balloons()
                    finalizar_chip('venda_finalizada', 'Venda Chip')

            c5,c6,c7,c8 = st.columns(4)
            with c5:
                if st.button("🟠 RETORNO", key=f"fin_re_{sel['id']}", use_container_width=True):
                    finalizar_chip('retorno_futuro', 'Retorno agendado')
            with c6:
                if st.button("❌ SEM INTERESSE", key=f"fin_ni_{sel['id']}", use_container_width=True):
                    finalizar_chip('atendido', 'Sem interesse')
            with c7:
                if st.button("📞 OCUPADO", key=f"fin_oc_{sel['id']}", use_container_width=True):
                    finalizar_chip('nao_atendeu', 'Ocupado')
            with c8:
                if st.button("⏰ AGENDADO", key=f"fin_ra_{sel['id']}", use_container_width=True):
                    finalizar_chip('retorno_futuro', 'Hora marcada')

# DASHBOARD
st.markdown("#### 4️⃣ DASHBOARD CHIP SAFE - Sem Preditivo, sem risco")
if not st.session_state.leads:
    st.inf
