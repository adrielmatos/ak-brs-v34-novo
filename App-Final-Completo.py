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
import streamlit.components.v1 as components

st.set_page_config(page_title="Discadora Eletrônica A&K", layout="wide", page_icon="📞")

BANCO_EMOJI = {
    "PAN": "🟢", "SAFRA": "🟠", "BMG": "🔵", "C6": "⚫", "ITAU": "🔷", "ITAÚ": "🔷",
    "OLE": "🟡", "ORIGINAL": "🟢", "BRADESCO": "🔴", "BB": "🟡", "CAIXA": "🔵",
    "AGIBANK": "🔵", "WILL": "🟡", "NEON": "🔵", "FACTA": "🔷", "DEFAULT": "⚪"
}

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
    st.markdown("""
    <style>
    .login-container {display:flex;justify-content:center;align-items:center;min-height:80vh;}
    .login-card {background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);padding:50px 40px;border-radius:24px;box-shadow:0 20px 60px rgba(0,0,0,0.5);text-align:center;max-width:420px;width:100%;border:1px solid rgba(0,255,136,0.2);}
    </style>
    <div class="login-container"><div class="login-card"><h1 style="color:white;">Discadora Eletrônica<br><span style="color:#00e5ff;">A&K</span></h1></div></div>
    """, unsafe_allow_html=True)
    col1,col2,col3=st.columns([1,1.2,1])
    with col2:
        senha = st.text_input("🔒 Senha", type="password")
        if st.button("🚀 Entrar", type="primary", use_container_width=True):
            senha_correta = st.secrets.get("APP_PASSWORD", None) if GITHUB_TOKEN else "1234"
            if senha == senha_correta:
                st.session_state.logado = True
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
                    return d.get("leads",[]), d.get("pausas",[]), set(d.get("bloqueados",[])), d.get("lotes",[]), d.get("nao_perturbe",[]), d.get("meta_diaria",20)
            except:
                return [],[],set(),[],[],20
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
    payload={"leads":st.session_state.leads,"pausas":st.session_state.pausas,"bloqueados":list(st.session_state.blocklist),"lotes":st.session_state.lotes,"nao_perturbe":st.session_state.nao_perturbe,"meta_diaria":st.session_state.get("meta_diaria",20)}
    conteudo_str=json.dumps(payload, ensure_ascii=False, indent=2)
    if not GITHUB_API or not GITHUB_TOKEN:
        with open("brs_dados_local.json","w",encoding="utf-8") as f:
            f.write(conteudo_str)
        return
    try:
        conteudo_b64=base64.b64encode(conteudo_str.encode("utf-8")).decode("utf-8")
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        body={"message": f"Discadora A&K {datetime.now().strftime('%d/%m %H:%M:%S')}","content": conteudo_b64}
        if st.session_state.get("_gh_sha"):
            body["sha"]=st.session_state["_gh_sha"]
        r=requests.put(GITHUB_API, headers=headers, json=body)
        if r.status_code in (200,201):
            st.session_state["_gh_sha"]=r.json()["content"]["sha"]
    except Exception as e:
        st.warning(f"Não salvou GitHub: {e}")

if "leads" not in st.session_state:
    leads,pausas,blocklist,lotes,nao_perturbe,meta_diaria=carregar_dados()
    for l in leads:
        if "notas_cliente" not in l:
            l["notas_cliente"] = ""
        if "arquivado_motivo" not in l:
            l["arquivado_motivo"] = ""
        if "retorno_hora" not in l:
            l["retorno_hora"] = ""
    st.session_state.leads=leads
    st.session_state.pausas=pausas
    st.session_state.blocklist=blocklist
    st.session_state.lotes=lotes
    st.session_state.nao_perturbe=nao_perturbe
    st.session_state.meta_diaria=meta_diaria
    st.session_state.selected_id=None
    st.session_state.auto_next=True
    st.session_state.call_start={}
    st.session_state.filtro_banco="TODOS"
    st.session_state.filtro_status="PENDENTES"
    st.session_state.filtro_tentativas="TODAS"
    st.session_state.ordenar_por="NUNCA LIGADOS PRIMEIRO"
    st.session_state.filtro_ddd="TODOS"
    st.session_state.em_pausa=None
    st.session_state.pausa_inicio=None
    st.session_state.modo_foco=False
    st.session_state.busca_global=""
    st.session_state.confirm_arquivar=None
    st.session_state.filtro_vendas_hoje=False
    st.session_state.copied_number=""

def formatar_tempo(seg):
    if not seg or seg<=0:
        return "00:00"
    m=int(seg//60)
    s=int(seg%60)
    if m>=60:
        h=m//60
        m=m%60
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def proximo_inteligente(atual_id=None):
    pend=[l for l in st.session_state.leads if l["status"]=="pendente"]
    if not pend:
        return None
    def score(l):
        tent=l.get("tentativas",0)
        nunca=0 if l.get("ultima")=="Nunca" else 1000
        return nunca + tent*10
    pend_sorted=sorted(pend, key=score)
    if not atual_id:
        return pend_sorted[0]["id"]
    ids=[l["id"] for l in pend_sorted]
    if atual_id not in ids:
        return pend_sorted[0]["id"]
    idx=ids.index(atual_id)
    if idx+1 < len(ids):
        return ids[idx+1]
    return pend_sorted[0]["id"] if len(pend_sorted)>1 else None

def retornos_hoje():
    hoje=datetime.now().strftime("%d/%m/%Y")
    return [l for l in st.session_state.leads if l.get("status")=="retorno_futuro" and l.get("retorno_data")==hoje]

def ler_xlsx_sem_openpyxl(file_bytes):
    try:
        import openpyxl
        return pd.read_excel(BytesIO(file_bytes), engine='openpyxl')
    except ImportError:
        pass
    try:
        z=zipfile.ZipFile(BytesIO(file_bytes))
        try:
            ss_data=z.read('xl/sharedStrings.xml')
            ss_root=ET.fromstring(ss_data)
            ns={'main':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            shared_strings=[]
            for si in ss_root.findall('main:si', ns):
                t=si.find('main:t', ns)
                if t is not None:
                    shared_strings.append(t.text if t.text else "")
                else:
                    txt=""
                    for t in si.findall('.//main:t', ns):
                        if t.text:
                            txt+=t.text
                    shared_strings.append(txt)
        except:
            shared_strings=[]
        try:
            sheet_data=z.read('xl/worksheets/sheet1.xml')
            sheet_root=ET.fromstring(sheet_data)
            ns={'main':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            rows=[]
            for row in sheet_root.findall('.//main:row', ns):
                cols=[]
                for c in row.findall('main:c', ns):
                    v=c.find('main:v', ns)
                    if v is not None and v.text:
                        if c.get('t')=='s' and shared_strings:
                            try:
                                idx=int(v.text)
                                cols.append(shared_strings[idx] if idx < len(shared_strings) else v.text)
                            except:
                                cols.append(v.text)
                        else:
                            cols.append(v.text)
                    else:
                        is_elem=c.find('main:is', ns)
                        if is_elem is not None:
                            t=is_elem.find('main:t', ns)
                            cols.append(t.text if t is not None and t.text else "")
                        else:
                            cols.append("")
                rows.append(cols)
            if rows:
                header=rows[0]
                data=rows[1:]
                max_cols=max(len(r) for r in rows)
                for r in data:
                    while len(r)<max_cols:
                        r.append("")
                df=pd.DataFrame(data, columns=header[:max_cols] if len(header)>=max_cols else header + [f"COL_{i}" for i in range(len(header), max_cols)])
                return df
        except Exception:
            pass
        raise ValueError("Conversor falhou")
    except zipfile.BadZipFile:
        raise ValueError("XLSX inválido")

def ler_planilha(up):
    nome=up.name.lower()
    file_bytes=up.read()
    up.seek(0)
    if nome.endswith(".xlsx"):
        try:
            return ler_xlsx_sem_openpyxl(file_bytes)
        except Exception as e:
            raise ValueError(f"{up.name}: {e}")
    elif nome.endswith(".xls"):
        try:
            return pd.read_excel(BytesIO(file_bytes), engine='xlrd')
        except:
            return pd.read_excel(BytesIO(file_bytes))
    for enc in ["utf-8","latin1","cp1252","iso-8859-1"]:
        for sep in [",",";","\t","|"]:
            try:
                df=pd.read_csv(BytesIO(file_bytes), encoding=enc, sep=sep)
                if len(df.columns)>1:
                    return df
            except:
                continue
    raise ValueError(f"{up.name}: Não consegui ler")

def montar_novos_leads(df, existentes, bloqueados, nao_perturbe_set, nome_lote):
    df.columns=[str(c).upper().strip() for c in df.columns]
    col_nome=next((c for c in df.columns if "NOME" in c), df.columns[0])
    col_cpf=next((c for c in df.columns if "CPF" in c), None)
    col_tel=next((c for c in df.columns if "TELEFONE" in c or c=="TEL" or "CEL" in c or "FONE" in c), None)
    col_banco=next((c for c in df.columns if "BANCO" in c), None)
    novos=[]
    ig_tel=ig_bloq=ig_dup=ig_ddd=ig_np=0
    for idx,row in df.iterrows():
        cpf=str(row.get(col_cpf,"")).strip() if col_cpf else f"semcpf{idx}"
        tel_raw=str(row.get(col_tel,"")).strip() if col_tel else ""
        tel="".join(filter(str.isdigit, tel_raw))
        if not tel or len(tel)<10:
            ig_tel+=1
            continue
        try:
            ddd=int(tel[:2])
            if ddd<11 or ddd>91:
                ig_ddd+=1
                continue
        except:
            ig_ddd+=1
            continue
        if tel in bloqueados or tel in nao_perturbe_set:
            if tel in nao_perturbe_set:
                ig_np+=1
            else:
                ig_bloq+=1
            continue
        h=hashlib.sha256(f"{cpf}{tel}".encode()).hexdigest()[:12]
        if h in existentes:
            ig_dup+=1
            continue
        existentes.add(h)
        novos.append({"id":h,"nome":str(row.get(col_nome,f"Lead {idx}"))[:40],"cpf":cpf,"telefone":tel,"banco":str(row.get(col_banco,"PAN")).upper()[:20] if col_banco else "PAN","produto":"FGTS","status":"pendente","tentativas":0,"ultima":"Nunca","duracao_seg":0,"duracao_txt":"00:00","historico":[],"tabulacao":"","observacao":"","notas_cliente":"","arquivado_motivo":"","retorno_hora":"","canal":"chip","custo_estimado":0.0,"retorno_data":None,"lote":nome_lote,"data_import":datetime.now().strftime("%d/%m %H:%M"),"ddd":tel[:2]})
    return novos, ig_tel, ig_bloq, ig_dup, ig_ddd, ig_np

# CSS LIMPO - SEM DIVS QUE QUEBRAM BOTÕES
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
html, body, [class*="css"] {font-family:'Space Grotesk', sans-serif;}
.block-container {padding-bottom:100px !important;}
section[data-testid="stSidebar"] {background:linear-gradient(180deg,#0f0c29,#1a1a2e); border-right:1px solid rgba(0,255,136,0.15);}
.lead-card {background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);border:1px solid rgba(0,229,255,0.2);border-radius:16px;padding:16px;margin-bottom:14px;}
.obs-box {background:rgba(255,204,0,0.08);border:1px solid rgba(255,204,0,0.3);border-radius:12px;padding:12px;margin-top:10px;}
.hist-timeline {background:rgba(0,229,255,0.05);border-left:3px solid #00e5ff;padding:8px 12px 8px 16px;margin:6px 0;border-radius:0 8px 8px 0;}
.retorno-card {background:linear-gradient(135deg,#2a1a0e,#3d2a14);border:1px solid #ff8c00;border-radius:12px;padding:12px;margin-bottom:10px;color:white;}
.foco-overlay {background:linear-gradient(135deg,#0f0c29,#302b63);border:2px solid #00ff88;border-radius:20px;padding:24px;color:white;}
@keyframes pulse-green {0%{box-shadow:0 0 0 0 rgba(0,255,136,0.7);}70%{box-shadow:0 0 0 10px rgba(0,255,136,0);}100%{box-shadow:0 0 0 0 rgba(0,255,136,0);}}
.t0-pulse {animation:pulse-green 2s infinite !important; border:1px solid #00ff88 !important;}
</style>
""", unsafe_allow_html=True)

total=len(st.session_state.leads)
pend=len([l for l in st.session_state.leads if l["status"]=="pendente"])
nunca=len([l for l in st.session_state.leads if l["status"]=="pendente" and l.get("ultima")=="Nunca"])
vendas=len([l for l in st.session_state.leads if l["status"]=="venda_finalizada"])
vendas_hoje=len([l for l in st.session_state.leads if l["status"]=="venda_finalizada" and datetime.now().strftime("%d/%m") in l.get("ultima","")])
retornos=retornos_hoje()
retornos_total=len([l for l in st.session_state.leads if l["status"]=="retorno_futuro"])
arquivados=len([l for l in st.session_state.leads if l["status"]=="arquivado"])
atendidos=len([l for l in st.session_state.leads if l["status"]=="atendido"])
nao_atendeu=len([l for l in st.session_state.leads if l["status"]=="nao_atendeu"])

with st.sidebar:
    st.markdown("## 🔍 Filtros")
    st.session_state.busca_global = st.text_input("Busca", value=st.session_state.get("busca_global",""), placeholder="Nome, banco, telefone...")
    bancos_disponiveis = sorted(list(set([l["banco"] for l in st.session_state.leads]))) if st.session_state.leads else []
    st.session_state.filtro_banco = st.selectbox("Banco", ["TODOS"]+bancos_disponiveis, index=0, key="f_banco_side")
    st.session_state.filtro_status = st.selectbox("Status", ["PENDENTES","ATENDIDOS","NÃO ATENDEU","RETORNOS","VENDAS","VENDAS HOJE","ARQUIVADOS","TODOS","QUARENTENA"], index=0, key="f_status_side")
    st.session_state.filtro_tentativas = st.selectbox("Tentativas", ["TODAS","NUNCA LIGADOS (T0)","T1","T2","T3+","T0+T1","T2+"], index=0, key="f_tent_side")
    st.session_state.ordenar_por = st.selectbox("Ordenar", ["NUNCA LIGADOS PRIMEIRO","MENOS TENTATIVAS","MAIS TENTATIVAS","NOME A-Z"], index=0, key="f_ord_side")
    ddds=sorted(list(set([l.get("ddd","") for l in st.session_state.leads if l.get("ddd")])) ) if st.session_state.leads else []
    st.session_state.filtro_ddd = st.selectbox("DDD", ["TODOS"]+ddds, index=0, key="f_ddd_side")
    st.divider()
    meta = st.session_state.get("meta_diaria",20)
    nova_meta = st.number_input("Meta diária", min_value=1, max_value=100, value=meta, key="meta_side")
    if nova_meta != meta:
        st.session_state.meta_diaria = nova_meta
        salvar_dados()
    st.progress(min(100, int(vendas_hoje/nova_meta*100))/100 if nova_meta>0 else 0)
    st.caption(f"{vendas_hoje}/{nova_meta} vendas")
    st.divider()
    if st.button("🧹 Limpar Filtros", use_container_width=True, key="clear_side"):
        st.session_state.filtro_banco="TODOS"
        st.session_state.filtro_status="PENDENTES"
        st.session_state.filtro_tentativas="TODAS"
        st.session_state.filtro_ddd="TODOS"
        st.session_state.ordenar_por="NUNCA LIGADOS PRIMEIRO"
        st.session_state.busca_global=""
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
    st.caption(f"📱 {total} | 📥 {pend} | 💰 {vendas}")

st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f0c29 0%,#302b63 50%,#24243e 100%);padding:18px 22px;border-radius:16px;color:white;margin-bottom:12px;border:1px solid rgba(0,255,136,0.15);">
<div style="display:flex;justify-content:space-between;align-items:center;">
<div style="display:flex;align-items:center;gap:12px;">
<div style="background:linear-gradient(135deg,#00e5ff,#00ff88);width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px;">📞</div>
<div><h1 style="margin:0;font-size:20px;font-weight:800;">Discadora Eletrônica <span style="color:#00e5ff;">A&K</span></h1><p style="margin:0;opacity:0.6;font-size:10px;">Sistema Profissional • KPIs clicáveis • Filtros na lateral</p></div>
</div>
<div style="text-align:right;"><p style="margin:0;font-size:10px;opacity:0.5;">{datetime.now().strftime('%d/%m/%Y %H:%M')}</p><span style="font-size:11px;color:#00ff88;">● Online</span></div>
</div>
</div>
""", unsafe_allow_html=True)

# KPIs CLICÁVEIS - BOTÕES CURTOS SEM CORTAR - TESTADO
c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
with c1:
    if st.button(f"{total}\nTOTAL", key="kpi_total", use_container_width=True, type="primary" if st.session_state.filtro_status=="TODOS" else "secondary"):
        st.session_state.filtro_status="TODOS"
        st.session_state.filtro_banco="TODOS"
        st.session_state.filtro_tentativas="TODAS"
        st.session_state.filtro_ddd="TODOS"
        st.session_state.busca_global=""
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
with c2:
    if st.button(f"{pend}\nPENDENTES", key="kpi_pend", use_container_width=True, type="primary" if st.session_state.filtro_status=="PENDENTES" and not st.session_state.filtro_vendas_hoje else "secondary"):
        st.session_state.filtro_status="PENDENTES"
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
with c3:
    if st.button(f"{nunca}\nNUNCA", key="kpi_nunca", use_container_width=True, type="primary" if st.session_state.filtro_tentativas=="NUNCA LIGADOS (T0)" else "secondary"):
        st.session_state.filtro_status="PENDENTES"
        st.session_state.filtro_tentativas="NUNCA LIGADOS (T0)"
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
with c4:
    if st.button(f"{vendas}\nVENDAS", key="kpi_vendas", use_container_width=True, type="primary" if st.session_state.filtro_status=="VENDAS" and not st.session_state.filtro_vendas_hoje else "secondary"):
        st.session_state.filtro_status="VENDAS"
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
with c5:
    if st.button(f"{vendas_hoje}\nHOJE", key="kpi_hoje", use_container_width=True, type="primary" if st.session_state.filtro_vendas_hoje else "secondary"):
        st.session_state.filtro_status="VENDAS"
        st.session_state.filtro_vendas_hoje=True
        st.rerun()
with c6:
    if st.button(f"{retornos_total}\nRETORNOS", key="kpi_ret", use_container_width=True, type="primary" if st.session_state.filtro_status=="RETORNOS" else "secondary"):
        st.session_state.filtro_status="RETORNOS"
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
with c7:
    if st.button(f"{arquivados}\nARQUIV", key="kpi_arq", use_container_width=True, type="primary" if st.session_state.filtro_status=="ARQUIVADOS" else "secondary"):
        st.session_state.filtro_status="ARQUIVADOS"
        st.session_state.filtro_vendas_hoje=False
        st.rerun()

st.caption(f"Filtro: {st.session_state.filtro_status} | Banco: {st.session_state.filtro_banco} | DDD: {st.session_state.filtro_ddd} | Clique nos KPIs acima para filtrar")

if retornos:
    st.warning(f"⏰ {len(retornos)} retorno(s) hoje!")

tab1, tab_ret, tab2, tab3 = st.tabs(["🎯 DISCADOR", "⏰ RETORNOS", "📦 LOTES", "📊 RELATÓRIOS"])

with tab1:
    col_h1,col_h2=st.columns([3,1])
    with col_h1:
        st.checkbox("⏭️ Auto Next", value=True, key="auto_next_check")
        st.session_state.auto_next = st.session_state.auto_next_check
    with col_h2:
        if st.button("🧠 Próximo Inteligente", use_container_width=True, type="primary", key="prox_inteligente"):
            nxt=proximo_inteligente(st.session_state.selected_id)
            if nxt:
                st.session_state.selected_id=nxt
                st.session_state.modo_foco=False
                st.rerun()

    # FILTRO LÓGICA
    lista=[]
    for l in st.session_state.leads:
        if st.session_state.get("filtro_vendas_hoje"):
            if l["status"]!="venda_finalizada":
                continue
            if datetime.now().strftime("%d/%m") not in l.get("ultima",""):
                continue
        else:
            if st.session_state.filtro_banco!="TODOS" and l["banco"]!=st.session_state.filtro_banco:
                continue
            if st.session_state.filtro_status=="PENDENTES" and l["status"]!="pendente":
                continue
            if st.session_state.filtro_status=="ATENDIDOS" and l["status"]!="atendido":
                continue
            if st.session_state.filtro_status=="NÃO ATENDEU" and l["status"]!="nao_atendeu":
                continue
            if st.session_state.filtro_status=="RETORNOS" and l["status"]!="retorno_futuro":
                continue
            if st.session_state.filtro_status=="VENDAS" and l["status"]!="venda_finalizada":
                continue
            if st.session_state.filtro_status=="ARQUIVADOS" and l["status"]!="arquivado":
                continue
            if st.session_state.filtro_status=="QUARENTENA" and not (l.get("tentativas",0)>=3 and "caixa" in l.get("observacao","").lower()):
                continue
        tent=l.get("tentativas",0)
        ultima=l.get("ultima","Nunca")
        ft=st.session_state.filtro_tentativas
        if ft=="NUNCA LIGADOS (T0)" and ultima!="Nunca":
            continue
        if ft=="T1" and tent!=1:
            continue
        if ft=="T2" and tent!=2:
            continue
        if ft=="T3+" and tent<3:
            continue
        if ft=="T0+T1" and tent>1:
            continue
        if ft=="T2+" and tent<2:
            continue
        if st.session_state.filtro_ddd!="TODOS" and l.get("ddd","")!=st.session_state.filtro_ddd:
            continue
        busca=st.session_state.get("busca_global","")
        if busca and busca.lower() not in l["nome"].lower() and busca.lower() not in l["banco"].lower() and busca.lower() not in l.get("lote","").lower() and busca.lower() not in l["telefone"]:
            continue
        lista.append(l)
    
    if st.session_state.ordenar_por=="NUNCA LIGADOS PRIMEIRO":
        lista=sorted(lista, key=lambda x: (0 if x.get("ultima")=="Nunca" else 1, x.get("tentativas",0)))
    elif st.session_state.ordenar_por=="MENOS TENTATIVAS":
        lista=sorted(lista, key=lambda x: x.get("tentativas",0))
    elif st.session_state.ordenar_por=="MAIS TENTATIVAS":
        lista=sorted(lista, key=lambda x: x.get("tentativas",0), reverse=True)

    def registrar_evento(sel,status_final,obs_pronta,retorno_data=None, retorno_hora=None):
        fim=datetime.now()
        dur=0
        if sel["id"] in st.session_state.call_start:
            dur=(fim-st.session_state.call_start[sel["id"]]).total_seconds()
            del st.session_state.call_start[sel["id"]]
        sel["status"]=status_final
        sel["tentativas"]=sel.get("tentativas",0)+1
        sel["ultima"]=fim.strftime("%d/%m %H:%M")
        sel["duracao_seg"]=int(dur)
        sel["duracao_txt"]=formatar_tempo(dur)
        sel["observacao"]=obs_pronta
        sel["tabulacao"]=obs_pronta[:30]
        sel["retorno_data"]=retorno_data
        sel["retorno_hora"]=retorno_hora or ""
        historico=sel.get("historico") or []
        historico.append({"data":fim.strftime("%d/%m %H:%M:%S"),"acao":status_final,"tempo":formatar_tempo(dur),"tab":obs_pronta, "retorno": f"{retorno_data} {retorno_hora}" if retorno_data else ""})
        sel["historico"]=historico
        salvar_dados()
        st.session_state.modo_foco=False
        if st.session_state.auto_next and status_final!="retorno_futuro":
            st.session_state.selected_id=proximo_inteligente(sel["id"])
        st.rerun()

    def arquivar_lead(sel, motivo="Já foi ligado"):
        sel["status"]="arquivado"
        sel["arquivado_motivo"]=motivo
        sel["ultima"]=datetime.now().strftime("%d/%m %H:%M")
        historico=sel.get("historico") or []
        historico.append({"data":datetime.now().strftime("%d/%m %H:%M:%S"),"acao":"arquivado","tempo":"00:00","tab":motivo})
        sel["historico"]=historico
        salvar_dados()
        st.session_state.confirm_arquivar=None
        st.session_state.selected_id=proximo_inteligente(sel["id"])
        st.rerun()

    modo_foco_ativo=st.session_state.modo_foco and st.session_state.selected_id in st.session_state.call_start if st.session_state.selected_id else False

    if modo_foco_ativo:
        sel=next((l for l in st.session_state.leads if l["id"]==st.session_state.selected_id), None)
        if sel:
            st.markdown('<div class="foco-overlay">', unsafe_allow_html=True)
            st.markdown(f"## 🎯 {sel['nome']} | {sel['banco']}")
            decorrido=(datetime.now()-st.session_state.call_start[sel["id"]]).total_seconds()
            st.markdown(f"### ⏱️ {formatar_tempo(decorrido)} | 📱 {sel['telefone']}")
            st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:20px;border-radius:14px;text-align:center;font-weight:900;text-decoration:none;font-size:22px;">📱 {sel["telefone"]}</a>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            c1,c2,c3,c4=st.columns(4)
            with c1:
                if st.button("✅ Atendeu", use_container_width=True, type="primary", key=f"foco_at_{sel['id']}"):
                    registrar_evento(sel,"atendido","Atendeu")
            with c2:
                if st.button("📬 Caixa Postal", use_container_width=True, key=f"foco_cx_{sel['id']}"):
                    registrar_evento(sel,"nao_atendeu","Caixa postal")
            with c3:
                if st.button("📵 Desligado", use_container_width=True, key=f"foco_des_{sel['id']}"):
                    registrar_evento(sel,"nao_atendeu","Desligado")
            with c4:
                if st.button("💰 Venda!", use_container_width=True, key=f"foco_vd_{sel['id']}"):
                    st.balloons()
                    registrar_evento(sel,"venda_finalizada","Venda")
            if st.button("🔙 Sair", use_container_width=True, key=f"foco_sair_{sel['id']}"):
                st.session_state.modo_foco=False
                st.rerun()
    else:
        col_lista,col_atend=st.columns([1,2])
        with col_lista:
            if len(lista)==0:
                st.info("Nenhum lead encontrado")
                if st.button("🧹 Limpar Filtros", use_container_width=True, key="clear_empty"):
                    st.session_state.filtro_banco="TODOS"
                    st.session_state.filtro_status="PENDENTES"
                    st.session_state.filtro_tentativas="TODAS"
                    st.session_state.filtro_ddd="TODOS"
                    st.session_state.busca_global=""
                    st.session_state.filtro_vendas_hoje=False
                    st.rerun()
            else:
                st.markdown(f"**📋 Fila ({len(lista)})**")
                page_size=30
                total_pags=(len(lista)//page_size)+1
                pag=st.selectbox(f"Pág {total_pags} ({page_size}/pág)", [f"{i*page_size+1}-{(i+1)*page_size}" for i in range(total_pags)], key="pag_disc")
                idx_pag=int(pag.split("-")[0])//page_size if pag else 0
                for lead in lista[idx_pag*page_size:(idx_pag+1)*page_size]:
                    is_sel=lead["id"]==st.session_state.selected_id
                    tent=lead.get("tentativas",0)
                    ultima=lead.get("ultima","Nunca")
                    eh_t0 = ultima=="Nunca" and tent==0
                    tent_txt=f" T{tent}" if tent>0 else " 🆕 T0" if eh_t0 else ""
                    tem_obs = "📝" if lead.get("notas_cliente") else ""
                    emoji_banco = BANCO_EMOJI.get(lead["banco"], "⚪")
                    dot = {"pendente":"⚪","atendido":"🟢","nao_atendeu":"🔴","retorno_futuro":"🟠","venda_finalizada":"💰","arquivado":"📁"}.get(lead["status"],"⚪")
                    label = f"{'👉' if is_sel else ''}{dot}{tem_obs} {emoji_banco} {lead['nome'][:10]} {tent_txt}"
                    if st.button(label, key=f"list_{lead['id']}", use_container_width=True, type="primary" if is_sel else "secondary"):
                        st.session_state.selected_id=lead["id"]
                        st.session_state.modo_foco=False
                        st.rerun()
        with col_atend:
            if not st.session_state.selected_id:
                st.info("👈 Selecione cliente na fila • Clique nos KPIs acima para filtrar")
                st.markdown('<div class="lead-card">', unsafe_allow_html=True)
                st.markdown("""
                **KPIs clicáveis funcionando:**
                - TOTAL: todos leads
                - PENDENTES: só pendentes
                - NUNCA: só nunca ligados (pulsando verde)
                - VENDAS: todas vendas
                - HOJE: vendas de hoje
                - RETORNOS: retornos futuros
                - ARQUIV: arquivados
                """)
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                sel=next((l for l in st.session_state.leads if l["id"]==st.session_state.selected_id), None)
                if sel:
                    emoji_banco = BANCO_EMOJI.get(sel["banco"], "⚪")
                    st.markdown('<div class="lead-card">', unsafe_allow_html=True)
                    st.markdown(f"### {emoji_banco} {sel['nome']} | 🏦 {sel['banco']} | T{sel.get('tentativas',0)}")
                    st.markdown(f"**📱 {sel['telefone']}** | CPF: {sel.get('cpf','')} | DDD: {sel.get('ddd','')} | Lote: {sel.get('lote','')[:20]}")
                    st.markdown(f"Status: **{sel['status'].upper()}** | Última: {sel.get('ultima','Nunca')} | Tentativas: {sel.get('tentativas',0)}")
                    
                    # Botão copiar simples que funciona - sem components.html
                    col_tel1, col_tel2 = st.columns([2,1])
                    with col_tel1:
                        st.code(sel['telefone'], language=None)
                    with col_tel2:
                        if st.button("📋 Copiar número", key=f"copy_{sel['id']}", use_container_width=True):
                            st.session_state.copied_number = sel['telefone']
                            st.success(f"Copiado: {sel['telefone']}")
                    
                    if sel["telefone"] in st.session_state.nao_perturbe:
                        st.error("🚫 Não Perturbe")
                    else:
                        em_ligacao=sel["id"] in st.session_state.call_start
                        if not em_ligacao:
                            c1,c2,c3=st.columns([1.2,1,1])
                            with c1:
                                if st.button(f"▶️ LIGAR {sel['telefone']}", key=f"discar_{sel['id']}", type="primary", use_container_width=True):
                                    st.session_state.call_start[sel["id"]]=datetime.now()
                                    st.session_state.modo_foco=True
                                    st.rerun()
                            with c2:
                                msg=f"Olá {sel['nome']}, A&K FGTS {sel['banco']} liberado"
                                msg_enc=urllib.parse.quote(msg)
                                st.markdown(f'<a href="https://wa.me/55{sel["telefone"]}?text={msg_enc}" target="_blank" style="display:block;background:#25D366;color:#fff;padding:10px;border-radius:8px;text-align:center;font-weight:700;text-decoration:none">💬 Zap {sel["banco"]}</a>', unsafe_allow_html=True)
                            with c3:
                                if st.button("🚫 Bloquear", key=f"bloq_{sel['id']}", use_container_width=True):
                                    st.session_state.blocklist.add(sel["telefone"])
                                    salvar_dados()
                                    st.rerun()
                        else:
                            decorrido=(datetime.now()-st.session_state.call_start[sel["id"]]).total_seconds()
                            st.warning(f"📱 EM LIGAÇÃO: {formatar_tempo(decorrido)}")
                    
                    st.markdown("**⚡ Tabulação**")
                    c1,c2,c3,c4=st.columns(4)
                    with c1:
                        if st.button("✅ Atendeu", use_container_width=True, key=f"at_{sel['id']}"):
                            registrar_evento(sel,"atendido","Atendeu")
                    with c2:
                        if st.button("📬 Caixa Postal", use_container_width=True, key=f"cx_{sel['id']}"):
                            registrar_evento(sel,"nao_atendeu","Caixa postal")
                    with c3:
                        if st.button("📵 Desligado", use_container_width=True, key=f"des_{sel['id']}"):
                            registrar_evento(sel,"nao_atendeu","Desligado")
                    with c4:
                        if st.button("💰 Venda!", use_container_width=True, key=f"vd_{sel['id']}"):
                            st.balloons()
                            registrar_evento(sel,"venda_finalizada","Venda")
                    c5,c6,c7,c8=st.columns(4)
                    with c5:
                        if st.button("🤔 Sem interesse", use_container_width=True, key=f"si_{sel['id']}"):
                            registrar_evento(sel,"atendido","Sem interesse")
                    with c6:
                        if st.button("❌ Errado", use_container_width=True, key=f"er_{sel['id']}"):
                            registrar_evento(sel,"nao_atendeu","Número errado")
                    with c7:
                        if st.session_state.confirm_arquivar == sel["id"]:
                            if st.button("✅ Confirmar ocultar", key=f"conf_sim_{sel['id']}", type="primary", use_container_width=True):
                                arquivar_lead(sel, "Já liguei")
                        else:
                            if st.button("📁 Já liguei", use_container_width=True, key=f"arq_{sel['id']}"):
                                st.session_state.confirm_arquivar = sel["id"]
                                st.rerun()
                    with c8:
                        if st.button("🔄 Pendentes", use_container_width=True, key=f"vol_{sel['id']}"):
                            sel["status"]="pendente"
                            salvar_dados()
                            st.rerun()
                    
                    with st.expander("📅 Agendar Retorno"):
                        col_dt1, col_dt2 = st.columns(2)
                        with col_dt1:
                            data_ret = st.date_input("Data", value=date.today()+timedelta(days=1), min_value=date.today(), key=f"data_ret_{sel['id']}")
                        with col_dt2:
                            hora_ret = st.time_input("Hora", value=time(14,0), key=f"hora_ret_{sel['id']}")
                        motivo_ret = st.text_input("Motivo", key=f"motivo_ret_{sel['id']}")
                        if st.button(f"✅ Agendar {data_ret.strftime('%d/%m')} {hora_ret.strftime('%H:%M')}", key=f"conf_ret_{sel['id']}", type="primary", use_container_width=True):
                            registrar_evento(sel,"retorno_futuro", f"Retorno {data_ret.strftime('%d/%m/%Y')} {hora_ret.strftime('%H:%M')} - {motivo_ret}", retorno_data=data_ret.strftime("%d/%m/%Y"), retorno_hora=hora_ret.strftime("%H:%M"))
                    st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown('<div class="obs-box">', unsafe_allow_html=True)
                    st.markdown("**📝 Observações**")
                    notas_atual = sel.get("notas_cliente","")
                    novas_notas = st.text_area("Obs", value=notas_atual, placeholder="Ex: Tem 2 cartões...", key=f"notas_{sel['id']}", label_visibility="collapsed", height=80)
                    if st.button("💾 Salvar Obs", key=f"save_obs_{sel['id']}", use_container_width=True):
                        sel["notas_cliente"] = novas_notas
                        salvar_dados()
                        st.success("Salvo!")
                    st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown('<div class="lead-card">', unsafe_allow_html=True)
                    st.markdown(f"**📊 Histórico - {sel['nome']}**")
                    hist = sel.get("historico") or []
                    c1,c2,c3,c4=st.columns(4)
                    with c1: st.metric("Ligações", len(hist))
                    with c2: st.metric("Atendeu", len([h for h in hist if h.get("acao")=="atendido"]))
                    with c3: st.metric("Caixa", len([h for h in hist if "caixa" in h.get("tab","").lower()]))
                    with c4: st.metric("Tempo", formatar_tempo(sel.get("duracao_seg",0)))
                    if hist:
                        for h in hist[::-1][:8]:
                            acao_icon = {"atendido":"✅","nao_atendeu":"🔴","venda_finalizada":"💰","retorno_futuro":"⏰","arquivado":"📁"}.get(h.get("acao"),"📞")
                            ret_txt = h.get("retorno","")
                            ret_display = f" | 📅 {ret_txt}" if ret_txt else ""
                            st.markdown(f"<div class='hist-timeline'><b>{acao_icon} {h.get('data','')}</b> | {h.get('acao','').upper()} | {h.get('tab','')[:50]}{ret_display}</div>", unsafe_allow_html=True)
                    else:
                        st.caption("🆕 Nunca ligado")
                    st.markdown('</div>', unsafe_allow_html=True)

with tab_ret:
    st.markdown("## ⏰ Retornos Futuros")
    retornos_all = [l for l in st.session_state.leads if l["status"]=="retorno_futuro"]
    if not retornos_all:
        st.info("Nenhum retorno agendado")
    else:
        for lead in sorted(retornos_all, key=lambda x: x.get("retorno_data","")):
            st.markdown(f'<div class="retorno-card">', unsafe_allow_html=True)
            st.markdown(f"**{lead['nome']} | {lead['banco']} | {lead['telefone']}** - 📅 {lead.get('retorno_data','')} {lead.get('retorno_hora','')} - {lead.get('observacao','')[:50]}")
            c1,c2=st.columns(2)
            with c1:
                if st.button("▶️ Ligar", key=f"ligar_ret_{lead['id']}", type="primary", use_container_width=True):
                    st.session_state.selected_id=lead["id"]
                    st.rerun()
            with c2:
                if st.button("📥 Pendentes", key=f"pend_ret_{lead['id']}", use_container_width=True):
                    lead["status"]="pendente"
                    salvar_dados()
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown("## 📦 Lotes")
    arquivos=st.file_uploader("Arraste planilhas", type=["csv","xlsx","xls"], accept_multiple_files=True, key="import_lotes")
    if arquivos:
        dfs=[]
        for arq in arquivos:
            try:
                dfs.append((arq.name, ler_planilha(arq)))
            except Exception as e:
                st.error(f"{arq.name}: {e}")
        if dfs:
            if st.button("✅ IMPORTAR TUDO", type="primary", use_container_width=True, key="import_all"):
                existentes=set([l["id"] for l in st.session_state.leads])
                nao_pert_set=set(st.session_state.nao_perturbe)
                total_importados=0
                for nome,df in dfs:
                    lote_id=hashlib.sha256(f"{nome}{datetime.now()}".encode()).hexdigest()[:8]
                    novos,ig_tel,ig_bloq,ig_dup,ig_ddd,ig_np=montar_novos_leads(df.copy(), existentes, st.session_state.blocklist, nao_pert_set, nome)
                    st.session_state.leads.extend(novos)
                    total_importados+=len(novos)
                    st.session_state.lotes.append({"id":lote_id,"nome":nome,"data":datetime.now().strftime("%d/%m %H:%M:%S"),"qtd":len(df),"importados":len(novos)})
                salvar_dados()
                st.success(f"✅ {total_importados} importados")
                st.rerun()

with tab3:
    st.markdown("## 📊 Relatórios")
    if st.session_state.leads:
        df_all=pd.DataFrame(st.session_state.leads)
        c1,c2,c3=st.columns(3)
        with c1: st.metric("Conversão", f"{len(df_all[df_all['status']=='venda_finalizada'])/max(len(df_all[df_all['status']!='pendente']),1)*100:.1f}%")
        with c2: st.metric("Tempo Total", formatar_tempo(df_all["duracao_seg"].sum()))
        with c3: st.metric("Arquivados", len(df_all[df_all["status"]=="arquivado"]))
        st.bar_chart(df_all["status"].value_counts())
        csv=df_all.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ CSV Geral", csv, file_name=f"BRS_{datetime.now().strftime('%d%m%Y')}.csv", mime="text/csv", use_container_width=True)

# JS PULSANDO - SEM BLACK BOX
components.html("""
<script>
function addPulse(){
 try{
  const doc=window.parent.document;
  doc.querySelectorAll('button').forEach(btn=>{
   if(btn.innerText.includes('🆕') && btn.innerText.includes('T0') && !btn.classList.contains('t0-pulse')){
    btn.classList.add('t0-pulse');
   }
  });
 }catch(e){}
}
setInterval(addPulse,1000);
setTimeout(addPulse,600);
</script>
""", height=0)
