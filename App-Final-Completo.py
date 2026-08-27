import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime
from io import BytesIO
import json
import os

st.set_page_config(page_title="A&K BRS v3.4 PERSISTENTE", layout="wide", page_icon="📞")

# --- PERSISTÊNCIA ---
ARQUIVO_BASE = "brs_base_persistente.json"

def salvar_base():
    try:
        with open(ARQUIVO_BASE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.leads, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def carregar_base():
    if os.path.exists(ARQUIVO_BASE):
        try:
            with open(ARQUIVO_BASE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

# --- INIT ---
if 'leads' not in st.session_state:
    # Tenta carregar do arquivo
    base_carregada = carregar_base()
    st.session_state.leads = base_carregada
    st.session_state.selected_id = None
    if base_carregada:
        st.toast(f"✅ Base recuperada: {len(base_carregada)} clientes salvos!", icon="💾")

try:
    import openpyxl
    OPENPYXL_OK = True
except:
    OPENPYXL_OK = False

col_logo, col_reset = st.columns([4,1])
with col_logo:
    st.markdown("### A&K Soluções Financeiras (BRS) **v3.4 PERSISTENTE - NÃO APAGA MAIS**")
    if st.session_state.leads:
        st.caption(f"💾 Base salva automaticamente | {len(st.session_state.leads)} clientes na memória permanente | CSV 100% + XLSX 40 bancos | tel: integrado")
    else:
        st.caption("💾 Persistência ativada | Salva automático mesmo com F5 ou fechar página | CSV 100% + XLSX 40 bancos")
with col_reset:
    if st.button("🗑️ RESETAR BASE", use_container_width=True):
        if os.path.exists(ARQUIVO_BASE):
            os.remove(ARQUIVO_BASE)
        st.session_state.leads = []
        st.session_state.selected_id = None
        st.toast("Base apagada permanentemente", icon="🗑️")
        st.rerun()

# Mostra status persistência
if st.session_state.leads:
    st.success(f"💾 **PERSISTÊNCIA ATIVA:** {len(st.session_state.leads)} clientes salvos. Pode dar F5 ou fechar a página que NÃO APAGA. Último salvamento: {datetime.now().strftime('%d/%m %H:%M:%S')}")

# ETAPA 1 - IMPORTAÇÃO DUAL
st.markdown("#### 1️⃣ IMPORTAÇÃO DUAL - 2 FORMAS (com persistência)")

tab_csv, tab_xlsx, tab_backup = st.tabs(["📄 FORMA 1: CSV", "📊 FORMA 2: XLSX (40 bancos)", "💾 BACKUP / RESTAURAR"])

def processar_df(df):
    df.columns = [str(c).upper().strip() for c in df.columns]
    col_nome = next((c for c in df.columns if 'NOME' in c), df.columns[0])
    col_cpf = next((c for c in df.columns if 'CPF' in c), None)
    col_tel = next((c for c in df.columns if 'TELEFONE' in c or c=='TEL' or 'CEL' in c), None)
    col_banco = next((c for c in df.columns if 'BANCO' in c), None)
    existentes = set([l['id'] for l in st.session_state.leads])
    novos = []
    duplicados = 0
    for idx, row in df.iterrows():
        cpf = str(row.get(col_cpf, '')).strip() if col_cpf else f"semcpf{idx}"
        tel = str(row.get(col_tel, '')).strip() if col_tel else ''
        if not tel or tel.lower() == 'nan' or len(tel) < 8:
            continue
        h = hashlib.sha256(f"{cpf}{tel}".encode()).hexdigest()[:12]
        if h in existentes:
            duplicados += 1
            continue
        existentes.add(h)
        novos.append({
            "id": h, "nome": str(row.get(col_nome, f'Lead {idx}'))[:40],
            "cpf": cpf, "telefone": tel, "banco": str(row.get(col_banco, 'PAN'))[:20] if col_banco else 'PAN',
            "produto": str(row.get('PRODUTO','FGTS')), "status": "pendente", "tentativas": 0, "ultima": "Nunca",
        })
    return novos, duplicados, len(df)

with tab_csv:
    up_csv = st.file_uploader("Arraste CSV", type=["csv"], key="csv")
    if up_csv:
        df = pd.read_csv(up_csv)
        novos, dup, tot = processar_df(df)
        st.session_state.leads.extend(novos)
        salvar_base()
        st.success(f"✅ CSV: {tot} lidos • {dup} duplicados • {len(novos)} novos • Total: {len(st.session_state.leads)} • 💾 SALVO AUTOMATICAMENTE")
        if novos and not st.session_state.selected_id:
            st.session_state.selected_id = novos[0]['id']

with tab_xlsx:
    if not OPENPYXL_OK:
        st.error("❌ openpyxl ainda instalando - Use CSV por enquanto - Mesmo assim salva automático")
    else:
        st.success("✅ XLSX liberado - 40 bancos")
        up_xlsx = st.file_uploader("Arraste XLSX/XLS", type=["xlsx","xls"], key="xlsx")
        if up_xlsx:
            df = pd.read_excel(up_xlsx, engine='openpyxl')
            novos, dup, tot = processar_df(df)
            st.session_state.leads.extend(novos)
            salvar_base()
            st.success(f"✅ XLSX: {tot} lidos • {dup} dup • {len(novos)} novos • Total: {len(st.session_state.leads)} • 💾 SALVO")

with tab_backup:
    st.markdown("**💾 Como não perder nunca (mesmo fechando navegador):**")
    st.info("O app já salva automático em `brs_base_persistente.json` e aguenta F5. Mas se você limpar cache do navegador ou o Streamlit reiniciar, use esse backup:")
    
    if st.session_state.leads:
        # Exportar backup JSON
        backup_json = json.dumps(st.session_state.leads, ensure_ascii=False, indent=2)
        st.download_button("⬇️ BAIXAR BACKUP COMPLETO (JSON) - Guarda no PC", backup_json.encode('utf-8'), file_name=f"BACKUP_BRS_{datetime.now().strftime('%d%m%Y_%H%M')}.json", mime="application/json", type="primary", use_container_width=True)
        
        df_exp = pd.DataFrame(st.session_state.leads)
        st.download_button("⬇️ BAIXAR BACKUP CSV (abre no Excel)", df_exp.to_csv(index=False).encode('utf-8'), file_name=f"BACKUP_BRS_{datetime.now().strftime('%d%m%Y')}.csv", mime="text/csv", use_container_width=True)
    
    st.markdown("**Restaurar backup:**")
    up_backup = st.file_uploader("Arraste seu backup JSON aqui para restaurar", type=["json"], key="backup")
    if up_backup:
        try:
            leads_restore = json.load(up_backup)
            st.session_state.leads = leads_restore
            salvar_base()
            st.success(f"✅ Backup restaurado: {len(leads_restore)} clientes • 💾 Salvo permanentemente")
            st.rerun()
        except Exception as e:
            st.error(f"Erro restore: {e}")

# ETAPA 2
st.markdown("#### 2️⃣ QUEM FALTA LIGAR + QUANTIDADE (persistente)")

if not st.session_state.leads:
    st.warning("👆 Importe CSV ou XLSX - Vai ficar salvo mesmo com F5")
else:
    counts = {
        "todos": len(st.session_state.leads),
        "pendentes": len([l for l in st.session_state.leads if l['status']=='pendente']),
        "ligados": len([l for l in st.session_state.leads if l['status']!='pendente']),
        "retornos": len([l for l in st.session_state.leads if l['status']=='retorno_futuro']),
        "vendas": len([l for l in st.session_state.leads if l['status']=='venda_finalizada']),
    }
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("TOTAL BASE", counts['todos'], f"{counts['pendentes']} pendentes")
    c2.metric("🔴 FALTAM LIGAR", counts['pendentes'], "PERSISTENTE", delta_color="inverse")
    c3.metric("🟢 JÁ LIGADOS", counts['ligados'])
    c4.metric("🟠 RETORNOS", counts['retornos'])
    c5.metric("💰 VENDAS", counts['vendas'])
    
    st.markdown(f"## 📞 FALTAM LIGAR: **{counts['pendentes']}** de {counts['todos']} | 💾 Salvo permanente")

    col_list, col_disc = st.columns([1,1.6])
    with col_list:
        filtro = st.radio("Filtro", ["PENDENTES - FALTA LIGAR","TODOS","LIGADOS","RETORNOS","VENDAS"], label_visibility="collapsed", index=0)
        busca = st.text_input("Buscar", placeholder="Nome, banco, telefone", label_visibility="collapsed")
        lista = []
        for l in st.session_state.leads:
            if filtro == "PENDENTES - FALTA LIGAR" and l['status']!='pendente': continue
            if filtro == "LIGADOS" and l['status']=='pendente': continue
            if filtro == "RETORNOS" and l['status']!='retorno_futuro': continue
            if filtro == "VENDAS" and l['status']!='venda_finalizada': continue
            if busca and busca.lower() not in l['nome'].lower() and busca.lower() not in l['banco'].lower(): continue
            lista.append(l)
        st.caption(f"Mostrando {len(lista)} - CLIQUE PARA LIGAR")
        for lead in lista[:300]:
            dot = {"pendente":"⚪","atendido":"🟢","nao_atendeu":"🔴","retorno_futuro":"🟠","venda_finalizada":"💰"}[lead['status']]
            if st.button(f"{dot} {lead['nome'][:22]} • {lead['banco']} • {lead['telefone']}", key=lead['id'], use_container_width=True):
                st.session_state.selected_id = lead['id']

    with col_disc:
        if not st.session_state.selected_id:
            st.info("👈 Clique cliente à esquerda")
        else:
            sel = next((l for l in st.session_state.leads if l['id']==st.session_state.selected_id), None)
            if sel:
                st.markdown(f"#### 3️⃣ DISCAR • **{sel['nome']}**")
                st.write(f"{sel['banco']} • {sel['telefone']} • CPF: {sel['cpf']}")
                numero = ''.join(filter(str.isdigit, sel['telefone']))
                st.markdown(f'<a href="tel:{numero}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:20px;border-radius:14px;text-align:center;font-weight:900;text-decoration:none;font-size:20px;margin:14px 0">📱 LIGAR AGORA • {sel["telefone"]}</a>', unsafe_allow_html=True)
                c1,c2,c3,c4 = st.columns(4)
                if c1.button("✅ ATENDIDO", key=f"at_{sel['id']}", use_container_width=True, type="primary"):
                    sel['status']='atendido'; sel['tentativas']+=1; salvar_base(); st.rerun()
                if c2.button("❌ NÃO AT.", key=f"na_{sel['id']}", use_container_width=True):
                    sel['status']='nao_atendeu'; sel['tentativas']+=1; salvar_base(); st.rerun()
                if c3.button("🟠 RETORNO", key=f"re_{sel['id']}", use_container_width=True):
                    sel['status']='retorno_futuro'; sel['tentativas']+=1; salvar_base(); st.rerun()
                if c4.button("💰 VENDA", key=f"ve_{sel['id']}", use_container_width=True):
                    sel['status']='venda_finalizada'; sel['tentativas']+=1; salvar_base(); st.balloons(); st.rerun()

st.markdown("#### 4️⃣ RELATÓRIO")
if st.session_state.leads:
    if st.button("📊 GERAR RELATÓRIO BRS", type="primary", use_container_width=True):
        df_export = pd.DataFrame(st.session_state.leads)
        if not OPENPYXL_OK:
            st.download_button("⬇️ BAIXAR CSV", df_export.to_csv(index=False).encode('utf-8'), file_name=f"BRS_{datetime.now().strftime('%d%m%Y')}.csv", mime="text/csv", use_container_width=True)
        else:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, sheet_name='GERAL', index=False)
                df_export[df_export['status']=='pendente'].to_excel(writer, sheet_name='PENDENTES_FALTA_LIGAR', index=False)
                df_export[df_export['status']=='atendido'].to_excel(writer, sheet_name='ATENDIDOS', index=False)
                df_export[df_export['status']=='nao_atendeu'].to_excel(writer, sheet_name='NAO_ATENDIDOS', index=False)
                df_export[df_export['status']=='venda_finalizada'].to_excel(writer, sheet_name='VENDAS', index=False)
            st.download_button("⬇️ BAIXAR EXCEL 5 ABAS", output.getvalue(), file_name=f"BRS_{datetime.now().strftime('%d%m%Y')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, type="primary")
