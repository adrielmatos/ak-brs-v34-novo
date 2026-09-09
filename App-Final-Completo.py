import streamlit as st
import pandas as pd
import hashlib
import base64
import json
import requests
from datetime import datetime, timedelta
from io import BytesIO
import urllib.parse
import os
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

st.set_page_config(page_title="A&K BRS v6.0 ULTIMATE - FUTURISTA", layout="wide", page_icon="🚀")

# =========================================================
# CONFIG GITHUB - BANCO
# =========================================================
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
    <div style="text-align:center;padding:40px;background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);border-radius:20px;color:white;margin-bottom:20px;">
    <h1>🚀 A&K BRS v6.0 ULTIMATE</h1>
    <p>Discadora Profissional + Gestão de Lotes + Auto Conversor + Compliance Anatel</p>
    </div>
    """, unsafe_allow_html=True)
    senha = st.text_input("🔒 Senha de acesso", type="password")
    if st.button("Entrar no Sistema", type="primary", use_container_width=True): 
        senha_correta = st.secrets.get("APP_PASSWORD", None) if GITHUB_TOKEN else "1234"
        if senha == senha_correta: st.session_state.logado = True; st.rerun()
        else: st.error("Senha incorreta.")
    return False

if GITHUB_TOKEN:
    if not checar_login(): st.stop()

# =========================================================
# PERSISTÊNCIA
# =========================================================
def carregar_dados():
    if not GITHUB_API or not GITHUB_TOKEN:
        if os.path.exists("brs_dados_local.json"):
            try:
                with open("brs_dados_local.json","r",encoding="utf-8") as f:
                    d=json.load(f)
                    return d.get("leads",[]), d.get("pausas",[]), set(d.get("bloqueados",[])), d.get("lotes",[]), d.get("nao_perturbe",[])
            except: return [],[],set(),[],[]
        return [],[],set(),[],[]
    try:
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        r=requests.get(GITHUB_API, headers=headers)
        if r.status_code==200:
            conteudo=r.json()
            st.session_state["_gh_sha"]=conteudo["sha"]
            dados=json.loads(base64.b64decode(conteudo["content"]).decode("utf-8"))
            return dados.get("leads",[]), dados.get("pausas",[]), set(dados.get("bloqueados",[])), dados.get("lotes",[]), dados.get("nao_perturbe",[])
        elif r.status_code==404:
            st.session_state["_gh_sha"]=None
            return [],[],set(),[],[]
    except Exception as e:
        st.error(f"Erro GitHub: {e}")
    return [],[],set(),[],[]

def salvar_dados():
    payload={"leads":st.session_state.leads,"pausas":st.session_state.pausas,"bloqueados":list(st.session_state.blocklist),"lotes":st.session_state.lotes,"nao_perturbe":st.session_state.nao_perturbe}
    conteudo_str=json.dumps(payload, ensure_ascii=False, indent=2)
    if not GITHUB_API or not GITHUB_TOKEN:
        with open("brs_dados_local.json","w",encoding="utf-8") as f: f.write(conteudo_str)
        return
    try:
        conteudo_b64=base64.b64encode(conteudo_str.encode("utf-8")).decode("utf-8")
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        body={"message": f"v6.0 {datetime.now().strftime('%d/%m %H:%M:%S')}","content": conteudo_b64}
        if st.session_state.get("_gh_sha"): body["sha"]=st.session_state["_gh_sha"]
        r=requests.put(GITHUB_API, headers=headers, json=body)
        if r.status_code in (200,201): st.session_state["_gh_sha"]=r.json()["content"]["sha"]
    except Exception as e:
        st.warning(f"Não salvou GitHub: {e}")

# =========================================================
# ESTADO INICIAL
# =========================================================
if "leads" not in st.session_state:
    leads,pausas,blocklist,lotes,nao_perturbe=carregar_dados()
    st.session_state.leads=leads; st.session_state.pausas=pausas; st.session_state.blocklist=blocklist; st.session_state.lotes=lotes; st.session_state.nao_perturbe=nao_perturbe
    st.session_state.selected_id=None; st.session_state.auto_next=True; st.session_state.call_start={}; st.session_state.filtro_banco="TODOS"; st.session_state.filtro_status="PENDENTES"
    st.session_state.filtro_tentativas="TODAS"; st.session_state.ordenar_por="NUNCA LIGADOS PRIMEIRO"; st.session_state.filtro_ddd="TODOS"
    st.session_state.em_pausa=None; st.session_state.pausa_inicio=None; st.session_state.modo_foco=False; st.session_state.tab_ativa="DISCADOR"

# =========================================================
# FUNÇÕES CORE
# =========================================================
def formatar_tempo(seg):
    if not seg or seg<=0: return "00:00"
    m=int(seg//60); s=int(seg%60)
    if m>=60: h=m//60; m=m%60; return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def proximo_inteligente(atual_id=None):
    pend=[l for l in st.session_state.leads if l["status"]=="pendente"]
    if not pend: return None
    # SCORE: nunca ligados = 0, depois menos tentativas, depois banco que mais vende, penaliza caixa 3x+
    vendas_banco=Counter([l["banco"] for l in st.session_state.leads if l["status"]=="venda_finalizada"])
    banco_top = vendas_banco.most_common(1)[0][0] if vendas_banco else None
    def score(l):
        tent=l.get("tentativas",0)
        nunca=0 if l.get("ultima")=="Nunca" else 1000
        caixa=50 if tent>=3 and "caixa" in l.get("observacao","").lower() else 0
        banco_bonus=-5 if l["banco"]==banco_top else 0
        return nunca + tent*10 + caixa + banco_bonus
    pend_sorted=sorted(pend, key=score)
    if not atual_id: return pend_sorted[0]["id"]
    ids=[l["id"] for l in pend_sorted]
    if atual_id not in ids: return pend_sorted[0]["id"]
    idx=ids.index(atual_id)
    if idx+1 < len(ids): return ids[idx+1]
    return pend_sorted[0]["id"] if len(pend_sorted)>1 else None

def melhor_horario():
    horas=[]
    for l in st.session_state.leads:
        for h in l.get("historico",[]) or []:
            if h.get("acao") in ("atendido","venda_finalizada"):
                try:
                    hora=int(h["data"].split(" ")[1].split(":")[0])
                    horas.append(hora)
                except: continue
    if len(horas)<5: return None
    faixa=Counter([h - (h % 2) for h in horas])
    melhor=faixa.most_common(1)[0][0]
    return f"{melhor:02d}h-{melhor+2:02d}h"

def retornos_hoje():
    hoje=datetime.now().strftime("%d/%m/%Y")
    return [l for l in st.session_state.leads if l.get("status")=="retorno_futuro" and l.get("retorno_data")==hoje]

# AUTO CONVERSOR XLSX SEM OPENPYXL
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
                if t is not None: shared_strings.append(t.text if t.text else "")
                else:
                    txt=""; 
                    for t in si.findall('.//main:t', ns):
                        if t.text: txt+=t.text
                    shared_strings.append(txt)
        except: shared_strings=[]
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
                            try: idx=int(v.text); cols.append(shared_strings[idx] if idx < len(shared_strings) else v.text)
                            except: cols.append(v.text)
                        else: cols.append(v.text)
                    else:
                        is_elem=c.find('main:is', ns)
                        if is_elem is not None:
                            t=is_elem.find('main:t', ns)
                            cols.append(t.text if t is not None and t.text else "")
                        else: cols.append("")
                rows.append(cols)
            if rows:
                header=rows[0]; data=rows[1:]
                max_cols=max(len(r) for r in rows)
                for r in data:
                    while len(r)<max_cols: r.append("")
                df=pd.DataFrame(data, columns=header[:max_cols] if len(header)>=max_cols else header + [f"COL_{i}" for i in range(len(header), max_cols)])
                return df
        except Exception as e:
            pass
        raise ValueError("Conversor manual falhou")
    except zipfile.BadZipFile:
        raise ValueError("XLSX inválido")

def ler_planilha(up):
    nome=up.name.lower()
    file_bytes=up.read()
    up.seek(0)
    if nome.endswith(".xlsx"):
        try: return ler_xlsx_sem_openpyxl(file_bytes)
        except Exception as e: raise ValueError(f"{up.name}: {e} - Adicione openpyxl no requirements ou converta para CSV")
    elif nome.endswith(".xls"):
        try: return pd.read_excel(BytesIO(file_bytes), engine='xlrd')
        except: return pd.read_excel(BytesIO(file_bytes))
    for enc in ["utf-8","latin1","cp1252","iso-8859-1"]:
        for sep in [",",";","\t","|"]:
            try:
                df=pd.read_csv(BytesIO(file_bytes), encoding=enc, sep=sep)
                if len(df.columns)>1: return df
            except: continue
    raise ValueError(f"{up.name}: Não consegui ler")

def montar_novos_leads(df, existentes, bloqueados, nao_perturbe_set, nome_lote):
    df.columns=[str(c).upper().strip() for c in df.columns]
    col_nome=next((c for c in df.columns if "NOME" in c), df.columns[0])
    col_cpf=next((c for c in df.columns if "CPF" in c), None)
    col_tel=next((c for c in df.columns if "TELEFONE" in c or c=="TEL" or "CEL" in c or "FONE" in c), None)
    col_banco=next((c for c in df.columns if "BANCO" in c), None)
    novos, ig_tel, ig_bloq, ig_dup, ig_ddd, ig_np = [],0,0,0,0,0
    for idx,row in df.iterrows():
        cpf=str(row.get(col_cpf,"")).strip() if col_cpf else f"semcpf{idx}"
        tel_raw=str(row.get(col_tel,"")).strip() if col_tel else ""
        tel="".join(filter(str.isdigit, tel_raw))
        if not tel or len(tel)<10: ig_tel+=1; continue
        try: ddd=int(tel[:2]); 
            if ddd<11 or ddd>91: ig_ddd+=1; continue
        except: ig_ddd+=1; continue
        if tel in bloqueados or tel in nao_perturbe_set: 
            if tel in nao_perturbe_set: ig_np+=1
            else: ig_bloq+=1
            continue
        h=hashlib.sha256(f"{cpf}{tel}".encode()).hexdigest()[:12]
        if h in existentes: ig_dup+=1; continue
        existentes.add(h)
        novos.append({
            "id":h,"nome":str(row.get(col_nome,f"Lead {idx}"))[:40],"cpf":cpf,
            "telefone":tel,"banco":str(row.get(col_banco,"PAN")).upper()[:20] if col_banco else "PAN",
            "produto":"FGTS","status":"pendente","tentativas":0,"ultima":"Nunca",
            "duracao_seg":0,"duracao_txt":"00:00","historico":[],"tabulacao":"","observacao":"","canal":"chip","custo_estimado":0.0,"retorno_data":None,
            "lote":nome_lote,"data_import":datetime.now().strftime("%d/%m %H:%M"),"ddd":tel[:2]
        })
    return novos, ig_tel, ig_bloq, ig_dup, ig_ddd, ig_np

# =========================================================
# CSS FUTURISTA PROFISSIONAL
# =========================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
html, body, [class*="css"] {font-family:'Space Grotesk', sans-serif;}
.mini-dash {position:fixed;bottom:12px;right:12px;background:linear-gradient(135deg,#0f0c29,#302b63);color:white;border:1px solid #00ff88;border-radius:16px;padding:12px 18px;box-shadow:0 8px 32px rgba(0,255,136,0.3);z-index:9999;font-size:12px;font-weight:600;}
.foco-overlay {background:linear-gradient(135deg,#0f0c29,#302b63);border:2px solid #00ff88;border-radius:20px;padding:30px;box-shadow:0 0 40px rgba(0,255,136,0.4);color:white;}
.lote-card {background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #00e5ff;border-radius:12px;padding:12px;margin-bottom:10px;color:white;box-shadow:0 4px 15px rgba(0,229,255,0.2);}
.kpi-card {background:linear-gradient(135deg,#0f0c29,#302b63);border:1px solid #00ff88;border-radius:16px;padding:16px;color:white;text-align:center;box-shadow:0 4px 20px rgba(0,255,136,0.2);}
.kpi-card h3 {font-size:28px;margin:0;color:#00ff88;}
.kpi-card p {font-size:12px;margin:4px 0 0 0;opacity:0.8;}
.tab-button {background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;font-weight:800;border-radius:10px;padding:10px;border:none;}
.glass {background:rgba(255,255,255,0.05);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:16px;}
</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER FUTURISTA + KPIs
# =========================================================
total=len(st.session_state.leads); pend=len([l for l in st.session_state.leads if l["status"]=="pendente"]); nunca=len([l for l in st.session_state.leads if l["status"]=="pendente" and l.get("ultima")=="Nunca"]); vendas=len([l for l in st.session_state.leads if l["status"]=="venda_finalizada"]); vendas_hoje=len([l for l in st.session_state.leads if l["status"]=="venda_finalizada" and datetime.now().strftime("%d/%m") in l.get("ultima","")])
retornos=retornos_hoje(); mh=melhor_horario()

st.markdown(f"""
<div style="background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);padding:24px;border-radius:20px;color:white;margin-bottom:16px;box-shadow:0 8px 32px rgba(0,0,0,0.3);">
<div style="display:flex;justify-content:space-between;align-items:center;">
<div><h1 style="margin:0;font-size:32px;">🚀 A&K BRS v6.0 ULTIMATE</h1><p style="margin:4px 0 0 0;opacity:0.8;">Discadora + Gestão Lotes + Auto Conversor + Compliance Anatel + Futurista</p></div>
<div style="text-align:right;"><p style="margin:0;font-size:12px;opacity:0.7;">{datetime.now().strftime('%d/%m/%Y %H:%M')}</p><p style="margin:0;font-size:14px;color:#00ff88;">● Online | GitHub Sync</p></div>
</div>
</div>
""", unsafe_allow_html=True)

k1,k2,k3,k4,k5,k6=st.columns(6)
with k1: st.markdown(f'<div class="kpi-card"><h3>{total}</h3><p>📱 TOTAL</p></div>', unsafe_allow_html=True)
with k2: st.markdown(f'<div class="kpi-card"><h3>{pend}</h3><p>📥 PENDENTES</p></div>', unsafe_allow_html=True)
with k3: st.markdown(f'<div class="kpi-card"><h3>{nunca}</h3><p>🆕 NUNCA LIGADOS</p></div>', unsafe_allow_html=True)
with k4: st.markdown(f'<div class="kpi-card"><h3>{vendas}</h3><p>💰 VENDAS TOTAL</p></div>', unsafe_allow_html=True)
with k5: st.markdown(f'<div class="kpi-card"><h3>{vendas_hoje}</h3><p>🔥 VENDAS HOJE</p></div>', unsafe_allow_html=True)
with k6: st.markdown(f'<div class="kpi-card"><h3>{len(retornos)}</h3><p>⏰ RETORNOS HOJE</p></div>', unsafe_allow_html=True)

if retornos: st.warning(f"⏰ {len(retornos)} retorno(s) agendado(s) para hoje - Filtro RETORNOS")
if mh: st.success(f"📈 Seu melhor horário de conversão: {mh} - Foco nesse horário")

# TABS FUTURISTAS
tab1, tab2, tab3, tab4 = st.tabs(["🎯 DISCADOR", "📦 LOTES & IMPORTAÇÃO", "📊 RELATÓRIOS", "⚙️ CONFIG & COMPLIANCE"])

# =========================================================
# TAB 1 - DISCADOR (CORE)
# =========================================================
with tab1:
    col_h1,col_h2,col_h3,col_h4=st.columns([2,1,1,1])
    with col_h1: st.caption(f"📦 {len(st.session_state.lotes)} lotes | 🧹 Auto higienizador | 🔄 Auto conversor | 🛡️ Não Perturbe OK")
    with col_h2: st.session_state.auto_next=st.checkbox("⏭️ Auto Next", value=True)
    with col_h3:
        if st.button("🧠 Próximo Inteligente", use_container_width=True, type="primary"):
            nxt=proximo_inteligente(st.session_state.selected_id)
            if nxt: st.session_state.selected_id=nxt; st.session_state.modo_foco=False; st.rerun()
    with col_h4:
        if st.button("🔄 Sair", use_container_width=True) and GITHUB_TOKEN: st.session_state.logado=False; st.rerun()

    modo_foco_ativo=st.session_state.modo_foco and st.session_state.selected_id in st.session_state.call_start if st.session_state.selected_id else False

    # LISTA FILTRADA
    lista=[]
    for l in st.session_state.leads:
        if st.session_state.filtro_banco!="TODOS" and l["banco"]!=st.session_state.filtro_banco: continue
        if st.session_state.filtro_status=="PENDENTES" and l["status"]!="pendente": continue
        if st.session_state.filtro_status=="ATENDIDOS" and l["status"]!="atendido": continue
        if st.session_state.filtro_status=="NÃO ATENDEU" and l["status"]!="nao_atendeu": continue
        if st.session_state.filtro_status=="RETORNOS" and l["status"]!="retorno_futuro": continue
        if st.session_state.filtro_status=="VENDAS" and l["status"]!="venda_finalizada": continue
        if st.session_state.filtro_status=="QUARENTENA" and not (l.get("tentativas",0)>=3 and "caixa" in l.get("observacao","").lower()): continue
        tent=l.get("tentativas",0); ultima=l.get("ultima","Nunca")
        if st.session_state.filtro_tentativas=="NUNCA LIGADOS (T0)" and ultima!="Nunca": continue
        if st.session_state.filtro_tentativas=="T1 (1 tentativa)" and tent!=1: continue
        if st.session_state.filtro_tentativas=="T2 (2 tentativas)" and tent!=2: continue
        if st.session_state.filtro_tentativas=="T3+ (3 ou mais)" and tent<3: continue
        if st.session_state.filtro_tentativas=="T0+T1 (novos)" and tent>1: continue
        if st.session_state.filtro_tentativas=="T2+ (reciclagem)" and tent<2: continue
        if st.session_state.filtro_ddd!="TODOS" and l.get("ddd","")!=st.session_state.filtro_ddd: continue
        busca=st.session_state.get("busca_global","")
        if busca and busca.lower() not in l["nome"].lower() and busca.lower() not in l["banco"].lower() and busca.lower() not in l.get("lote","").lower() and busca.lower() not in l["telefone"]: continue
        lista.append(l)
    if st.session_state.ordenar_por=="NUNCA LIGADOS PRIMEIRO":
        lista=sorted(lista, key=lambda x: (0 if x.get("ultima")=="Nunca" else 1, x.get("tentativas",0)))
    elif st.session_state.ordenar_por=="MENOS TENTATIVAS PRIMEIRO":
        lista=sorted(lista, key=lambda x: x.get("tentativas",0))
    elif st.session_state.ordenar_por=="MAIS TENTATIVAS PRIMEIRO":
        lista=sorted(lista, key=lambda x: x.get("tentativas",0), reverse=True)
    elif st.session_state.ordenar_por=="NOME A-Z":
        lista=sorted(lista, key=lambda x: x.get("nome",""))
    elif st.session_state.ordenar_por=="BANCO QUE MAIS VENDE":
        vendas_banco=Counter([l["banco"] for l in st.session_state.leads if l["status"]=="venda_finalizada"])
        lista=sorted(lista, key=lambda x: vendas_banco.get(x["banco"],0), reverse=True)

    def registrar_evento(sel,status_final,obs_pronta,retorno_data=None):
        fim=datetime.now(); dur=0
        if sel["id"] in st.session_state.call_start: dur=(fim-st.session_state.call_start[sel["id"]]).total_seconds(); del st.session_state.call_start[sel["id"]]
        sel["status"]=status_final; sel["tentativas"]=sel.get("tentativas",0)+1; sel["ultima"]=fim.strftime("%d/%m %H:%M"); sel["duracao_seg"]=int(dur); sel["duracao_txt"]=formatar_tempo(dur)
        sel["observacao"]=obs_pronta; sel["tabulacao"]=obs_pronta[:30]; sel["retorno_data"]=retorno_data
        historico=sel.get("historico") or []; historico.append({"data":fim.strftime("%d/%m %H:%M:%S"),"acao":status_final,"tempo":formatar_tempo(dur),"tab":obs_pronta}); sel["historico"]=historico
        salvar_dados(); st.session_state.modo_foco=False
        if st.session_state.auto_next: st.session_state.selected_id=proximo_inteligente(sel["id"])
        st.rerun()

    if modo_foco_ativo:
        sel=next((l for l in st.session_state.leads if l["id"]==st.session_state.selected_id), None)
        if sel:
            st.markdown('<div class="foco-overlay">', unsafe_allow_html=True)
            st.markdown(f"## 🎯 MODO FOCO | {sel['nome']} | 🏦 {sel['banco']} | 📦 {sel.get('lote','')} | T{sel.get('tentativas',0)}")
            decorrido=(datetime.now()-st.session_state.call_start[sel["id"]]).total_seconds()
            st.markdown(f"### ⏱️ {formatar_tempo(decorrido)} | 📱 {sel['telefone']} | DDD {sel.get('ddd','')}")
            st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:24px;border-radius:16px;text-align:center;font-weight:900;text-decoration:none;font-size:26px;box-shadow:0 0 30px rgba(0,255,136,0.5);">📱 {sel["telefone"]} • EM LIGAÇÃO {formatar_tempo(decorrido)}</a>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            c1,c2,c3,c4=st.columns(4)
            with c1:
                if st.button("✅ Interessado", use_container_width=True, type="primary", key=f"foco_at1_{sel['id']}"): registrar_evento(sel,"atendido","Atendeu - interessado")
            with c2:
                if st.button("🔴 Caixa", use_container_width=True, key=f"foco_cx_{sel['id']}"): registrar_evento(sel,"nao_atendeu","Caixa postal")
            with c3:
                if st.button("📵 Desligado", use_container_width=True, key=f"foco_des_{sel['id']}"): registrar_evento(sel,"nao_atendeu","Desligado")
            with c4:
                if st.button("💰 Venda!", use_container_width=True, key=f"foco_vd_{sel['id']}"): st.balloons(); registrar_evento(sel,"venda_finalizada","Venda FGTS")
            if st.button("🔙 Sair do Foco", use_container_width=True, key=f"foco_sair_{sel['id']}"): st.session_state.modo_foco=False; st.rerun()
    else:
        col_lista,col_atend=st.columns([1,2.2])
        with col_lista:
            st.markdown(f"#### 📋 Fila ({len(lista)}) | {st.session_state.ordenar_por}")
            # Paginação
            total_pags=(len(lista)//80)+1
            pag=st.selectbox(f"Página (80 por vez) - {total_pags} págs", [f"{i*80+1}-{(i+1)*80}" for i in range(total_pags)], key="pag_disc")
            idx_pag=int(pag.split("-")[0])//80 if pag else 0
            for lead in lista[idx_pag*80:(idx_pag+1)*80]:
                bloqueado=lead["telefone"] in st.session_state.blocklist or lead["telefone"] in st.session_state.nao_perturbe
                dot="🚫" if bloqueado else {"pendente":"⚪","atendido":"🟢","nao_atendeu":"🔴","retorno_futuro":"🟠","venda_finalizada":"💰"}[lead["status"]]
                is_sel=lead["id"]==st.session_state.selected_id
                tent=lead.get("tentativas",0); ultima=lead.get("ultima","Nunca")
                tent_txt=f" T{tent}" if tent>0 else " 🆕" if ultima=="Nunca" else f" T{tent}"
                ddd_txt=f" {lead.get('ddd','')}"
                if st.button(f"{'👉' if is_sel else ''}{dot} {lead['nome'][:12]} • {lead['banco']}{tent_txt}{ddd_txt}", key=f"list_{lead['id']}", use_container_width=True, type="primary" if is_sel else "secondary"):
                    st.session_state.selected_id=lead["id"]; st.session_state.modo_foco=False; st.rerun()
        with col_atend:
            if not st.session_state.selected_id:
                st.info("👈 Selecione cliente na fila ou clique 🧠 Próximo Inteligente")
                # Resumo tentativas
                if st.session_state.leads:
                    st.markdown("#### 🔢 Resumo por Tentativas")
                    df_all=pd.DataFrame(st.session_state.leads)
                    if not df_all.empty:
                        df_all["tentativas"]=df_all["tentativas"].fillna(0)
                        resumo=df_all.groupby(["tentativas","status"]).size().unstack(fill_value=0)
                        st.dataframe(resumo, use_container_width=True)
            else:
                sel=next((l for l in st.session_state.leads if l["id"]==st.session_state.selected_id), None)
                if sel:
                    bloqueado=sel["telefone"] in st.session_state.blocklist or sel["telefone"] in st.session_state.nao_perturbe
                    tent=sel.get("tentativas",0)
                    st.markdown(f"### 👤 {sel['nome']} | 🏦 {sel['banco']} | 📱 {sel['telefone']} | 🔢 T{tent} | 📦 {sel.get('lote','')} | DDD {sel.get('ddd','')}")
                    if sel["telefone"] in st.session_state.nao_perturbe: st.error("🚫 Este número está no Não Perturbe Anatel - NÃO LIGAR (multa R$50k)")
                    elif bloqueado: st.error("🚫 Blocklist interna")
                    else:
                        em_ligacao=sel["id"] in st.session_state.call_start
                        em_pausa=st.session_state.em_pausa is not None
                        if em_pausa: st.error(f"⏸️ Em pausa: {st.session_state.em_pausa}")
                        elif not em_ligacao:
                            col_d1,col_d2,col_d3,col_d4=st.columns([1.5,1,1,1])
                            with col_d1:
                                if st.button(f"▶️ LIGAR CHIP • {sel['telefone']}", key=f"discar_{sel['id']}", type="primary", use_container_width=True):
                                    st.session_state.call_start[sel["id"]]=datetime.now(); st.session_state.modo_foco=True; st.rerun()
                            with col_d2:
                                msg_map={"PAN":f"Olá {sel['nome']}, A&K sobre FGTS PAN liberado. Explico 1 min?","BMG":f"Olá {sel['nome']}, BMG liberou FGTS. Quer saber valor?","C6":f"Olá {sel['nome']}, C6 liberou FGTS. Explico rapidinho?"}
                                msg=msg_map.get(sel["banco"], f"Olá {sel['nome']}, A&K FGTS {sel['banco']} liberado")
                                msg_enc=urllib.parse.quote(msg)
                                st.markdown(f'<a href="https://wa.me/55{sel["telefone"]}?text={msg_enc}" target="_blank" style="display:block;background:#25D366;color:#fff;padding:12px;border-radius:10px;text-align:center;font-weight:700;text-decoration:none">💬 Zap {sel["banco"]}</a>', unsafe_allow_html=True)
                            with col_d3:
                                if st.button("🎯 Foco", key=f"foco_on_{sel['id']}", use_container_width=True): st.session_state.modo_foco=True; st.rerun()
                            with col_d4:
                                if st.button("🚫 Bloquear", key=f"bloq_{sel['id']}", use_container_width=True): st.session_state.blocklist.add(sel["telefone"]); salvar_dados(); st.rerun()
                        else:
                            decorrido=(datetime.now()-st.session_state.call_start[sel["id"]]).total_seconds()
                            st.warning(f"📱 EM LIGAÇÃO: {formatar_tempo(decorrido)}")
                            st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:20px;border-radius:14px;text-align:center;font-weight:900;text-decoration:none;font-size:22px">📱 {sel["telefone"]} • ⏱️ {formatar_tempo(decorrido)}</a>', unsafe_allow_html=True)
                            if st.button("🔍 Modo Foco Grande", key=f"ver_foco_{sel['id']}", type="primary", use_container_width=True): st.session_state.modo_foco=True; st.rerun()
                        st.markdown("#### ⚡ Tabulação 1 Clique - Profissional")
                        c1,c2,c3,c4=st.columns(4)
                        with c1:
                            if st.button("✅ Atendeu - Interessado", use_container_width=True, type="primary", key=f"fin_at_{sel['id']}"): registrar_evento(sel,"atendido","Atendeu - interessado")
                        with c2:
                            if st.button("🔴 Caixa Postal", use_container_width=True, key=f"fin_cx_{sel['id']}"): registrar_evento(sel,"nao_atendeu","Caixa postal")
                        with c3:
                            if st.button("📵 Desligado", use_container_width=True, key=f"fin_des_{sel['id']}"): registrar_evento(sel,"nao_atendeu","Desligado")
                        with c4:
                            if st.button("💰 Venda Fechada!", use_container_width=True, key=f"fin_ve_{sel['id']}"): st.balloons(); registrar_evento(sel,"venda_finalizada","Venda FGTS")
                        c5,c6,c7,c8=st.columns(4)
                        with c5:
                            if st.button("🤔 Sem interesse", use_container_width=True, key=f"fin_si_{sel['id']}"): registrar_evento(sel,"atendido","Sem interesse no momento")
                        with c6:
                            if st.button("📅 Retorno Amanhã 14h", use_container_width=True, key=f"fin_rt_{sel['id']}"):
                                amanha=(datetime.now()+timedelta(days=1)).strftime("%d/%m/%Y")
                                registrar_evento(sel,"retorno_futuro","Retornar amanhã 14h", retorno_data=amanha)
                        with c7:
                            if st.button("📅 Retorno 2 dias", use_container_width=True, key=f"fin_rt2_{sel['id']}"):
                                ret2=(datetime.now()+timedelta(days=2)).strftime("%d/%m/%Y")
                                registrar_evento(sel,"retorno_futuro","Retornar em 2 dias", retorno_data=ret2)
                        with c8:
                            if st.button("❌ Número errado", use_container_width=True, key=f"fin_er_{sel['id']}"): registrar_evento(sel,"nao_atendeu","Número errado")
                        with st.expander(f"📜 Histórico Completo {sel['nome']} - T{tent}"):
                            if sel.get("historico"):
                                for h in sel["historico"][::-1][:10]: st.caption(f"📅 {h['data']} | {h['acao']} | ⏱️ {h['tempo']} | {h['tab']}")
                            else: st.caption("🆕 Nunca ligado - primeira tentativa")
                            st.json({"ID":sel["id"],"Lote":sel.get("lote"),"DDD":sel.get("ddd"),"CPF":sel["cpf"][:6]+"***","Import":sel.get("data_import")})

# =========================================================
# TAB 2 - LOTES & IMPORTAÇÃO
# =========================================================
with tab2:
    st.markdown("## 📦 Gestão de Lotes Profissional + Auto Conversor + Higienizador")
    col_imp1,col_imp2=st.columns([2,1])
    with col_imp1:
        st.markdown("#### 📥 Importação Inteligente - Várias Planilhas de Uma Vez")
        st.info("✅ Aceita: CSV, XLSX (conversão automática sem openpyxl), XLS | Auto higienizador DDD + Não Perturbe + Duplicados")
        arquivos=st.file_uploader("Arraste várias planilhas aqui (drag & drop)", type=["csv","xlsx","xls"], accept_multiple_files=True, key="import_ultimate")
        if arquivos:
            dfs,erros=[],[]
            for arq in arquivos:
                try: df_arq=ler_planilha(arq); dfs.append((arq.name, df_arq))
                except Exception as e: erros.append(f"{arq.name}: {e}")
            if erros: 
                for err in erros: st.error(err)
            if dfs:
                total_linhas=sum(len(df) for _,df in dfs)
                st.success(f"📦 {len(dfs)} planilha(s) | {total_linhas} linhas totais | Conversão automática OK")
                # Preview
                for nome,df in dfs:
                    with st.expander(f"📄 {nome}: {len(df)} linhas - Preview"):
                        st.dataframe(df.head(5), use_container_width=True)
                        st.caption(f"Colunas: {', '.join(df.columns[:6])}")
                # Botões importação
                c1,c2,c3=st.columns(3)
                with c1:
                    if st.button("✅ IMPORTAR TUDO com Higienizador + Não Perturbe", type="primary", use_container_width=True):
                        existentes=set([l["id"] for l in st.session_state.leads])
                        nao_pert_set=set(st.session_state.nao_perturbe)
                        total_importados=0
                        relatorio=[]
                        for nome,df in dfs:
                            lote_id=hashlib.sha256(f"{nome}{datetime.now()}".encode()).hexdigest()[:8]
                            novos,ig_tel,ig_bloq,ig_dup,ig_ddd,ig_np=montar_novos_leads(df.copy(), existentes, st.session_state.blocklist, nao_pert_set, nome)
                            st.session_state.leads.extend(novos)
                            total_importados+=len(novos)
                            st.session_state.lotes.append({
                                "id":lote_id,"nome":nome,"data":datetime.now().strftime("%d/%m %H:%M:%S"),
                                "qtd":len(df),"importados":len(novos),"ignorados":ig_tel+ig_bloq+ig_dup+ig_ddd+ig_np,
                                "detalhe":f"Tel:{ig_tel} Bloq:{ig_bloq} Dup:{ig_dup} DDD:{ig_ddd} NP:{ig_np}"
                            })
                            relatorio.append({"Planilha":nome,"Total":len(df),"Importados":len(novos),"Tel Inv":ig_tel,"Bloq":ig_bloq,"Dup":ig_dup,"DDD":ig_ddd,"Não Perturbe":ig_np,"Aprov":f"{len(novos)/len(df)*100:.1f}%" if len(df)>0 else "0%"})
                        salvar_dados()
                        st.success(f"✅ {total_importados} leads importados de {len(dfs)} planilhas")
                        st.dataframe(pd.DataFrame(relatorio), use_container_width=True)
                        st.rerun()
                with c2:
                    if st.button("🧹 Só Ver Relatório Higienização", use_container_width=True):
                        existentes=set([l["id"] for l in st.session_state.leads])
                        nao_pert_set=set(st.session_state.nao_perturbe)
                        rel=[]
                        for nome,df in dfs:
                            novos,ig_tel,ig_bloq,ig_dup,ig_ddd,ig_np=montar_novos_leads(df.copy(), existentes.copy(), st.session_state.blocklist, nao_pert_set, nome)
                            rel.append({"Planilha":nome,"Linhas":len(df),"Válidos":len(novos),"Tel Inv":ig_tel,"Bloq":ig_bloq,"Dup":ig_dup,"DDD":ig_ddd,"NP":ig_np,"Aprov":f"{len(novos)/len(df)*100:.1f}%"})
                        st.dataframe(pd.DataFrame(rel), use_container_width=True)
                with c3:
                    if st.button("💾 Baixar CSVs Convertidos", use_container_width=True):
                        for nome,df in dfs:
                            csv=df.to_csv(index=False).encode("utf-8")
                            st.download_button(f"⬇️ {nome}.csv", csv, file_name=f"{nome}.csv", mime="text/csv", key=f"dl_conv_{nome}")
    with col_imp2:
        st.markdown("#### 📦 Lotes Ativos")
        if st.session_state.lotes:
            for lote in st.session_state.lotes[-20:][::-1]:
                st.markdown(f"<div class='lote-card'><b>📦 {lote['nome'][:20]}</b><br>📅 {lote['data']}<br>📱 {lote['qtd']} → ✅ {lote.get('importados',0)} | ❌ {lote.get('ignorados',0)}<br><small>{lote.get('detalhe','')}</small></div>", unsafe_allow_html=True)
                c1,c2,c3=st.columns(3)
                with c1:
                    if st.button(f"🗑️", key=f"del_lote_tab2_{lote['id']}", help="Excluir lote"): 
                        st.session_state.leads=[l for l in st.session_state.leads if l.get('lote')!=lote['nome']]
                        st.session_state.lotes=[lt for lt in st.session_state.lotes if lt['id']!=lote['id']]
                        salvar_dados(); st.success(f"Excluído {lote['nome']}"); st.rerun()
                with c2:
                    if st.button(f"📊", key=f"stats_lote_{lote['id']}", help="Ver stats"):
                        df_lote=[l for l in st.session_state.leads if l.get('lote')==lote['nome']]
                        st.json({"Total":len(df_lote),"Pend":len([x for x in df_lote if x["status"]=="pendente"]),"Vendas":len([x for x in df_lote if x["status"]=="venda_finalizada"])})
                with c3:
                    df_lote_pd=pd.DataFrame([l for l in st.session_state.leads if l.get('lote')==lote['nome']])
                    if not df_lote_pd.empty:
                        csv=df_lote_pd.to_csv(index=False).encode("utf-8")
                        st.download_button(f"⬇️", csv, file_name=f"{lote['nome']}_export.csv", mime="text/csv", key=f"dl_tab2_{lote['id']}", help="Exportar lote")
        else:
            st.caption("Nenhum lote importado ainda")

# =========================================================
# TAB 3 - RELATÓRIOS
# =========================================================
with tab3:
    st.markdown("## 📊 Relatórios Profissionais - Futurista")
    if not st.session_state.leads:
        st.info("Sem dados ainda")
    else:
        df_all=pd.DataFrame(st.session_state.leads)
        # KPIs
        c1,c2,c3,c4=st.columns(4)
        with c1:
            taxa_conv=len(df_all[df_all["status"]=="venda_finalizada"])/max(len(df_all[df_all["status"]!="pendente"]),1)*100
            st.metric("Taxa Conversão", f"{taxa_conv:.1f}%")
        with c2:
            tmo=df_all["duracao_seg"].sum()/max(len(df_all[df_all["status"]!="pendente"]),1)
            st.metric("TMO Médio", formatar_tempo(tmo))
        with c3:
            tempo_total=df_all["duracao_seg"].sum()
            st.metric("Tempo Total Falado", formatar_tempo(tempo_total))
        with c4:
            st.metric("Blocklist + Não Perturbe", f"{len(st.session_state.blocklist)+len(st.session_state.nao_perturbe)}")

        # Gráficos
        col_g1,col_g2=st.columns(2)
        with col_g1:
            st.markdown("#### 🏦 Vendas por Banco")
            vendas_banco=df_all[df_all["status"]=="venda_finalizada"]["banco"].value_counts()
            if not vendas_banco.empty: st.bar_chart(vendas_banco)
            else: st.caption("Sem vendas ainda")
        with col_g2:
            st.markdown("#### 🔢 Leads por Tentativas")
            tent_counts=df_all["tentativas"].value_counts().sort_index()
            st.bar_chart(tent_counts)

        col_g3,col_g4=st.columns(2)
        with col_g3:
            st.markdown("#### 📦 Leads por Lote")
            lote_counts=df_all["lote"].value_counts()
            st.bar_chart(lote_counts)
        with col_g4:
            st.markdown("#### 📊 Status Geral")
            status_counts=df_all["status"].value_counts()
            st.bar_chart(status_counts)

        st.markdown("#### ⏰ Pausas do Dia")
        if st.session_state.pausas:
            st.dataframe(pd.DataFrame(st.session_state.pausas[-20:]), use_container_width=True)
        else: st.caption("Sem pausas registradas")

        # Exportações
        st.markdown("#### 📥 Exportações Avançadas")
        e1,e2,e3,e4=st.columns(4)
        with e1:
            csv=df_all.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ CSV Geral Completo", csv, file_name=f"BRS_ULTIMATE_{datetime.now().strftime('%d%m%Y_%H%M')}.csv", mime="text/csv", use_container_width=True)
        with e2:
            df_vendas=df_all[df_all["status"]=="venda_finalizada"]
            if not df_vendas.empty:
                csv_v=df_vendas.to_csv(index=False).encode("utf-8")
                st.download_button("💰 Só VENDAS", csv_v, file_name=f"VENDAS_{datetime.now().strftime('%d%m%Y')}.csv", mime="text/csv", use_container_width=True)
        with e3:
            df_pend=df_all[df_all["status"]=="pendente"]
            if not df_pend.empty:
                csv_p=df_pend.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Só PENDENTES", csv_p, file_name=f"PENDENTES_{datetime.now().strftime('%d%m%Y')}.csv", mime="text/csv", use_container_width=True)
        with e4:
            # Backup JSON
            json_backup=json.dumps({"leads":st.session_state.leads,"pausas":st.session_state.pausas,"bloqueados":list(st.session_state.blocklist),"lotes":st.session_state.lotes}, ensure_ascii=False, indent=2).encode("utf-8")
            st.download_button("💾 Backup JSON", json_backup, file_name=f"BACKUP_BRS_{datetime.now().strftime('%d%m%Y_%H%M')}.json", mime="application/json", use_container_width=True)

# =========================================================
# TAB 4 - CONFIG & COMPLIANCE ANATEL
# =========================================================
with tab4:
    st.markdown("## ⚙️ Configurações Profissionais + Compliance Anatel Não Perturbe")
    col_c1,col_c2=st.columns(2)
    with col_c1:
        st.markdown("#### 🛡️ Não Perturbe Anatel - Compliance")
        st.info("Importe lista oficial de https://www.naomeperturbe.com.br (login CNPJ) - Números nessa lista NÃO serão discados, evita multa R$50k")
        st.metric("Números Não Perturbe Bloqueados", len(st.session_state.nao_perturbe))
        st.metric("Blocklist Interna", len(st.session_state.blocklist))
        arquivo_np=st.file_uploader("📥 Subir CSV Não Perturbe Oficial (coluna TELEFONE)", type=["csv","xlsx"], key="np_upload")
        if arquivo_np:
            try:
                df_np=ler_planilha(arquivo_np)
                df_np.columns=[str(c).upper().strip() for c in df_np.columns]
                col_tel_np=next((c for c in df_np.columns if "TEL" in c or "FONE" in c), df_np.columns[0])
                novos_np=0
                for _,row in df_np.iterrows():
                    tel="".join(filter(str.isdigit, str(row.get(col_tel_np,""))))
                    if len(tel)>=10 and tel not in st.session_state.nao_perturbe:
                        st.session_state.nao_perturbe.append(tel)
                        novos_np+=1
                salvar_dados()
                st.success(f"✅ {novos_np} números Não Perturbe adicionados - Agora estão bloqueados na discagem")
            except Exception as e: st.error(f"Erro: {e}")

        if st.button("🗑️ Limpar Lista Não Perturbe", use_container_width=True):
            st.session_state.nao_perturbe=[]; salvar_dados(); st.success("Lista Não Perturbe limpa"); st.rerun()

        st.markdown("#### 🧹 Ações em Massa - Profissional")
        if st.button("🚫 Quarentena Automática: Caixa 3x+ → Não Atendeu", use_container_width=True):
            qtd=0
            for l in st.session_state.leads:
                if l.get("tentativas",0)>=3 and "caixa" in l.get("observacao","").lower() and l["status"]=="pendente":
                    l["status"]="nao_atendeu"; qtd+=1
            salvar_dados(); st.success(f"✅ {qtd} leads em quarentena")
        if st.button("🔄 Resetar Tentativas: Zerar T0 todos pendentes", use_container_width=True):
            for l in st.session_state.leads:
                if l["status"]=="pendente": l["tentativas"]=0; l["ultima"]="Nunca"
            salvar_dados(); st.success("Tentativas resetadas"); st.rerun()
        if st.button("🗑️ Limpar SÓ PENDENTES (mantém vendas)", use_container_width=True):
            st.session_state.leads=[l for l in st.session_state.leads if l["status"]!="pendente"]; salvar_dados(); st.success("Pendentes limpos"); st.rerun()
        if st.button("💣 RESET TOTAL - Apagar TUDO (com confirmação)", use_container_width=True):
            if st.checkbox("⚠️ CONFIRMO APAGAR TUDO - backup feito?"):
                st.session_state.leads=[]; st.session_state.lotes=[]; st.session_state.pausas=[]; salvar_dados(); st.success("Tudo apagado"); st.rerun()

    with col_c2:
        st.markdown("#### ⚙️ Filtros Avançados")
        st.session_state.filtro_banco=st.selectbox("🏦 Filtrar por Banco", ["TODOS"]+sorted(list(set([l["banco"] for l in st.session_state.leads]))) if st.session_state.leads else ["TODOS"], key="f_banco_cfg")
        st.session_state.filtro_status=st.selectbox("📊 Filtrar por Status", ["PENDENTES","ATENDIDOS","NÃO ATENDEU","RETORNOS","VENDAS","TODOS","QUARENTENA"], key="f_status_cfg")
        st.session_state.filtro_tentativas=st.selectbox("🔢 Filtrar por Tentativas", ["TODAS","NUNCA LIGADOS (T0)","T1 (1 tentativa)","T2 (2 tentativas)","T3+ (3 ou mais)","T0+T1 (novos)","T2+ (reciclagem)"], key="f_tent_cfg")
        st.session_state.ordenar_por=st.selectbox("📈 Ordenar por", ["NUNCA LIGADOS PRIMEIRO","MENOS TENTATIVAS PRIMEIRO","MAIS TENTATIVAS PRIMEIRO","NOME A-Z","BANCO QUE MAIS VENDE"], key="f_ord_cfg")
        ddds=sorted(list(set([l.get("ddd","") for l in st.session_state.leads if l.get("ddd")])) ) if st.session_state.leads else []
        st.session_state.filtro_ddd=st.selectbox("📍 Filtrar por DDD", ["TODOS"]+ddds, key="f_ddd_cfg")
        st.session_state.busca_global=st.text_input("🔍 Busca Global (nome, banco, lote, telefone)", placeholder="Ex: João, PAN, 11 9...", key="busca_cfg")

        st.markdown("#### 📱 Backup & Restore")
        backup_file=st.file_uploader("📥 Restaurar Backup JSON", type=["json"], key="backup_restore")
        if backup_file:
            try:
                dados=json.load(backup_file)
                st.session_state.leads=dados.get("leads",[]); st.session_state.pausas=dados.get("pausas",[]); st.session_state.blocklist=set(dados.get("bloqueados",[])); st.session_state.lotes=dados.get("lotes",[]); st.session_state.nao_perturbe=dados.get("nao_perturbe",[])
                salvar_dados(); st.success(f"✅ Backup restaurado: {len(st.session_state.leads)} leads"); st.rerun()
            except Exception as e: st.error(f"Erro restore: {e}")

        st.markdown("#### 💡 Dicas Profissionais")
        st.markdown("""
        - **Comece o dia com T0**: Filtro NUNCA LIGADOS → Próximo Inteligente
        - **DDD 11, 21, 47 vendem mais**: Filtre DDD
        - **Quarentena**: Use todo dia fim de expediente
        - **Não Perturbe**: Importe CSV oficial 1x por semana
        - **Lotes**: Exclua lote que não converte
        - **Backup**: Faça 1x ao dia
        """)

# MINI DASH FIXO FUTURISTA
if st.session_state.leads:
    df_all=pd.DataFrame(st.session_state.leads)
    pend=len(df_all[df_all["status"]=="pendente"]); nunca=len(df_all[(df_all["status"]=="pendente") & (df_all["ultima"]=="Nunca")]); vendas=len(df_all[df_all["status"]=="venda_finalizada"]); tempo_total=df_all["duracao_seg"].sum()
    tmo=tempo_total/max(len(df_all[df_all["status"]!="pendente"]),1)
    st.markdown(f'<div class="mini-dash">📥 {pend} pend | 🆕 {nunca} nunca | ⏱️ TMO {formatar_tempo(tmo)} | 💰 {vendas} vendas | 📦 {len(st.session_state.lotes)} lotes | 🛡️ NP {len(st.session_state.nao_perturbe)} | 🚀 v6.0 ULTIMATE</div>', unsafe_allow_html=True)
