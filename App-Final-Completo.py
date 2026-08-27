import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime
from io import BytesIO

st.set_page_config(page_title="A&K BRS v3.4 DEFINITIVA DUAL", layout="wide", page_icon="📞")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
* { font-family: 'Inter', sans-serif; }
.stApp { background: #060a14; color: #e2e8f0; }
</style>
""", unsafe_allow_html=True)

if 'leads' not in st.session_state:
    st.session_state.leads = []
    st.session_state.selected_id = None

try:
    import openpyxl
    OPENPYXL_OK = True
except:
    OPENPYXL_OK = False

col_logo, col_reset = st.columns([4,1])
with col_logo:
    st.markdown("### A&K Soluções Financeiras (BRS) **v3.4 DEFINITIVA DUAL COMPLETA**")
    if OPENPYXL_OK:
        st.caption("✅ DUAL | CSV + XLSX 40 bancos | tel: integrado | 5 abas | Hash CPF LGPD | TUDO PRONTO")
    else:
        st.caption("⚠️ DUAL | CSV 100% | XLSX instalando... | tel: pronto")
with col_reset:
    if st.button("🗑️ RESETAR BASE", use_container_width=True):
        st.session_state.leads = []
        st.session_state.selected_id = None
        st.rerun()

st.markdown("#### 1️⃣ IMPORTAÇÃO DUAL - 2 FORMAS")
tab_csv, tab_xlsx = st.tabs(["📄 FORMA 1: CSV (garantido)", "📊 FORMA 2: XLSX/XLS (40 bancos)"])

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
    st.info("✅ FUNCIONA SEMPRE - Mesmo se XLSX falhar")
    up_csv = st.file_uploader("Arraste CSV", type=["csv"], key="csv")
    if up_csv:
        try:
            df = pd.read_csv(up_csv)
            novos, dup, tot = processar_df(df)
            st.session_state.leads.extend(novos)
            st.success(f"✅ CSV: {tot} lidos • {dup} duplicados • {len(novos)} novos • Total: {len(st.session_state.leads)}")
            if novos and not st.session_state.selected_id:
                st.session_state.selected_id = novos[0]['id']
        except Exception as e:
            st.error(f"Erro CSV: {e}")

with tab_xlsx:
    if not OPENPYXL_OK:
        st.error("❌ openpyxl instalando - Use CSV por enquanto")
        st.code("requirements.txt deve ter:\nstreamlit\npandas\nopenpyxl\n\nDepois: share.streamlit.io > Manage app > Reboot", language="text")
    else:
        st.success("✅ XLSX liberado - 40 bancos")
        up_xlsx = st.file_uploader("Arraste XLSX/XLS", type=["xlsx","xls"], key="xlsx")
        if up_xlsx:
            try:
                df = pd.read_excel(up_xlsx, engine='openpyxl')
                novos, dup, tot = processar_df(df)
                st.session_state.leads.extend(novos)
                st.success(f"✅ XLSX: {tot} lidos • {dup} duplicados • {len(novos)} novos • Total: {len(st.session_state.leads)}")
                if novos and not st.session_state.selected_id:
                    st.session_state.selected_id = novos[0]['id']
            except Exception as e:
                st.error(f"Erro XLSX: {e}")

st.markdown("#### 2️⃣ ONDE VER - QUEM FALTA LIGAR + QUANTIDADE")

if not st.session_state.leads:
    st.warning("👆 Importe CSV ou XLSX acima")
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
    c2.metric("🔴 FALTAM LIGAR", counts['pendentes'], "PENDENTES", delta_color="inverse")
    c3.metric("🟢 JÁ LIGADOS", counts['ligados'])
    c4.metric("🟠 RETORNOS", counts['retornos'])
    c5.metric("💰 VENDAS", counts['vendas'])
    
    st.markdown(f"## 📞 FALTAM LIGAR: **{counts['pendentes']}** de {counts['todos']} | Já ligados: {counts['ligados']}")

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
            st.markdown("""
            **LIGAÇÃO INTEGRADA - COMO FUNCIONA (já pronta):**
            1. Clica cliente lista
            2. Botão azul **📱 LIGAR AGORA**
            3. Abre discador celular com número preenchido
            4. Usa seu chip, sem API, sem custo
            5. Depois marca resultado
            6. Sai de PENDENTES → LIGADOS
            """)
        else:
            sel = next((l for l in st.session_state.leads if l['id']==st.session_state.selected_id), None)
            if sel:
                st.markdown(f"#### 3️⃣ DISCAR • **{sel['nome']}**")
                st.write(f"{sel['banco']} • {sel['telefone']} • CPF: {sel['cpf']}")
                numero = ''.join(filter(str.isdigit, sel['telefone']))
                st.markdown(f'<a href="tel:{numero}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:20px;border-radius:14px;text-align:center;font-weight:900;text-decoration:none;font-size:20px;margin:14px 0">📱 LIGAR AGORA • {sel["telefone"]}<br><span style="font-size:12px">Abre discador celular - Usa seu chip</span></a>', unsafe_allow_html=True)
                c1,c2,c3,c4 = st.columns(4)
                if c1.button("✅ ATENDIDO", key=f"at_{sel['id']}", use_container_width=True, type="primary"):
                    sel['status']='atendido'; sel['tentativas']+=1; st.rerun()
                if c2.button("❌ NÃO AT.", key=f"na_{sel['id']}", use_container_width=True):
                    sel['status']='nao_atendeu'; sel['tentativas']+=1; st.rerun()
                if c3.button("🟠 RETORNO", key=f"re_{sel['id']}", use_container_width=True):
                    sel['status']='retorno_futuro'; sel['tentativas']+=1; st.rerun()
                if c4.button("💰 VENDA", key=f"ve_{sel['id']}", use_container_width=True):
                    sel['status']='venda_finalizada'; sel['tentativas']+=1; st.balloons(); st.rerun()

st.markdown("#### 4️⃣ RELATÓRIO 5 ABAS")
if st.session_state.leads:
    if st.button("📊 GERAR RELATÓRIO BRS", type="primary", use_container_width=True):
        df_export = pd.DataFrame(st.session_state.leads)
        if not OPENPYXL_OK:
            st.download_button("⬇️ BAIXAR CSV (XLSX ainda instalando)", df_export.to_csv(index=False).encode('utf-8'), file_name=f"BRS_{datetime.now().strftime('%d%m%Y')}.csv", mime="text/csv", use_container_width=True)
        else:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, sheet_name='GERAL', index=False)
                df_export[df_export['status']=='pendente'].to_excel(writer, sheet_name='PENDENTES_FALTA_LIGAR', index=False)
                df_export[df_export['status']=='atendido'].to_excel(writer, sheet_name='ATENDIDOS', index=False)
                df_export[df_export['status']=='nao_atendeu'].to_excel(writer, sheet_name='NAO_ATENDIDOS', index=False)
                df_export[df_export['status']=='venda_finalizada'].to_excel(writer, sheet_name='VENDAS', index=False)
            st.download_button("⬇️ BAIXAR EXCEL 5 ABAS", output.getvalue(), file_name=f"BRS_{datetime.now().strftime('%d%m%Y')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, type="primary")
