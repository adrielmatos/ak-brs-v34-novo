import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime
import json
import os
from io import BytesIO

st.set_page_config(page_title="A&K BRS v3.4 RANKING", layout="wide", page_icon="🏆")

ARQUIVO_BASE = "brs_base_persistente.json"
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

if 'leads' not in st.session_state:
    st.session_state.leads = carregar_base()
    st.session_state.selected_id = None
    st.session_state.auto_next = True
    st.session_state.call_start = {}

try:
    import openpyxl
    OPENPYXL_OK = True
except:
    OPENPYXL_OK = False

def formatar_tempo(seg):
    if not seg or seg<=0: return "00:00"
    m=int(seg//60); s=int(seg%60)
    return f"{m:02d}:{s:02d}"

def proximo_pendente(atual_id=None):
    pend=[l for l in st.session_state.leads if l['status']=='pendente']
    if not pend: return None
    if not atual_id: return pend[0]['id']
    ids=[l['id'] for l in pend]
    if atual_id not in ids: return pend[0]['id']
    idx=ids.index(atual_id)
    if idx+1 < len(ids): return ids[idx+1]
    return pend[0]['id'] if len(pend)>1 else None

# Header
col_logo, col_auto, col_reset = st.columns([3,1,1])
with col_logo:
    st.markdown("### A&K BRS v3.4 **🏆 RANKING BANCOS + CRONÔMETRO**")
    st.caption(f"💾 {len(st.session_state.leads)} clientes | ⏱️ Cronômetro | 🏆 Ranking Bancos")
with col_auto:
    st.session_state.auto_next = st.checkbox("⏭️ Auto-pular", value=True)
with col_reset:
    if st.button("🗑️ RESETAR", use_container_width=True):
        if os.path.exists(ARQUIVO_BASE): os.remove(ARQUIVO_BASE)
        st.session_state.leads=[]; st.session_state.selected_id=None; st.session_state.call_start={}; st.rerun()

# Import
st.markdown("#### 1️⃣ IMPORTAÇÃO")
tab_csv, tab_xlsx, tab_backup = st.tabs(["📄 CSV", "📊 XLSX 40 bancos", "💾 BACKUP"])
def processar_df(df):
    df.columns=[str(c).upper().strip() for c in df.columns]
    col_nome=next((c for c in df.columns if 'NOME' in c), df.columns[0])
    col_cpf=next((c for c in df.columns if 'CPF' in c), None)
    col_tel=next((c for c in df.columns if 'TELEFONE' in c or c=='TEL' or 'CEL' in c), None)
    col_banco=next((c for c in df.columns if 'BANCO' in c), None)
    existentes=set([l['id'] for l in st.session_state.leads])
    novos=[]; dup=0
    for idx, row in df.iterrows():
        cpf=str(row.get(col_cpf,'')).strip() if col_cpf else f"semcpf{idx}"
        tel=str(row.get(col_tel,'')).strip() if col_tel else ''
        if not tel or tel.lower()=='nan' or len(tel)<8: continue
        h=hashlib.sha256(f"{cpf}{tel}".encode()).hexdigest()[:12]
        if h in existentes: dup+=1; continue
        existentes.add(h)
        novos.append({"id":h,"nome":str(row.get(col_nome,f'Lead {idx}'))[:40],"cpf":cpf,"telefone":tel,"banco":str(row.get(col_banco,'PAN')).upper()[:20] if col_banco else 'PAN',"produto":str(row.get('PRODUTO','FGTS')),"status":"pendente","tentativas":0,"ultima":"Nunca","duracao_seg":0,"duracao_txt":"00:00","inicio_lig":"","fim_lig":""})
    return novos, dup, len(df)

with tab_csv:
    up=st.file_uploader("CSV", type=["csv"], key="csv")
    if up:
        df=pd.read_csv(up); novos,dup,tot=processar_df(df)
        st.session_state.leads.extend(novos); salvar_base()
        st.success(f"✅ {tot} lidos • {len(novos)} novos • Total {len(st.session_state.leads)}")
        if novos and not st.session_state.selected_id: st.session_state.selected_id=novos[0]['id']
with tab_xlsx:
    if not OPENPYXL_OK: st.error("openpyxl instalando - Use CSV")
    else:
        up=st.file_uploader("XLSX", type=["xlsx","xls"], key="xlsx")
        if up:
            df=pd.read_excel(up, engine='openpyxl'); novos,dup,tot=processar_df(df)
            st.session_state.leads.extend(novos); salvar_base()
            st.success(f"✅ XLSX {tot} lidos • {len(novos)} novos")
with tab_backup:
    if st.session_state.leads:
        st.download_button("⬇️ BACKUP JSON", json.dumps(st.session_state.leads, ensure_ascii=False, indent=2).encode('utf-8'), file_name=f"BACKUP_{datetime.now().strftime('%d%m%Y_%H%M')}.json", mime="application/json", type="primary", use_container_width=True)
    up=st.file_uploader("Restaurar JSON", type=["json"], key="backup")
    if up:
        st.session_state.leads=json.load(up); salvar_base(); st.success("✅ Restaurado"); st.rerun()

# Lista
st.markdown("#### 2️⃣ QUEM FALTA LIGAR")
if not st.session_state.leads:
    st.warning("Importe CSV")
else:
    counts={"todos":len(st.session_state.leads),"pendentes":len([l for l in st.session_state.leads if l['status']=='pendente']),"atendidos":len([l for l in st.session_state.leads if l['status']=='atendido']),"nao_at":len([l for l in st.session_state.leads if l['status']=='nao_atendeu']),"retornos":len([l for l in st.session_state.leads if l['status']=='retorno_futuro']),"vendas":len([l for l in st.session_state.leads if l['status']=='venda_finalizada'])}
    c1,c2,c3,c4,c5,c6=st.columns(6)
    c1.metric("TOTAL",counts['todos']); c2.metric("🔴 FALTAM",counts['pendentes']); c3.metric("🟢 ATEND",counts['atendidos']); c4.metric("🔴 NÃO AT",counts['nao_at']); c5.metric("🟠 RET",counts['retornos']); c6.metric("💰 VENDAS",counts['vendas'])
    col_list, col_disc = st.columns([1,1.8])
    with col_list:
        filtro=st.radio("Filtro", ["PENDENTES","ATENDIDOS","NÃO ATENDEU","RETORNOS","VENDAS","TODOS"], label_visibility="collapsed", index=0)
        busca=st.text_input("Buscar", placeholder="Nome, banco", label_visibility="collapsed")
        lista=[]
        for l in st.session_state.leads:
            if filtro=="PENDENTES" and l['status']!='pendente': continue
            if filtro=="ATENDIDOS" and l['status']!='atendido': continue
            if filtro=="NÃO ATENDEU" and l['status']!='nao_atendeu': continue
            if filtro=="RETORNOS" and l['status']!='retorno_futuro': continue
            if filtro=="VENDAS" and l['status']!='venda_finalizada': continue
            if busca and busca.lower() not in l['nome'].lower() and busca.lower() not in l['banco'].lower(): continue
            lista.append(l)
        st.caption(f"{len(lista)} clientes")
        for lead in lista[:300]:
            dot={"pendente":"⚪","atendido":"🟢","nao_atendeu":"🔴","retorno_futuro":"🟠","venda_finalizada":"💰"}[lead['status']]
            dur=f" ⏱️{lead.get('duracao_txt','')}" if lead.get('duracao_seg',0)>0 else ""
            is_sel=lead['id']==st.session_state.selected_id
            if st.button(f"{'👉 ' if is_sel else ''}{dot} {lead['nome'][:18]} • {lead['banco']}{dur}", key=lead['id'], use_container_width=True, type="primary" if is_sel else "secondary"):
                st.session_state.selected_id=lead['id']; st.rerun()
    with col_disc:
        if not st.session_state.selected_id:
            st.info("👈 Clique cliente")
        else:
            sel=next((l for l in st.session_state.leads if l['id']==st.session_state.selected_id), None)
            if sel:
                st.markdown(f"#### 3️⃣ DISCAR • **{sel['nome']}** • {sel['banco']}")
                em_ligacao=sel['id'] in st.session_state.call_start
                if not em_ligacao:
                    if st.button("▶️ INICIAR LIGAÇÃO + CRONÔMETRO", key=f"start_{sel['id']}", type="primary", use_container_width=True):
                        st.session_state.call_start[sel['id']]=datetime.now(); st.rerun()
                    numero=''.join(filter(str.isdigit, sel['telefone']))
                    st.markdown(f'<a href="tel:{numero}" style="display:block;background:#222;color:#00e5ff;padding:12px;border-radius:10px;text-align:center;font-weight:700;text-decoration:none;border:1px solid #00e5ff">📱 LIGAR SEM CRONÔMETRO</a>', unsafe_allow_html=True)
                else:
                    inicio=st.session_state.call_start[sel['id']]
                    decorrido=(datetime.now()-inicio).total_seconds()
                    st.warning(f"⏱️ EM LIGAÇÃO: {formatar_tempo(decorrido)} • {inicio.strftime('%H:%M:%S')}")
                    numero=''.join(filter(str.isdigit, sel['telefone']))
                    st.markdown(f'<a href="tel:{numero}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:18px;border-radius:14px;text-align:center;font-weight:900;text-decoration:none">📱 LIGAR AGORA • {sel["telefone"]} • ⏱️ {formatar_tempo(decorrido)}</a>', unsafe_allow_html=True)
                    if st.button("🔄 Atualizar tempo", key=f"ref_{sel['id']}"): st.rerun()

                def marcar_com_tempo(novo_status):
                    fim=datetime.now(); duracao=0; inicio_str=""
                    if sel['id'] in st.session_state.call_start:
                        inicio=st.session_state.call_start[sel['id']]
                        duracao=(fim-inicio).total_seconds()
                        inicio_str=inicio.strftime("%d/%m %H:%M:%S")
                        del st.session_state.call_start[sel['id']]
                    sel['status']=novo_status; sel['tentativas']+=1; sel['ultima']=fim.strftime("%d/%m %H:%M")
                    sel['duracao_seg']=int(duracao); sel['duracao_txt']=formatar_tempo(duracao); sel['inicio_lig']=inicio_str; sel['fim_lig']=fim.strftime("%d/%m %H:%M:%S")
                    salvar_base()
                    if st.session_state.auto_next:
                        st.session_state.selected_id=proximo_pendente(sel['id'])
                        st.toast(f"✅ {novo_status} • ⏱️ {formatar_tempo(duracao)} • ⏭️", icon="⏭️")
                    st.rerun()
                c1,c2,c3,c4=st.columns(4)
                with c1:
                    if st.button("✅ ATENDEU", key=f"at_{sel['id']}", use_container_width=True, type="primary"): marcar_com_tempo('atendido')
                with c2:
                    if st.button("❌ NÃO AT.", key=f"na_{sel['id']}", use_container_width=True): marcar_com_tempo('nao_atendeu')
                with c3:
                    if st.button("🟠 RETORNO", key=f"re_{sel['id']}", use_container_width=True): marcar_com_tempo('retorno_futuro')
                with c4:
                    if st.button("💰 VENDA", key=f"ve_{sel['id']}", use_container_width=True): st.balloons(); marcar_com_tempo('venda_finalizada')

# 4️⃣ RELATÓRIO COM RANKING BANCOS
st.markdown("#### 4️⃣ RELATÓRIO + 🏆 RANKING BANCOS")

if not st.session_state.leads:
    st.info("Importe para gerar relatório")
else:
    df_all = pd.DataFrame(st.session_state.leads)
    
    # Calcula ranking bancos
    ranking_lig = df_all[df_all['status']!='pendente'].groupby('banco').size().reset_index(name='TOTAL LIGAÇÕES').sort_values('TOTAL LIGAÇÕES', ascending=False)
    ranking_vendas = df_all[df_all['status']=='venda_finalizada'].groupby('banco').size().reset_index(name='VENDAS').sort_values('VENDAS', ascending=False)
    ranking_atendeu = df_all[df_all['status']=='atendido'].groupby('banco').size().reset_index(name='ATENDIDOS').sort_values('ATENDIDOS', ascending=False)
    ranking_tempo = df_all.groupby('banco')['duracao_seg'].sum().reset_index().rename(columns={'duracao_seg':'TEMPO_TOTAL_SEG'})
    ranking_tempo['TEMPO_TOTAL']=ranking_tempo['TEMPO_TOTAL_SEG'].apply(formatar_tempo)
    ranking_tempo = ranking_tempo.sort_values('TEMPO_TOTAL_SEG', ascending=False)
    
    # Merge completo ranking
    ranking_completo = pd.merge(ranking_lig, ranking_vendas, on='banco', how='outer').fillna(0)
    ranking_completo = pd.merge(ranking_completo, ranking_atendeu, on='banco', how='outer').fillna(0)
    ranking_completo = pd.merge(ranking_completo, ranking_tempo[['banco','TEMPO_TOTAL','TEMPO_TOTAL_SEG']], on='banco', how='outer').fillna(0)
    # Taxa conversão
    ranking_completo['TAXA CONVERSÃO %'] = (ranking_completo['VENDAS'] / ranking_completo['TOTAL LIGAÇÕES'] * 100).round(1)
    ranking_completo = ranking_completo.sort_values('TOTAL LIGAÇÕES', ascending=False)
    
    # Mostra ranking visual
    col_rank1, col_rank2 = st.columns(2)
    with col_rank1:
        st.markdown("##### 🏆 RANKING - MAIS LIGAÇÕES POR BANCO")
        st.dataframe(ranking_lig.head(10), use_container_width=True, hide_index=True)
        st.bar_chart(ranking_lig.set_index('banco').head(10))
        
        st.markdown("##### 💰 RANKING - MAIS VENDAS POR BANCO")
        if len(ranking_vendas)>0:
            st.dataframe(ranking_vendas.head(10), use_container_width=True, hide_index=True)
            st.bar_chart(ranking_vendas.set_index('banco').head(10))
        else:
            st.info("Nenhuma venda ainda")
    
    with col_rank2:
        st.markdown("##### ⏱️ RANKING - MAIS TEMPO EM LIGAÇÃO POR BANCO")
        st.dataframe(ranking_tempo[['banco','TEMPO_TOTAL','TEMPO_TOTAL_SEG']].head(10), use_container_width=True, hide_index=True)
        
        st.markdown("##### 📊 RANKING COMPLETO - LIGAÇÕES x VENDAS x CONVERSÃO")
        st.dataframe(ranking_completo[['banco','TOTAL LIGAÇÕES','VENDAS','ATENDIDOS','TEMPO_TOTAL','TAXA CONVERSÃO %']].head(15), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    col_filtro_rep, col_gerar = st.columns([1,2])
    with col_filtro_rep:
        tipo_rel = st.selectbox("Tipo relatório:", ["COMPLETO + RANKING BANCOS", "SÓ ATENDIDOS", "SÓ NÃO ATENDEU", "SÓ VENDAS", "SÓ RETORNOS", "SÓ PENDENTES", "RESUMO + RANKING"], index=0)
    with col_gerar:
        if st.button("📊 GERAR EXCEL COM RANKING BANCOS", type="primary", use_container_width=True):
            df_filtrado = df_all
            if "ATENDIDOS" in tipo_rel: df_filtrado = df_all[df_all['status']=='atendido']
            elif "NÃO ATENDEU" in tipo_rel: df_filtrado = df_all[df_all['status']=='nao_atendeu']
            elif "VENDAS" in tipo_rel: df_filtrado = df_all[df_all['status']=='venda_finalizada']
            elif "RETORNOS" in tipo_rel: df_filtrado = df_all[df_all['status']=='retorno_futuro']
            elif "PENDENTES" in tipo_rel: df_filtrado = df_all[df_all['status']=='pendente']
            
            st.success(f"✅ {tipo_rel}: {len(df_filtrado)} registros")
            
            if not OPENPYXL_OK:
                st.download_button("⬇️ CSV", df_filtrado.to_csv(index=False).encode('utf-8'), file_name=f"BRS_{tipo_rel}_{datetime.now().strftime('%d%m%Y')}.csv", mime="text/csv", use_container_width=True)
            else:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_all.to_excel(writer, sheet_name='GERAL_TODOS', index=False)
                    df_filtrado.to_excel(writer, sheet_name=tipo_rel[:30], index=False)
                    # Abas por tipo
                    df_all[df_all['status']=='pendente'].to_excel(writer, sheet_name='PENDENTES', index=False)
                    df_all[df_all['status']=='atendido'].to_excel(writer, sheet_name='ATENDIDOS', index=False)
                    df_all[df_all['status']=='nao_atendeu'].to_excel(writer, sheet_name='NAO_ATENDEU', index=False)
                    df_all[df_all['status']=='venda_finalizada'].to_excel(writer, sheet_name='VENDAS', index=False)
                    df_all[df_all['status']=='retorno_futuro'].to_excel(writer, sheet_name='RETORNOS', index=False)
                    # RANKING BANCOS - NOVO
                    ranking_completo.to_excel(writer, sheet_name='RANKING_BANCOS', index=False)
                    ranking_lig.to_excel(writer, sheet_name='RANK_LIGACOES', index=False)
                    ranking_vendas.to_excel(writer, sheet_name='RANK_VENDAS', index=False)
                    ranking_tempo.to_excel(writer, sheet_name='RANK_TEMPO', index=False)
                    
                    # Resumo
                    resumo = []
                    for status in ['pendente','atendido','nao_atendeu','retorno_futuro','venda_finalizada']:
                        f = df_all[df_all['status']==status]
                        resumo.append({"STATUS":status,"QTD":len(f),"TEMPO_TOTAL":formatar_tempo(f['duracao_seg'].sum())})
                    pd.DataFrame(resumo).to_excel(writer, sheet_name='RESUMO', index=False)
                
                st.download_button(f"⬇️ BAIXAR EXCEL COMPLETO COM RANKING BANCOS - 10 ABAS", output.getvalue(), file_name=f"BRS_RANKING_BANCOS_{datetime.now().strftime('%d%m%Y_%H%M')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, type="primary")
            
            # Preview ranking
            st.markdown("##### Prévia Ranking Completo:")
            st.dataframe(ranking_completo.head(10), use_container_width=True, hide_index=True)
