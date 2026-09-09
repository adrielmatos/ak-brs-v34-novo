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
    if st.session_state.get("logado"): return True
    st.markdown("""
    <style>
    .login-container {display:flex;justify-content:center;align-items:center;min-height:80vh;}
    .login-card {background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);padding:50px 40px;border-radius:24px;box-shadow:0 20px 60px rgba(0,0,0,0.5);text-align:center;max-width:420px;width:100%;border:1px solid rgba(0,255,136,0.2);}
    .login-card h1 {color:white;font-size:32px;margin:0 0 8px 0;font-weight:800;letter-spacing:-1px;}
    .login-card p {color:#00ff88;font-size:14px;margin:0 0 30px 0;letter-spacing:2px;text-transform:uppercase;font-weight:600;}
    .login-icon {font-size:56px;margin-bottom:16px;display:block;}
    </style>
    <div class="login-container">
    <div class="login-card">
    <span class="login-icon">📞</span>
    <h1>Discadora Eletrônica</h1>
    <h1 style="color:#00e5ff;margin-top:-10px;">A&K</h1>
    <p>Sistema Profissional de Discagem</p>
    </div>
    </div>
    """, unsafe_allow_html=True)
    col1,col2,col3=st.columns([1,1.2,1])
    with col2:
        senha = st.text_input("🔒 Senha de acesso", type="password", placeholder="Digite sua senha")
        if st.button("🚀 Entrar no Sistema", type="primary", use_container_width=True): 
            senha_correta = st.secrets.get("APP_PASSWORD", None) if GITHUB_TOKEN else "1234"
            if senha == senha_correta: 
                st.session_state.logado = True
                st.rerun()
            else: 
                st.error("Senha incorreta.")
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
    vendas_banco=Counter([l["banco"] for l in st.session_state.leads if l["status"]=="venda_finalizada"])
    banco_top = vendas_banco.most_common(1)[0][0] if vendas_banco else None
    def score(l):
        tent=l.get("tentativas",0)
        nunca=0 if l.get("ultima")=="Nunca" else 1000
        caixa=50 if tent>=3 and "caixa" in l.get("observacao","").lower() else 0
        banco_bonus=-5 if l["banco"]==banco_top else 0
        return nunca + tent*10 + caixa + banco_bonus
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
        raise ValueError("Conversor manual falhou")
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
    ig_tel=0
    ig_bloq=0
    ig_dup=0
    ig_ddd=0
    ig_np=0
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
        novos.append({
            "id":h,
            "nome":str(row.get(col_nome,f"Lead {idx}"))[:40],
            "cpf":cpf,
            "telefone":tel,
            "banco":str(row.get(col_banco,"PAN")).upper()[:20] if col_banco else "PAN",
            "produto":"FGTS",
            "status":"pendente",
            "tentativas":0,
            "ultima":"Nunca",
            "duracao_seg":0,
            "duracao_txt":"00:00",
            "historico":[],
            "tabulacao":"",
            "observacao":"",
            "notas_cliente":"",
            "arquivado_motivo":"",
            "retorno_hora":"",
            "canal":"chip",
            "custo_estimado":0.0,
            "retorno_data":None,
            "lote":nome_lote,
            "data_import":datetime.now().strftime("%d/%m %H:%M"),
            "ddd":tel[:2]
        })
    return novos, ig_tel, ig_bloq, ig_dup, ig_ddd, ig_np

# CSS FINAL - SEM VERSÃO, KPIs CLICÁVEIS, SIDEBAR LIMPA
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@600&display=swap');
html, body, [class*="css"] {font-family:'Space Grotesk', sans-serif;}
.block-container {padding-bottom:100px !important; padding-top:20px !important;}
section[data-testid="stSidebar"] {background:linear-gradient(180deg,#0f0c29,#1a1a2e); border-right:1px solid rgba(0,255,136,0.15);}
.mini-dash {position:fixed;bottom:70px;right:12px;background:linear-gradient(135deg,#0f0c29,#302b63);color:white;border:1px solid #00ff88;border-radius:16px;padding:10px 16px;box-shadow:0 8px 32px rgba(0,255,136,0.3);z-index:9998;font-size:11px;font-weight:600;}
.foco-overlay {background:linear-gradient(135deg,#0f0c29,#302b63);border:2px solid #00ff88;border-radius:20px;padding:30px;box-shadow:0 0 40px rgba(0,255,136,0.4);color:white;}
.lote-card {background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #00e5ff;border-radius:12px;padding:12px;margin-bottom:10px;color:white;}
.lead-card {background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);border:1px solid rgba(0,229,255,0.2);border-radius:16px;padding:20px;margin-bottom:16px;box-shadow:0 4px 20px rgba(0,0,0,0.3);}
.lead-header-sticky {position:sticky;top:0;z-index:5;background:linear-gradient(135deg,#1a1a2e,#16213e);padding:12px;border-radius:12px;border:1px solid rgba(0,255,136,0.2);margin-bottom:12px;}
.tab-header {background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:10px 14px;margin-bottom:14px;}
.stButton>button {border-radius:10px !important; font-weight:600 !important; transition:all 0.2s !important;}
.stButton>button:hover {transform:translateY(-1px);}
@keyframes pulse-green {0%{box-shadow:0 0 0 0 rgba(0,255,136,0.7);}70%{box-shadow:0 0 0 12px rgba(0,255,136,0);}100%{box-shadow:0 0 0 0 rgba(0,255,136,0);}}
.t0-pulse {animation:pulse-green 2s infinite !important; border:2px solid #00ff88 !important; background:linear-gradient(135deg,rgba(0,255,136,0.2),rgba(0,229,255,0.15)) !important;}
.obs-box {background:rgba(255,204,0,0.08);border:1px solid rgba(255,204,0,0.3);border-radius:12px;padding:14px;margin-top:12px;}
.hist-timeline {background:rgba(0,229,255,0.05);border-left:3px solid #00e5ff;padding:8px 12px 8px 16px;margin:8px 0;border-radius:0 8px 8px 0;}
.retorno-card {background:linear-gradient(135deg,#2a1a0e,#3d2a14);border:1px solid #ff8c00;border-radius:12px;padding:14px;margin-bottom:10px;color:white;}
.kpi-row .stButton>button {background:linear-gradient(135deg,#0f0c29,#302b63) !important; border:1px solid rgba(0,255,136,0.25) !important; border-radius:16px !important; padding:14px 8px !important; height:95px !important; color:white !important; text-align:center !important; line-height:1.2 !important; white-space:pre-line !important; font-family:'JetBrains Mono', monospace !important;}
.kpi-row .stButton>button:hover {border-color:#00ff88 !important; box-shadow:0 6px 30px rgba(0,255,136,0.35) !important; transform:translateY(-2px) !important;}
.kpi-row .stButton>button[kind="primary"] {border:2px solid #00ff88 !important; background:linear-gradient(135deg,#0f0c29,#1a4d2e) !important; box-shadow:0 0 20px rgba(0,255,136,0.4) !important;}
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

# SIDEBAR - FILTROS ORGANIZADOS (NÃO POLUI O DISCADOR)
with st.sidebar:
    st.markdown("## 🔍 Filtros Avançados")
    st.caption("Filtros movidos para cá para limpar o discador")
    
    st.session_state.busca_global = st.text_input("🔍 Busca Global", value=st.session_state.get("busca_global",""), placeholder="Nome, banco, lote, telefone...")
    
    bancos_disponiveis = sorted(list(set([l["banco"] for l in st.session_state.leads]))) if st.session_state.leads else []
    st.session_state.filtro_banco = st.selectbox("🏦 Banco", ["TODOS"]+bancos_disponiveis, index=0 if st.session_state.filtro_banco not in bancos_disponiveis else bancos_disponiveis.index(st.session_state.filtro_banco)+1 if st.session_state.filtro_banco!="TODOS" else 0, key="f_banco_side")
    
    st.session_state.filtro_status = st.selectbox("📊 Status", ["PENDENTES","ATENDIDOS","NÃO ATENDEU","RETORNOS","VENDAS","VENDAS HOJE","ARQUIVADOS","TODOS","QUARENTENA"], index=["PENDENTES","ATENDIDOS","NÃO ATENDEU","RETORNOS","VENDAS","VENDAS HOJE","ARQUIVADOS","TODOS","QUARENTENA"].index(st.session_state.filtro_status) if st.session_state.filtro_status in ["PENDENTES","ATENDIDOS","NÃO ATENDEU","RETORNOS","VENDAS","VENDAS HOJE","ARQUIVADOS","TODOS","QUARENTENA"] else 0, key="f_status_side")
    
    st.session_state.filtro_tentativas = st.selectbox("🔢 Tentativas", ["TODAS","NUNCA LIGADOS (T0)","T1 (1 tentativa)","T2 (2 tentativas)","T3+ (3 ou mais)","T0+T1 (novos)","T2+ (reciclagem)"], index=["TODAS","NUNCA LIGADOS (T0)","T1 (1 tentativa)","T2 (2 tentativas)","T3+ (3 ou mais)","T0+T1 (novos)","T2+ (reciclagem)"].index(st.session_state.filtro_tentativas) if st.session_state.filtro_tentativas in ["TODAS","NUNCA LIGADOS (T0)","T1 (1 tentativa)","T2 (2 tentativas)","T3+ (3 ou mais)","T0+T1 (novos)","T2+ (reciclagem)"] else 0, key="f_tent_side")
    
    st.session_state.ordenar_por = st.selectbox("📈 Ordenar", ["NUNCA LIGADOS PRIMEIRO","MENOS TENTATIVAS PRIMEIRO","MAIS TENTATIVAS PRIMEIRO","NOME A-Z"], index=["NUNCA LIGADOS PRIMEIRO","MENOS TENTATIVAS PRIMEIRO","MAIS TENTATIVAS PRIMEIRO","NOME A-Z"].index(st.session_state.ordenar_por), key="f_ord_side")
    
    ddds=sorted(list(set([l.get("ddd","") for l in st.session_state.leads if l.get("ddd")])) ) if st.session_state.leads else []
    st.session_state.filtro_ddd = st.selectbox("📍 DDD", ["TODOS"]+ddds, index=0 if st.session_state.filtro_ddd not in ddds else ddds.index(st.session_state.filtro_ddd)+1 if st.session_state.filtro_ddd!="TODOS" else 0, key="f_ddd_side")
    
    st.divider()
    st.markdown("### 🎯 Meta Diária")
    meta = st.session_state.get("meta_diaria",20)
    nova_meta = st.number_input("Meta vendas", min_value=1, max_value=100, value=meta, label_visibility="collapsed", key="meta_side")
    if nova_meta != meta:
        st.session_state.meta_diaria = nova_meta
        salvar_dados()
    perc_meta = min(100, int(vendas_hoje/nova_meta*100)) if nova_meta>0 else 0
    st.progress(perc_meta/100)
    st.caption(f"{vendas_hoje}/{nova_meta} vendas ({perc_meta}%)")
    
    st.divider()
    if st.button("🧹 Limpar Todos Filtros", use_container_width=True):
        st.session_state.filtro_banco="TODOS"
        st.session_state.filtro_status="PENDENTES"
        st.session_state.filtro_tentativas="TODAS"
        st.session_state.filtro_ddd="TODOS"
        st.session_state.ordenar_por="NUNCA LIGADOS PRIMEIRO"
        st.session_state.busca_global=""
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
    
    st.divider()
    st.caption(f"📱 {total} leads | 📥 {pend} pend | 💰 {vendas} vendas")

# HEADER SEM VERSÃO
st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f0c29 0%,#302b63 50%,#24243e 100%);padding:20px 26px;border-radius:20px;color:white;margin-bottom:14px;box-shadow:0 10px 40px rgba(0,0,0,0.4);border:1px solid rgba(0,255,136,0.15);">
<div style="display:flex;justify-content:space-between;align-items:center;">
<div style="display:flex;align-items:center;gap:14px;">
<div style="background:linear-gradient(135deg,#00e5ff,#00ff88);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:22px;">📞</div>
<div><h1 style="margin:0;font-size:22px;font-weight:800;letter-spacing:-0.5px;">Discadora Eletrônica <span style="color:#00e5ff;">A&K</span></h1><p style="margin:2px 0 0 0;opacity:0.6;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;">Sistema Profissional • Filtros na lateral • KPIs clicáveis</p></div>
</div>
<div style="text-align:right;">
<p style="margin:0;font-size:11px;opacity:0.5;font-family:'JetBrains Mono';">{datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
<div style="display:flex;align-items:center;gap:6px;justify-content:flex-end;margin-top:4px;"><div style="width:8px;height:8px;background:#00ff88;border-radius:50%;box-shadow:0 0 10px #00ff88;"></div><span style="font-size:12px;color:#00ff88;font-weight:600;">Online</span></div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

# KPIs CLICÁVEIS - AGORA FUNCIONAM DE VERDADE
st.markdown('<div class="kpi-row">', unsafe_allow_html=True)
k1,k2,k3,k4,k5,k6,k7=st.columns(7)
with k1:
    is_active = st.session_state.filtro_status=="TODOS" and st.session_state.filtro_banco=="TODOS"
    if st.button(f"{total}\n📱 TOTAL\n{atendidos}a+{nao_atendeu}na", key="kpi_total", use_container_width=True, type="primary" if is_active else "secondary"):
        st.session_state.filtro_status="TODOS"
        st.session_state.filtro_banco="TODOS"
        st.session_state.filtro_tentativas="TODAS"
        st.session_state.filtro_ddd="TODOS"
        st.session_state.busca_global=""
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
with k2:
    is_active = st.session_state.filtro_status=="PENDENTES"
    if st.button(f"{pend}\n📥 PENDENTES", key="kpi_pend", use_container_width=True, type="primary" if is_active else "secondary"):
        st.session_state.filtro_status="PENDENTES"
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
with k3:
    is_active = st.session_state.filtro_tentativas=="NUNCA LIGADOS (T0)" and st.session_state.filtro_status=="PENDENTES"
    if st.button(f"{nunca}\n🆕 NUNCA LIGADOS", key="kpi_nunca", use_container_width=True, type="primary" if is_active else "secondary"):
        st.session_state.filtro_status="PENDENTES"
        st.session_state.filtro_tentativas="NUNCA LIGADOS (T0)"
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
with k4:
    is_active = st.session_state.filtro_status=="VENDAS" and not st.session_state.filtro_vendas_hoje
    if st.button(f"{vendas}\n💰 VENDAS TOTAL", key="kpi_vendas", use_container_width=True, type="primary" if is_active else "secondary"):
        st.session_state.filtro_status="VENDAS"
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
with k5:
    is_active = st.session_state.filtro_vendas_hoje
    if st.button(f"{vendas_hoje}\n🔥 VENDAS HOJE", key="kpi_vendas_hoje", use_container_width=True, type="primary" if is_active else "secondary"):
        st.session_state.filtro_status="VENDAS"
        st.session_state.filtro_vendas_hoje=True
        st.rerun()
with k6:
    is_active = st.session_state.filtro_status=="RETORNOS"
    if st.button(f"{retornos_total}\n⏰ RETORNOS", key="kpi_ret", use_container_width=True, type="primary" if is_active else "secondary"):
        st.session_state.filtro_status="RETORNOS"
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
with k7:
    is_active = st.session_state.filtro_status=="ARQUIVADOS"
    if st.button(f"{arquivados}\n📁 ARQUIVADOS", key="kpi_arq", use_container_width=True, type="primary" if is_active else "secondary"):
        st.session_state.filtro_status="ARQUIVADOS"
        st.session_state.filtro_vendas_hoje=False
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

if retornos:
    st.markdown(f'<div style="background:linear-gradient(90deg,#ff8c00,#ffcc00);color:#000;padding:8px 14px;border-radius:10px;font-weight:700;font-size:12px;margin:10px 0;">⏰ {len(retornos)} retorno(s) hoje! Clique em ⏰ RETORNOS acima</div>', unsafe_allow_html=True)

tab1, tab_ret, tab2, tab3 = st.tabs(["🎯 DISCADOR", "⏰ RETORNOS FUTUROS", "📦 LOTES", "📊 RELATÓRIOS"])

with tab1:
    st.markdown('<div class="tab-header">', unsafe_allow_html=True)
    col_h1,col_h2,col_h3=st.columns([2.5,1,1])
    with col_h1:
        status_txt = st.session_state.filtro_status
        if st.session_state.filtro_vendas_hoje:
            status_txt = "VENDAS HOJE"
        st.caption(f"📊 Filtro ativo: {status_txt} | 🏦 {st.session_state.filtro_banco} | 🔢 {st.session_state.filtro_tentativas} | 📍 DDD {st.session_state.filtro_ddd} | Filtros na lateral ←")
    with col_h2:
        st.session_state.auto_next=st.checkbox("⏭️ Auto Next", value=True)
    with col_h3:
        if st.button("🧠 Próximo Inteligente", use_container_width=True, type="primary"):
            nxt=proximo_inteligente(st.session_state.selected_id)
            if nxt:
                st.session_state.selected_id=nxt
                st.session_state.modo_foco=False
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    modo_foco_ativo=st.session_state.modo_foco and st.session_state.selected_id in st.session_state.call_start if st.session_state.selected_id else False

    lista=[]
    for l in st.session_state.leads:
        # Filtro vendas hoje especial
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
            if st.session_state.filtro_status=="VENDAS HOJE" and l["status"]!="venda_finalizada":
                continue
            if st.session_state.filtro_status=="ARQUIVADOS" and l["status"]!="arquivado":
                continue
            if st.session_state.filtro_status=="QUARENTENA" and not (l.get("tentativas",0)>=3 and "caixa" in l.get("observacao","").lower()):
                continue
            if st.session_state.filtro_status=="PENDENTES" and l["status"]=="arquivado":
                continue
        tent=l.get("tentativas",0)
        ultima=l.get("ultima","Nunca")
        if st.session_state.filtro_tentativas=="NUNCA LIGADOS (T0)" and ultima!="Nunca":
            continue
        if st.session_state.filtro_tentativas=="T1 (1 tentativa)" and tent!=1:
            continue
        if st.session_state.filtro_tentativas=="T2 (2 tentativas)" and tent!=2:
            continue
        if st.session_state.filtro_tentativas=="T3+ (3 ou mais)" and tent<3:
            continue
        if st.session_state.filtro_tentativas=="T0+T1 (novos)" and tent>1:
            continue
        if st.session_state.filtro_tentativas=="T2+ (reciclagem)" and tent<2:
            continue
        if st.session_state.filtro_ddd!="TODOS" and l.get("ddd","")!=st.session_state.filtro_ddd:
            continue
        busca=st.session_state.get("busca_global","")
        if busca and busca.lower() not in l["nome"].lower() and busca.lower() not in l["banco"].lower() and busca.lower() not in l.get("lote","").lower() and busca.lower() not in l["telefone"]:
            continue
        lista.append(l)
    
    if st.session_state.ordenar_por=="NUNCA LIGADOS PRIMEIRO":
        lista=sorted(lista, key=lambda x: (0 if x.get("ultima")=="Nunca" else 1, x.get("tentativas",0)))
    elif st.session_state.ordenar_por=="MENOS TENTATIVAS PRIMEIRO":
        lista=sorted(lista, key=lambda x: x.get("tentativas",0))
    elif st.session_state.ordenar_por=="MAIS TENTATIVAS PRIMEIRO":
        lista=sorted(lista, key=lambda x: x.get("tentativas",0), reverse=True)
    elif st.session_state.ordenar_por=="NOME A-Z":
        lista=sorted(lista, key=lambda x: x.get("nome",""))

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

    def arquivar_lead(sel, motivo="Já foi ligado - ocultar"):
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

    if modo_foco_ativo:
        sel=next((l for l in st.session_state.leads if l["id"]==st.session_state.selected_id), None)
        if sel:
            st.markdown('<div class="foco-overlay">', unsafe_allow_html=True)
            st.markdown(f"## 🎯 MODO FOCO | {sel['nome']} | 🏦 {sel['banco']} | T{sel.get('tentativas',0)}")
            decorrido=(datetime.now()-st.session_state.call_start[sel["id"]]).total_seconds()
            st.markdown(f"### ⏱️ {formatar_tempo(decorrido)} | 📱 {sel['telefone']}")
            st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:24px;border-radius:16px;text-align:center;font-weight:900;text-decoration:none;font-size:26px;">📱 {sel["telefone"]} • EM LIGAÇÃO</a>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            c1,c2,c3,c4=st.columns(4)
            with c1:
                if st.button("✅ Atendeu", use_container_width=True, type="primary", key=f"foco_at1_{sel['id']}"):
                    registrar_evento(sel,"atendido","Atendeu - interessado")
            with c2:
                if st.button("📬 Caixa Postal", use_container_width=True, key=f"foco_cx_{sel['id']}"):
                    registrar_evento(sel,"nao_atendeu","Caixa postal")
            with c3:
                if st.button("📵 Desligado", use_container_width=True, key=f"foco_des_{sel['id']}"):
                    registrar_evento(sel,"nao_atendeu","Desligado")
            with c4:
                if st.button("💰 Venda!", use_container_width=True, key=f"foco_vd_{sel['id']}"):
                    st.balloons()
                    registrar_evento(sel,"venda_finalizada","Venda FGTS")
            if st.button("🔙 Sair do Foco", use_container_width=True, key=f"foco_sair_{sel['id']}"):
                st.session_state.modo_foco=False
                st.rerun()
    else:
        col_lista,col_atend=st.columns([1,2.2])
        with col_lista:
            if len(lista)==0:
                st.markdown("""
                <div style="text-align:center;padding:40px;background:rgba(255,255,255,0.03);border-radius:16px;border:1px dashed rgba(255,255,255,0.2);">
                <div style="font-size:48px;">📭</div>
                <p style="color:white;font-weight:600;">Nenhum lead encontrado</p>
                <p style="color:#aaa;font-size:12px;">Tente limpar filtros na lateral</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button("🧹 Limpar Filtros", use_container_width=True, key="clear_filtros_empty"):
                    st.session_state.filtro_banco="TODOS"
                    st.session_state.filtro_status="PENDENTES"
                    st.session_state.filtro_tentativas="TODAS"
                    st.session_state.filtro_ddd="TODOS"
                    st.session_state.busca_global=""
                    st.session_state.filtro_vendas_hoje=False
                    st.rerun()
            else:
                st.markdown(f'<p style="font-size:13px;font-weight:700;color:#00e5ff;letter-spacing:1px;text-transform:uppercase;">📋 Fila ({len(lista)}) • {st.session_state.ordenar_por}</p>', unsafe_allow_html=True)
                page_size = 30
                total_pags=(len(lista)//page_size)+1
                pag=st.selectbox(f"Página {total_pags} págs ({page_size}/pág)", [f"{i*page_size+1}-{(i+1)*page_size}" for i in range(total_pags)], key="pag_disc")
                idx_pag=int(pag.split("-")[0])//page_size if pag else 0
                for lead in lista[idx_pag*page_size:(idx_pag+1)*page_size]:
                    bloqueado=lead["telefone"] in st.session_state.blocklist or lead["telefone"] in st.session_state.nao_perturbe
                    dot="🚫" if bloqueado else {"pendente":"⚪","atendido":"🟢","nao_atendeu":"🔴","retorno_futuro":"🟠","venda_finalizada":"💰","arquivado":"📁"}[lead["status"]]
                    is_sel=lead["id"]==st.session_state.selected_id
                    tent=lead.get("tentativas",0)
                    ultima=lead.get("ultima","Nunca")
                    eh_t0 = ultima=="Nunca" and tent==0
                    tent_txt=f" T{tent}" if tent>0 else " 🆕 T0" if eh_t0 else f" T{tent}"
                    tem_obs = "📝" if lead.get("notas_cliente") else ""
                    emoji_banco = BANCO_EMOJI.get(lead["banco"], BANCO_EMOJI["DEFAULT"])
                    label = f"{'👉' if is_sel else ''}{dot}{tem_obs} {emoji_banco} {lead['nome'][:12]} • {lead['banco']}{tent_txt}"
                    if st.button(label, key=f"list_{lead['id']}", use_container_width=True, type="primary" if is_sel else "secondary"):
                        st.session_state.selected_id=lead["id"]
                        st.session_state.modo_foco=False
                        st.rerun()
        with col_atend:
            if not st.session_state.selected_id:
                st.info("👈 Selecione cliente na fila • Clique nos KPIs acima para filtrar • Filtros na lateral ←")
                st.markdown('<div class="lead-card">', unsafe_allow_html=True)
                st.markdown("#### 💡 Como usar os KPIs clicáveis")
                st.markdown("""
                - **📱 TOTAL:** Mostra todos os 150 leads
                - **📥 PENDENTES:** Só quem ainda não foi tabulado
                - **🆕 NUNCA LIGADOS:** Só T0, nunca ligados (pulsando verde)
                - **💰 VENDAS TOTAL:** Todas vendas
                - **🔥 VENDAS HOJE:** Só vendas de hoje - clique pra ver quem vendeu!
                - **⏰ RETORNOS:** Quem agendou retorno
                - **📁 ARQUIVADOS:** Quem você ocultou com Já liguei
                - **Filtros:** Na lateral esquerda, não polui mais o discador
                """)
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                sel=next((l for l in st.session_state.leads if l["id"]==st.session_state.selected_id), None)
                if sel:
                    tent=sel.get("tentativas",0)
                    cpf_raw = sel.get("cpf","")
                    emoji_banco = BANCO_EMOJI.get(sel["banco"], BANCO_EMOJI["DEFAULT"])
                    st.markdown('<div class="lead-header-sticky">', unsafe_allow_html=True)
                    col_h_nome, col_h_copy = st.columns([3,1])
                    with col_h_nome:
                        st.markdown(f"### {emoji_banco} {sel['nome']} | 🏦 {sel['banco']} | 🔢 T{tent} | 📦 {sel.get('lote','')[:20]}")
                        st.caption(f"CPF: {cpf_raw} | DDD: {sel.get('ddd','')} | Status: {sel['status'].upper()} | {sel.get('data_import','')}")
                    with col_h_copy:
                        components.html(f"""
                        <button onclick="navigator.clipboard.writeText('{sel['telefone']}'); alert('Copiado {sel['telefone']}!')" style="background:#1a1a2e;border:1px solid #00e5ff;color:#00e5ff;padding:8px 12px;border-radius:8px;cursor:pointer;width:100%;font-weight:700;font-size:12px;">
                        📋 Copiar
                        </button>
                        """, height=38)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.markdown('<div class="lead-card">', unsafe_allow_html=True)
                    if sel["telefone"] in st.session_state.nao_perturbe:
                        st.error("🚫 Não Perturbe Anatel - NÃO LIGAR")
                    else:
                        em_ligacao=sel["id"] in st.session_state.call_start
                        if not em_ligacao:
                            col_d1,col_d2,col_d3=st.columns([1.5,1,1])
                            with col_d1:
                                if st.button(f"▶️ LIGAR CHIP • {sel['telefone']}", key=f"discar_{sel['id']}", type="primary", use_container_width=True):
                                    st.session_state.call_start[sel["id"]]=datetime.now()
                                    st.session_state.modo_foco=True
                                    st.rerun()
                            with col_d2:
                                msg_map={"PAN":f"Olá {sel['nome']}, A&K sobre FGTS PAN liberado. Explico 1 min?","BMG":f"Olá {sel['nome']}, BMG liberou FGTS. Quer saber valor?","C6":f"Olá {sel['nome']}, C6 liberou FGTS. Explico rapidinho?","ITAÚ":f"Olá {sel['nome']}, Itaú liberou FGTS. Quer saber valor?","ITAU":f"Olá {sel['nome']}, Itaú liberou FGTS. Quer saber valor?"}
                                msg=msg_map.get(sel["banco"], f"Olá {sel['nome']}, A&K FGTS {sel['banco']} liberado")
                                msg_enc=urllib.parse.quote(msg)
                                st.markdown(f'<a href="https://wa.me/55{sel["telefone"]}?text={msg_enc}" target="_blank" style="display:block;background:#25D366;color:#fff;padding:12px;border-radius:10px;text-align:center;font-weight:700;text-decoration:none">💬 Zap {sel["banco"]}</a>', unsafe_allow_html=True)
                            with col_d3:
                                if st.button("🚫 Bloquear", key=f"bloq_{sel['id']}", use_container_width=True):
                                    st.session_state.blocklist.add(sel["telefone"])
                                    salvar_dados()
                                    st.rerun()
                        else:
                            decorrido=(datetime.now()-st.session_state.call_start[sel["id"]]).total_seconds()
                            st.warning(f"📱 EM LIGAÇÃO: {formatar_tempo(decorrido)}")
                            st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:20px;border-radius:14px;text-align:center;font-weight:900;text-decoration:none;font-size:22px">📱 {sel["telefone"]} • ⏱️ {formatar_tempo(decorrido)}</a>', unsafe_allow_html=True)
                    
                    st.markdown("#### ⚡ Tabulação Rápida - 1 Clique")
                    c1,c2,c3,c4=st.columns(4)
                    with c1:
                        if st.button("✅ Atendeu", use_container_width=True, type="primary", key=f"fin_at_{sel['id']}"):
                            registrar_evento(sel,"atendido","Atendeu - interessado")
                    with c2:
                        if st.button("📬 Caixa Postal", use_container_width=True, key=f"fin_cx_{sel['id']}"):
                            registrar_evento(sel,"nao_atendeu","Caixa postal")
                    with c3:
                        if st.button("📵 Desligado", use_container_width=True, key=f"fin_des_{sel['id']}"):
                            registrar_evento(sel,"nao_atendeu","Desligado")
                    with c4:
                        if st.button("💰 Venda!", use_container_width=True, key=f"fin_ve_{sel['id']}"):
                            st.balloons()
                            registrar_evento(sel,"venda_finalizada","Venda FGTS")
                    c5,c6,c7,c8=st.columns(4)
                    with c5:
                        if st.button("🤔 Sem interesse", use_container_width=True, key=f"fin_si_{sel['id']}"):
                            registrar_evento(sel,"atendido","Sem interesse no momento")
                    with c6:
                        if st.button("❌ Número errado", use_container_width=True, key=f"fin_er_{sel['id']}"):
                            registrar_evento(sel,"nao_atendeu","Número errado")
                    with c7:
                        if st.session_state.confirm_arquivar == sel["id"]:
                            st.warning("Tem certeza?")
                            cc1, cc2 = st.columns(2)
                            with cc1:
                                if st.button("✅ Sim", key=f"conf_sim_{sel['id']}", type="primary", use_container_width=True):
                                    arquivar_lead(sel, "Já foi ligado - ocultar")
                            with cc2:
                                if st.button("❌ Não", key=f"conf_nao_{sel['id']}", use_container_width=True):
                                    st.session_state.confirm_arquivar = None
                                    st.rerun()
                        else:
                            if st.button("📁 Já liguei", use_container_width=True, key=f"fin_arq_{sel['id']}"):
                                st.session_state.confirm_arquivar = sel["id"]
                                st.rerun()
                    with c8:
                        if st.button("🔄 Pendentes", use_container_width=True, key=f"fin_volta_{sel['id']}"):
                            sel["status"]="pendente"
                            salvar_dados()
                            st.rerun()

                    st.markdown("#### 📅 Agendar Retorno Futuro")
                    with st.expander("📅 Agendar com data/hora", expanded=False):
                        col_dt1, col_dt2 = st.columns(2)
                        with col_dt1:
                            data_ret = st.date_input("📅 Data", value=date.today()+timedelta(days=1), min_value=date.today(), key=f"data_ret_{sel['id']}")
                        with col_dt2:
                            hora_ret = st.time_input("⏰ Hora", value=time(14,0), key=f"hora_ret_{sel['id']}")
                        motivo_ret = st.text_input("📝 Motivo", placeholder="Ex: Pediu segunda 14h", key=f"motivo_ret_{sel['id']}")
                        if st.button(f"✅ Agendar {data_ret.strftime('%d/%m/%Y')} {hora_ret.strftime('%H:%M')}", type="primary", use_container_width=True, key=f"conf_ret_{sel['id']}"):
                            data_str = data_ret.strftime("%d/%m/%Y")
                            hora_str = hora_ret.strftime("%H:%M")
                            obs_ret = f"Retorno {data_str} {hora_str} - {motivo_ret}" if motivo_ret else f"Retorno {data_str} {hora_str}"
                            registrar_evento(sel,"retorno_futuro", obs_ret, retorno_data=data_str, retorno_hora=hora_str)
                    st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown('<div class="obs-box">', unsafe_allow_html=True)
                    st.markdown("#### 📝 Observações do cliente")
                    notas_atual = sel.get("notas_cliente","")
                    novas_notas = st.text_area("Obs", value=notas_atual, placeholder="Ex: Tem 2 cartões, prefere WhatsApp...", key=f"notas_area_{sel['id']}", label_visibility="collapsed", height=90)
                    col_obs1, col_obs2 = st.columns([1,1])
                    with col_obs1:
                        if st.button("💾 Salvar Obs", use_container_width=True, key=f"save_obs_{sel['id']}"):
                            sel["notas_cliente"] = novas_notas
                            salvar_dados()
                            st.success("Salvo!")
                    with col_obs2:
                        if sel.get("notas_cliente"):
                            st.info(f"📝 {sel.get('notas_cliente')[:70]}...")
                    st.markdown('</div>', unsafe_allow_html=True)

                    st.markdown('<div class="lead-card">', unsafe_allow_html=True)
                    st.markdown(f"#### 📊 Histórico - {sel['nome']}")
                    col_hist1, col_hist2, col_hist3, col_hist4 = st.columns(4)
                    hist = sel.get("historico") or []
                    with col_hist1:
                        st.metric("📞 Ligações", len(hist))
                    with col_hist2:
                        st.metric("✅ Atendeu", len([h for h in hist if h.get("acao")=="atendido"]))
                    with col_hist3:
                        st.metric("📬 Caixa Postal", len([h for h in hist if "caixa" in h.get("tab","").lower()]))
                    with col_hist4:
                        st.metric("⏱️ Tempo", formatar_tempo(sel.get("duracao_seg",0)))
                    if hist:
                        st.markdown("**📜 Timeline:**")
                        for h in hist[::-1][:10]:
                            acao_icon = {"atendido":"✅","nao_atendeu":"🔴","venda_finalizada":"💰","retorno_futuro":"⏰","arquivado":"📁"}.get(h.get("acao"),"📞")
                            ret_txt = h.get("retorno","")
                            ret_display = f" | 📅 {ret_txt}" if ret_txt else ""
                            st.markdown(f"<div class='hist-timeline'><b>{acao_icon} {h.get('data','')}</b> | {h.get('acao','').upper()} | ⏱️ {h.get('tempo','00:00')} | {h.get('tab','')[:60]}{ret_display}</div>", unsafe_allow_html=True)
                    else:
                        st.caption("🆕 Nunca ligado")
                    st.markdown('</div>', unsafe_allow_html=True)

with tab_ret:
    st.markdown("## ⏰ Retornos Futuros")
    retornos_all = [l for l in st.session_state.leads if l["status"]=="retorno_futuro"]
    if not retornos_all:
        st.info("📭 Nenhum retorno agendado")
    else:
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            hoje_str = datetime.now().strftime("%d/%m/%Y")
            ret_hoje = len([l for l in retornos_all if l.get("retorno_data")==hoje_str])
            st.metric("⏰ Hoje", ret_hoje)
        with col_r2:
            amanha_str = (datetime.now()+timedelta(days=1)).strftime("%d/%m/%Y")
            ret_amanha = len([l for l in retornos_all if l.get("retorno_data")==amanha_str])
            st.metric("📅 Amanhã", ret_amanha)
        with col_r3:
            st.metric("📋 Total", len(retornos_all))
        def parse_data_ret(l):
            try:
                return datetime.strptime(l.get("retorno_data","01/01/2099"), "%d/%m/%Y")
            except:
                return datetime(2099,1,1)
        retornos_sorted = sorted(retornos_all, key=parse_data_ret)
        for lead in retornos_sorted:
            st.markdown(f'<div class="retorno-card">', unsafe_allow_html=True)
            col_r_a, col_r_b = st.columns([2,1])
            with col_r_a:
                emoji = BANCO_EMOJI.get(lead['banco'], "⚪")
                st.markdown(f"**{emoji} {lead['nome']} | 🏦 {lead['banco']} | 📱 {lead['telefone']}**")
                st.markdown(f"📅 **{lead.get('retorno_data','')} às {lead.get('retorno_hora','')}** | {lead.get('observacao','')[:60]}")
            with col_r_b:
                if st.button(f"▶️ Ligar Agora", key=f"ligar_ret_{lead['id']}", type="primary", use_container_width=True):
                    st.session_state.selected_id = lead["id"]
                    st.success("Vá em DISCADOR")
                c1,c2 = st.columns(2)
                with c1:
                    if st.button(f"🔄 Reagendar", key=f"reag_ret_{lead['id']}", use_container_width=True):
                        st.session_state.selected_id = lead["id"]
                with c2:
                    if st.button(f"📥 Pendentes", key=f"pend_ret_{lead['id']}", use_container_width=True):
                        lead["status"]="pendente"
                        salvar_dados()
                        st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

with tab2:
    st.markdown("## 📦 Gestão de Lotes")
    col_imp1,col_imp2=st.columns([2,1])
    with col_imp1:
        st.info("✅ CSV, XLSX, XLS • Higienizador")
        arquivos=st.file_uploader("Arraste planilhas", type=["csv","xlsx","xls"], accept_multiple_files=True, key="import_ultimate")
        if arquivos:
            dfs=[]
            erros=[]
            for arq in arquivos:
                try:
                    dfs.append((arq.name, ler_planilha(arq)))
                except Exception as e:
                    erros.append(f"{arq.name}: {e}")
            if erros:
                for err in erros:
                    st.error(err)
            if dfs:
                st.success(f"📦 {len(dfs)} planilha(s)")
                for nome,df in dfs:
                    with st.expander(f"📄 {nome}: {len(df)} linhas"):
                        st.dataframe(df.head(5), use_container_width=True)
                if st.button("✅ IMPORTAR TUDO", type="primary", use_container_width=True):
                    existentes=set([l["id"] for l in st.session_state.leads])
                    nao_pert_set=set(st.session_state.nao_perturbe)
                    total_importados=0
                    for nome,df in dfs:
                        lote_id=hashlib.sha256(f"{nome}{datetime.now()}".encode()).hexdigest()[:8]
                        novos,ig_tel,ig_bloq,ig_dup,ig_ddd,ig_np=montar_novos_leads(df.copy(), existentes, st.session_state.blocklist, nao_pert_set, nome)
                        st.session_state.leads.extend(novos)
                        total_importados+=len(novos)
                        st.session_state.lotes.append({"id":lote_id,"nome":nome,"data":datetime.now().strftime("%d/%m %H:%M:%S"),"qtd":len(df),"importados":len(novos),"ignorados":ig_tel+ig_bloq+ig_dup+ig_ddd+ig_np,"detalhe":f"Tel:{ig_tel} Bloq:{ig_bloq} Dup:{ig_dup} DDD:{ig_ddd} NP:{ig_np}"})
                    salvar_dados()
                    st.success(f"✅ {total_importados} importados")
                    st.rerun()
    with col_imp2:
        st.markdown("#### 📦 Lotes Ativos")
        if st.session_state.lotes:
            for lote in st.session_state.lotes[-20:][::-1]:
                st.markdown(f"<div class='lote-card'><b>📦 {lote['nome'][:20]}</b><br>📅 {lote['data']}<br>✅ {lote.get('importados',0)}/{lote['qtd']}</div>", unsafe_allow_html=True)
                c1,c2=st.columns(2)
                with c1:
                    if st.button(f"🗑️ Excluir", key=f"del_lote_tab2_{lote['id']}"):
                        st.session_state.leads=[l for l in st.session_state.leads if l.get('lote')!=lote['nome']]
                        st.session_state.lotes=[lt for lt in st.session_state.lotes if lt['id']!=lote['id']]
                        salvar_dados()
                        st.rerun()
                with c2:
                    df_lote_pd=pd.DataFrame([l for l in st.session_state.leads if l.get('lote')==lote['nome']])
                    if not df_lote_pd.empty:
                        csv=df_lote_pd.to_csv(index=False).encode("utf-8")
                        st.download_button(f"⬇️ Exportar", csv, file_name=f"{lote['nome']}_export.csv", mime="text/csv", key=f"dl_tab2_{lote['id']}", use_container_width=True)

with tab3:
    st.markdown("## 📊 Relatórios")
    if not st.session_state.leads:
        st.info("Sem dados ainda")
    else:
        df_all=pd.DataFrame(st.session_state.leads)
        c1,c2,c3,c4=st.columns(4)
        with c1:
            taxa=len(df_all[df_all["status"]=="venda_finalizada"])/max(len(df_all[df_all["status"]!="pendente"]),1)*100
            st.metric("Taxa Conversão", f"{taxa:.1f}%")
        with c2:
            tmo=df_all["duracao_seg"].sum()/max(len(df_all[df_all["status"]!="pendente"]),1)
            st.metric("TMO Médio", formatar_tempo(tmo))
        with c3:
            st.metric("Tempo Total", formatar_tempo(df_all["duracao_seg"].sum()))
        with c4:
            st.metric("Blocklist+NP", f"{len(st.session_state.blocklist)+len(st.session_state.nao_perturbe)}")
        col_g1,col_g2=st.columns(2)
        with col_g1:
            st.markdown("#### 🏦 Vendas por Banco")
            vendas_banco=df_all[df_all["status"]=="venda_finalizada"]["banco"].value_counts()
            if not vendas_banco.empty:
                st.bar_chart(vendas_banco)
        with col_g2:
            st.markdown("#### 🔢 Por Tentativas")
            st.bar_chart(df_all["tentativas"].value_counts().sort_index())
        e1,e2,e3=st.columns(3)
        with e1:
            csv=df_all.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ CSV Geral", csv, file_name=f"BRS_{datetime.now().strftime('%d%m%Y_%H%M')}.csv", mime="text/csv", use_container_width=True)
        with e2:
            df_vendas=df_all[df_all["status"]=="venda_finalizada"]
            if not df_vendas.empty:
                csv_v=df_vendas.to_csv(index=False).encode("utf-8")
                st.download_button("💰 Só VENDAS", csv_v, file_name=f"VENDAS_{datetime.now().strftime('%d%m%Y')}.csv", mime="text/csv", use_container_width=True)
        with e3:
            json_backup=json.dumps({"leads":st.session_state.leads,"pausas":st.session_state.pausas,"bloqueados":list(st.session_state.blocklist),"lotes":st.session_state.lotes}, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button("💾 Backup JSON", json_backup, file_name=f"BACKUP_{datetime.now().strftime('%d%m%Y_%H%M')}.json", mime="application/json", use_container_width=True)

components.html("""
<script>
function addPulseToT0() {
    try {
        const doc = window.parent.document;
        const buttons = doc.querySelectorAll('button');
        buttons.forEach(btn => {
            if (btn.innerText.includes('🆕') && btn.innerText.includes('T0')) {
                if (!btn.classList.contains('t0-pulse')) {
                    btn.classList.add('t0-pulse');
                }
            }
        });
    } catch(e) {}
}
const observer = new MutationObserver(addPulseToT0);
try {
    observer.observe(window.parent.document.body, {childList: true, subtree: true});
} catch(e) {}
setInterval(addPulseToT0, 800);
setTimeout(addPulseToT0, 500);
</script>
""", height=0)

if st.session_state.leads:
    df_all=pd.DataFrame(st.session_state.leads)
    pend=len(df_all[df_all["status"]=="pendente"])
    nunca=len(df_all[(df_all["status"]=="pendente") & (df_all["ultima"]=="Nunca")])
    vendas=len(df_all[df_all["status"]=="venda_finalizada"])
    tempo_total=df_all["duracao_seg"].sum()
    tmo=tempo_total/max(len(df_all[df_all["status"]!="pendente"]),1)
    st.markdown(f'<div class="mini-dash">📥 {pend} pend | 🆕 {nunca} nunca | ⏱️ TMO {formatar_tempo(tmo)} | 💰 {vendas} vendas | 📁 {len(df_all[df_all["status"]=="arquivado"])} arq | ⏰ {len(df_all[df_all["status"]=="retorno_futuro"])} ret</div>', unsafe_allow_html=True)
