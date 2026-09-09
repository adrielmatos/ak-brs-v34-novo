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

st.set_page_config(page_title="A&K BRS v5.4.2 - AUTO CONVERSOR", layout="wide", page_icon="📱")

# =========================================================
# CONFIG GITHUB
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
    st.markdown("## 🔒 A&K BRS v5.4.2")
    senha = st.text_input("Senha de acesso", type="password")
    if st.button("Entrar", type="primary"): 
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
                    return d.get("leads",[]), d.get("pausas",[]), set(d.get("bloqueados",[])), d.get("lotes",[])
            except: return [],[],set(),[]
        return [],[],set(),[]
    try:
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        r=requests.get(GITHUB_API, headers=headers)
        if r.status_code==200:
            conteudo=r.json()
            st.session_state["_gh_sha"]=conteudo["sha"]
            dados=json.loads(base64.b64decode(conteudo["content"]).decode("utf-8"))
            return dados.get("leads",[]), dados.get("pausas",[]), set(dados.get("bloqueados",[])), dados.get("lotes",[])
        elif r.status_code==404:
            st.session_state["_gh_sha"]=None
            return [],[],set(),[]
    except Exception as e:
        st.error(f"Erro GitHub: {e}")
    return [],[],set(),[]

def salvar_dados():
    payload={"leads":st.session_state.leads,"pausas":st.session_state.pausas,"bloqueados":list(st.session_state.blocklist),"lotes":st.session_state.lotes}
    conteudo_str=json.dumps(payload, ensure_ascii=False, indent=2)
    if not GITHUB_API or not GITHUB_TOKEN:
        with open("brs_dados_local.json","w",encoding="utf-8") as f: f.write(conteudo_str)
        return
    try:
        conteudo_b64=base64.b64encode(conteudo_str.encode("utf-8")).decode("utf-8")
        headers={"Authorization": f"token {GITHUB_TOKEN}"}
        body={"message": f"Atualização {datetime.now().strftime('%d/%m %H:%M:%S')}","content": conteudo_b64}
        if st.session_state.get("_gh_sha"): body["sha"]=st.session_state["_gh_sha"]
        r=requests.put(GITHUB_API, headers=headers, json=body)
        if r.status_code in (200,201): st.session_state["_gh_sha"]=r.json()["content"]["sha"]
    except Exception as e:
        st.warning(f"Não salvou GitHub: {e}")

# =========================================================
# ESTADO
# =========================================================
if "leads" not in st.session_state:
    leads,pausas,blocklist,lotes=carregar_dados()
    st.session_state.leads=leads; st.session_state.pausas=pausas; st.session_state.blocklist=blocklist; st.session_state.lotes=lotes
    st.session_state.selected_id=None; st.session_state.auto_next=True; st.session_state.call_start={}; st.session_state.filtro_banco="TODOS"; st.session_state.filtro_status="PENDENTES"
    st.session_state.filtro_tentativas="TODAS"; st.session_state.ordenar_por="NUNCA LIGADOS PRIMEIRO"
    st.session_state.em_pausa=None; st.session_state.pausa_inicio=None; st.session_state.modo_foco=False

# =========================================================
# CONVERSOR AUTOMÁTICO XLSX -> CSV SEM OPENPYXL
# =========================================================
def ler_xlsx_sem_openpyxl(file_bytes):
    """
    Lê XLSX sem precisar de openpyxl - converte automaticamente
    XLSX é um ZIP com XMLs, dá pra ler manual
    """
    try:
        # Tenta com openpyxl se existir
        import openpyxl
        return pd.read_excel(BytesIO(file_bytes), engine='openpyxl')
    except ImportError:
        pass
    
    # SE NÃO TEM OPENPYXL, CONVERTE MANUALMENTE (AUTO CONVERSOR)
    try:
        # Método 1: tenta ler como zip/xml manual
        z = zipfile.ZipFile(BytesIO(file_bytes))
        
        # Lê shared strings
        try:
            ss_data = z.read('xl/sharedStrings.xml')
            ss_root = ET.fromstring(ss_data)
            ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            shared_strings = []
            for si in ss_root.findall('main:si', ns):
                t = si.find('main:t', ns)
                if t is not None:
                    shared_strings.append(t.text if t.text else "")
                else:
                    # texto rico
                    txt = ""
                    for t in si.findall('.//main:t', ns):
                        if t.text: txt += t.text
                    shared_strings.append(txt)
        except:
            shared_strings = []
        
        # Lê primeira planilha
        try:
            sheet_data = z.read('xl/worksheets/sheet1.xml')
            sheet_root = ET.fromstring(sheet_data)
            ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            
            rows = []
            for row in sheet_root.findall('.//main:row', ns):
                cols = []
                for c in row.findall('main:c', ns):
                    # valor
                    v = c.find('main:v', ns)
                    if v is not None and v.text:
                        # se tem shared string
                        if c.get('t') == 's' and shared_strings:
                            try:
                                idx = int(v.text)
                                cols.append(shared_strings[idx] if idx < len(shared_strings) else v.text)
                            except:
                                cols.append(v.text)
                        else:
                            cols.append(v.text)
                    else:
                        # inline string
                        is_elem = c.find('main:is', ns)
                        if is_elem is not None:
                            t = is_elem.find('main:t', ns)
                            cols.append(t.text if t is not None and t.text else "")
                        else:
                            cols.append("")
                rows.append(cols)
            
            if rows:
                # primeira linha é cabeçalho
                header = rows[0]
                data = rows[1:]
                # normaliza tamanho
                max_cols = max(len(r) for r in rows)
                for r in data:
                    while len(r) < max_cols:
                        r.append("")
                df = pd.DataFrame(data, columns=header[:max_cols] if len(header)>=max_cols else header + [f"COL_{i}" for i in range(len(header), max_cols)])
                return df
        except Exception as e:
            st.warning(f"Conversor manual falhou: {e}, tentando método alternativo")
        
        # Método 2: tenta com pandas xlrd ou outro engine
        try:
            return pd.read_excel(BytesIO(file_bytes), engine=None)
        except:
            pass
            
        raise ValueError("Não consegui converter XLSX automaticamente")
        
    except zipfile.BadZipFile:
        raise ValueError("Arquivo não é XLSX válido")

def ler_planilha(up):
    nome=up.name.lower()
    file_bytes = up.read()
    up.seek(0)
    
    if nome.endswith(".xlsx"):
        try:
            # AUTO CONVERSOR: converte XLSX pra DataFrame sem precisar openpyxl
            df = ler_xlsx_sem_openpyxl(file_bytes)
            st.success(f"✅ {up.name} convertido automaticamente (sem precisar de openpyxl) - {len(df)} linhas")
            return df
        except ImportError as e:
            if "openpyxl" in str(e).lower():
                # tenta conversor manual
                try:
                    df = ler_xlsx_sem_openpyxl(file_bytes)
                    return df
                except Exception as e2:
                    st.error(f"❌ {up.name}: openpyxl não instalado no servidor")
                    st.info("🔄 Tentando conversão automática interna...")
                    raise ValueError(f"{up.name}: Conversão automática falhou. Adicione openpyxl no requirements.txt OU salve como CSV")
            raise e
        except Exception as e:
            # se falhar, tenta conversor manual
            try:
                df = ler_xlsx_sem_openpyxl(file_bytes)
                return df
            except:
                raise e
    
    elif nome.endswith(".xls"):
        try:
            return pd.read_excel(BytesIO(file_bytes), engine='xlrd')
        except ImportError:
            try:
                return pd.read_excel(BytesIO(file_bytes))
            except Exception as e:
                st.error(f"❌ {up.name}: precisa xlrd para .xls - converta para .xlsx ou .csv")
                raise e
    
    # CSV
    for enc in ["utf-8","latin1","cp1252","iso-8859-1"]:
        for sep in [",",";","\t","|"]:
            try:
                df=pd.read_csv(BytesIO(file_bytes), encoding=enc, sep=sep)
                if len(df.columns)>1: 
                    st.success(f"✅ {up.name} lido como CSV ({enc}, sep='{sep}') - {len(df)} linhas")
                    return df
            except: continue
    raise ValueError(f"{up.name}: Não consegui ler")

def montar_novos_leads(df, existentes, bloqueados, nome_lote):
    df.columns=[str(c).upper().strip() for c in df.columns]
    col_nome=next((c for c in df.columns if "NOME" in c), df.columns[0])
    col_cpf=next((c for c in df.columns if "CPF" in c), None)
    col_tel=next((c for c in df.columns if "TELEFONE" in c or c=="TEL" or "CEL" in c or "FONE" in c), None)
    col_banco=next((c for c in df.columns if "BANCO" in c), None)
    novos, ig_tel, ig_bloq, ig_dup, ig_ddd = [],0,0,0,0
    for idx,row in df.iterrows():
        cpf=str(row.get(col_cpf,"")).strip() if col_cpf else f"semcpf{idx}"
        tel_raw=str(row.get(col_tel,"")).strip() if col_tel else ""
        tel="".join(filter(str.isdigit, tel_raw))
        if not tel or len(tel)<10: ig_tel+=1; continue
        try:
            ddd=int(tel[:2]) if len(tel)>=10 else 0
            if ddd<11 or ddd>91: ig_ddd+=1; continue
        except: ig_ddd+=1; continue
        if tel in bloqueados: ig_bloq+=1; continue
        h=hashlib.sha256(f"{cpf}{tel}".encode()).hexdigest()[:12]
        if h in existentes: ig_dup+=1; continue
        existentes.add(h)
        novos.append({
            "id":h,"nome":str(row.get(col_nome,f"Lead {idx}"))[:40],"cpf":cpf,
            "telefone":tel,"banco":str(row.get(col_banco,"PAN")).upper()[:20] if col_banco else "PAN",
            "produto":"FGTS","status":"pendente","tentativas":0,"ultima":"Nunca",
            "duracao_seg":0,"duracao_txt":"00:00","historico":[],"tabulacao":"","observacao":"","canal":"chip","custo_estimado":0.0,"retorno_data":None,
            "lote":nome_lote,"data_import":datetime.now().strftime("%d/%m %H:%M")
        })
    return novos, ig_tel, ig_bloq, ig_dup, ig_ddd

# ESTILO
st.markdown("""
<style>
.mini-dash {position:fixed;bottom:12px;right:12px;background:rgba(255,255,255,0.95);border:1px solid #e0e0e0;border-radius:12px;padding:8px 12px;box-shadow:0 4px 12px rgba(0,0,0,0.12);z-index:9999;font-size:12px;}
.foco-overlay {background:#f8fafc;border:2px solid #00c853;border-radius:16px;padding:20px;}
.lote-card {border:1px solid #e0e0e0;border-radius:10px;padding:10px;margin-bottom:8px;background:#fff;}
</style>
""", unsafe_allow_html=True)

st.markdown("## 📱 A&K BRS v5.4.2 - AUTO CONVERSOR XLSX SEM OPENPYXL")
col_h1,col_h2,col_h3,col_h4 = st.columns([2.5,1,1,1])
with col_h1:
    total=len(st.session_state.leads); pend=len([l for l in st.session_state.leads if l["status"]=="pendente"])
    nunca=len([l for l in st.session_state.leads if l["status"]=="pendente" and l.get("ultima")=="Nunca"])
    st.caption(f"📱 {total} | 📥 {pend} pend | 🆕 {nunca} nunca | 📦 {len(st.session_state.lotes)} lotes | 🔄 Auto conversor")
with col_h2: st.session_state.auto_next=st.checkbox("⏭️ Auto", value=True)
with col_h3:
    if st.button("🧠 Próximo Inteligente", use_container_width=True, type="primary"):
        nxt=proximo_inteligente(st.session_state.selected_id)
        if nxt: st.session_state.selected_id=nxt; st.session_state.modo_foco=False; st.rerun()
with col_h4:
    if st.button("🔄 Sair", use_container_width=True) and GITHUB_TOKEN: st.session_state.logado=False; st.rerun()

def formatar_tempo(seg):
    if not seg or seg<=0: return "00:00"
    m=int(seg//60); s=int(seg%60)
    if m>=60: h=m//60; m=m%60; return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def proximo_inteligente(atual_id=None):
    pend=[l for l in st.session_state.leads if l["status"]=="pendente"]
    if not pend: return None
    def score(l):
        tent=l.get("tentativas",0)
        nunca=0 if l.get("ultima")=="Nunca" else 1000
        return nunca + tent*10
    pend_sorted=sorted(pend, key=score)
    if not atual_id: return pend_sorted[0]["id"]
    ids=[l["id"] for l in pend_sorted]
    if atual_id not in ids: return pend_sorted[0]["id"]
    idx=ids.index(atual_id)
    if idx+1 < len(ids): return ids[idx+1]
    return pend_sorted[0]["id"] if len(pend_sorted)>1 else None

with st.sidebar:
    st.markdown("### 🎯 Filtros")
    banco_list=["TODOS"]+sorted(list(set([l["banco"] for l in st.session_state.leads]))) if st.session_state.leads else ["TODOS"]
    st.session_state.filtro_banco=st.selectbox("🏦 Banco", banco_list)
    st.session_state.filtro_status=st.selectbox("📊 Status", ["PENDENTES","ATENDIDOS","NÃO ATENDEU","RETORNOS","VENDAS","TODOS","QUARENTENA"])
    st.markdown("#### 🔢 Tentativas")
    st.session_state.filtro_tentativas=st.selectbox("Tentativas", ["TODAS","NUNCA LIGADOS (T0)","T1 (1 tentativa)","T2 (2 tentativas)","T3+ (3 ou mais)","T0+T1 (novos)","T2+ (reciclagem)"], label_visibility="collapsed")
    st.session_state.ordenar_por=st.selectbox("Ordenar por", ["NUNCA LIGADOS PRIMEIRO","MENOS TENTATIVAS PRIMEIRO","MAIS TENTATIVAS PRIMEIRO","NOME A-Z"], label_visibility="collapsed")
    busca=st.text_input("🔍 Buscar", placeholder="Nome, banco, lote...")
    st.markdown("---")
    st.markdown("### 📦 Gestão de Lotes")
    if st.session_state.lotes:
        for lote in st.session_state.lotes[-10:][::-1]:
            st.markdown(f"<div class='lote-card'><b>📦 {lote['nome']}</b><br>📅 {lote['data']}<br>✅ {lote.get('importados',0)}/{lote['qtd']}</div>", unsafe_allow_html=True)
            c1,c2=st.columns(2)
            with c1:
                if st.button(f"🗑️ Excluir", key=f"del_lote_{lote['id']}", use_container_width=True):
                    st.session_state.leads=[l for l in st.session_state.leads if l.get('lote')!=lote['nome']]
                    st.session_state.lotes=[lt for lt in st.session_state.lotes if lt['id']!=lote['id']]
                    salvar_dados(); st.success(f"Lote {lote['nome']} excluído"); st.rerun()
            with c2:
                if st.button(f"📋 Ver", key=f"ver_lote_{lote['id']}", use_container_width=True):
                    st.session_state.filtro_banco="TODOS"; st.rerun()
    else:
        st.caption("Nenhum lote ainda")
    st.markdown("---")
    if st.button("🚫 Quarentena Caixa 3x+", use_container_width=True):
        qtd=0
        for l in st.session_state.leads:
            if l.get("tentativas",0)>=3 and "caixa" in l.get("observacao","").lower() and l["status"]=="pendente":
                l["status"]="nao_atendeu"; qtd+=1
        salvar_dados(); st.success(f"{qtd} em quarentena")
    if st.button("🗑️ Limpar só PENDENTES", use_container_width=True):
        st.session_state.leads=[l for l in st.session_state.leads if l["status"]!="pendente"]; salvar_dados(); st.rerun()

modo_foco_ativo=st.session_state.modo_foco and st.session_state.selected_id in st.session_state.call_start if st.session_state.selected_id else False

if not st.session_state.leads:
    st.info("📥 Suba planilhas - Auto conversor XLSX sem openpyxl integrado")
    st.markdown("#### 🔄 Como funciona o Auto Conversor:")
    st.markdown("- Se você subir `.xlsx` e não tiver `openpyxl` no servidor, o sistema **converte automaticamente** lendo o arquivo ZIP/XML interno do Excel")
    st.markdown("- Se conversão automática falhar, tenta outros métodos")
    st.markdown("- Recomendado: Adicione `openpyxl` no `requirements.txt` para 100% compatibilidade, mas **agora já funciona mesmo sem**")
else:
    with st.expander("📥 SUBIR NOVAS PLANILHAS (várias) - Auto conversor", expanded=False):
        st.markdown("**Aceita:** .csv, .xlsx (conversão automática), .xls")
        arquivos=st.file_uploader("Arraste várias planilhas", type=["csv","xlsx","xls"], accept_multiple_files=True, key="import_multi")
        if arquivos:
            dfs,erros=[],[]
            for arq in arquivos:
                try: 
                    df_arq=ler_planilha(arq)
                    dfs.append((arq.name, df_arq))
                except Exception as e: erros.append(f"{arq.name}: {e}")
            if erros: 
                for err in erros: st.error(err)
            if dfs:
                total_linhas=sum(len(df) for _,df in dfs)
                st.success(f"📦 {len(dfs)} planilha(s) | {total_linhas} linhas - Conversão automática OK")
                for nome,df in dfs:
                    st.caption(f"📄 {nome}: {len(df)} linhas, colunas: {', '.join(df.columns[:4])}")
                    st.dataframe(df.head(3), use_container_width=True)
                if st.button("✅ IMPORTAR TUDO", type="primary", use_container_width=True):
                    existentes=set([l["id"] for l in st.session_state.leads])
                    total_importados=0
                    for nome,df in dfs:
                        lote_id=hashlib.sha256(f"{nome}{datetime.now()}".encode()).hexdigest()[:8]
                        novos,ig_tel,ig_bloq,ig_dup,ig_ddd=montar_novos_leads(df.copy(), existentes, st.session_state.blocklist, nome)
                        st.session_state.leads.extend(novos)
                        total_importados+=len(novos)
                        st.session_state.lotes.append({
                            "id":lote_id,"nome":nome,"data":datetime.now().strftime("%d/%m %H:%M"),
                            "qtd":len(df),"importados":len(novos),"ignorados":ig_tel+ig_bloq+ig_dup+ig_ddd,
                        })
                    salvar_dados()
                    st.success(f"✅ {total_importados} importados com conversão automática"); st.rerun()

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
    if busca and busca.lower() not in l["nome"].lower() and busca.lower() not in l["banco"].lower() and busca.lower() not in l.get("lote","").lower(): continue
    lista.append(l)

if st.session_state.ordenar_por=="NUNCA LIGADOS PRIMEIRO":
    lista=sorted(lista, key=lambda x: (0 if x.get("ultima")=="Nunca" else 1, x.get("tentativas",0)))
elif st.session_state.ordenar_por=="MENOS TENTATIVAS PRIMEIRO":
    lista=sorted(lista, key=lambda x: x.get("tentativas",0))
elif st.session_state.ordenar_por=="MAIS TENTATIVAS PRIMEIRO":
    lista=sorted(lista, key=lambda x: x.get("tentativas",0), reverse=True)
elif st.session_state.ordenar_por=="NOME A-Z":
    lista=sorted(lista, key=lambda x: x.get("nome",""))

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
        st.markdown(f"## 🎯 MODO FOCO | {sel['nome']} | 🏦 {sel['banco']} | T{sel.get('tentativas',0)}")
        decorrido=(datetime.now()-st.session_state.call_start[sel["id"]]).total_seconds()
        st.markdown(f"### ⏱️ {formatar_tempo(decorrido)} | 📱 {sel['telefone']}")
        st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:22px;border-radius:14px;text-align:center;font-weight:900;text-decoration:none;font-size:24px">📱 {sel["telefone"]} • EM LIGAÇÃO</a>', unsafe_allow_html=True)
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
        st.markdown(f"#### 📋 Fila: {st.session_state.filtro_banco} ({len(lista)}) - {st.session_state.ordenar_por}")
        pag=st.selectbox("Pág", [f"{i*80+1}-{(i+1)*80}" for i in range((len(lista)//80)+1)], key="pag")
        idx_pag=int(pag.split("-")[0])//80 if pag else 0
        for lead in lista[idx_pag*80:(idx_pag+1)*80]:
            bloqueado=lead["telefone"] in st.session_state.blocklist
            dot="🚫" if bloqueado else {"pendente":"⚪","atendido":"🟢","nao_atendeu":"🔴","retorno_futuro":"🟠","venda_finalizada":"💰"}[lead["status"]]
            is_sel=lead["id"]==st.session_state.selected_id
            tent=lead.get("tentativas",0); ultima=lead.get("ultima","Nunca")
            tent_txt=f" T{tent}" if tent>0 else " 🆕" if ultima=="Nunca" else f" T{tent}"
            if st.button(f"{'👉' if is_sel else ''}{dot} {lead['nome'][:10]} • {lead['banco']}{tent_txt}", key=f"list_{lead['id']}", use_container_width=True, type="primary" if is_sel else "secondary"):
                st.session_state.selected_id=lead["id"]; st.session_state.modo_foco=False; st.rerun()
    with col_atend:
        if not st.session_state.selected_id:
            st.info("👈 Selecione cliente ou 🧠 Próximo Inteligente")
        else:
            sel=next((l for l in st.session_state.leads if l["id"]==st.session_state.selected_id), None)
            if sel:
                tent=sel.get("tentativas",0)
                st.markdown(f"### 👤 {sel['nome']} | 🏦 {sel['banco']} | 📱 {sel['telefone']} | 🔢 T{tent}")
                em_ligacao=sel["id"] in st.session_state.call_start
                em_pausa=st.session_state.em_pausa is not None
                if em_pausa: st.error(f"⏸️ Em pausa: {st.session_state.em_pausa}")
                elif not em_ligacao:
                    col_d1,col_d2,col_d3=st.columns([1.5,1,1])
                    with col_d1:
                        if st.button(f"▶️ LIGAR CHIP • {sel['telefone']}", key=f"discar_{sel['id']}", type="primary", use_container_width=True):
                            st.session_state.call_start[sel["id"]]=datetime.now(); st.session_state.modo_foco=True; st.rerun()
                    with col_d2:
                        msg_map={"PAN":f"Olá {sel['nome']}, A&K sobre FGTS PAN liberado. Explico 1 min?","BMG":f"Olá {sel['nome']}, BMG liberou FGTS. Quer saber valor?","C6":f"Olá {sel['nome']}, C6 liberou FGTS. Explico rapidinho?"}
                        msg=msg_map.get(sel["banco"], f"Olá {sel['nome']}, A&K FGTS {sel['banco']} liberado")
                        msg_enc=urllib.parse.quote(msg)
                        st.markdown(f'<a href="https://wa.me/55{sel["telefone"]}?text={msg_enc}" target="_blank" style="display:block;background:#25D366;color:#fff;padding:12px;border-radius:8px;text-align:center;font-weight:700;text-decoration:none">💬 Zap</a>', unsafe_allow_html=True)
                    with col_d3:
                        if st.button("🚫 Não ligar mais", key=f"bloq_{sel['id']}", use_container_width=True): st.session_state.blocklist.add(sel["telefone"]); salvar_dados(); st.rerun()
                else:
                    decorrido=(datetime.now()-st.session_state.call_start[sel["id"]]).total_seconds()
                    st.warning(f"📱 EM LIGAÇÃO: {formatar_tempo(decorrido)}")
                    st.markdown(f'<a href="tel:{sel["telefone"]}" style="display:block;background:linear-gradient(90deg,#00e5ff,#00ff88);color:#000;padding:18px;border-radius:12px;text-align:center;font-weight:900;text-decoration:none;font-size:20px">📱 {sel["telefone"]} • ⏱️ {formatar_tempo(decorrido)}</a>', unsafe_allow_html=True)
                st.markdown("#### ⚡ Tabulação 1 clique")
                c1,c2,c3,c4=st.columns(4)
                with c1:
                    if st.button("✅ Atendeu", use_container_width=True, type="primary", key=f"fin_at_{sel['id']}"): registrar_evento(sel,"atendido","Atendeu - interessado")
                with c2:
                    if st.button("🔴 Caixa", use_container_width=True, key=f"fin_cx_{sel['id']}"): registrar_evento(sel,"nao_atendeu","Caixa postal")
                with c3:
                    if st.button("📵 Deslig", use_container_width=True, key=f"fin_des_{sel['id']}"): registrar_evento(sel,"nao_atendeu","Desligado")
                with c4:
                    if st.button("💰 Venda", use_container_width=True, key=f"fin_ve_{sel['id']}"): st.balloons(); registrar_evento(sel,"venda_finalizada","Venda FGTS")
                c5,c6,c7=st.columns(3)
                with c5:
                    if st.button("🤔 Sem interesse", use_container_width=True, key=f"fin_si_{sel['id']}"): registrar_evento(sel,"atendido","Sem interesse no momento")
                with c6:
                    if st.button("📅 Retorno amanhã", use_container_width=True, key=f"fin_rt_{sel['id']}"):
                        amanha=(datetime.now()+timedelta(days=1)).strftime("%d/%m/%Y")
                        registrar_evento(sel,"retorno_futuro","Retornar amanhã 14h", retorno_data=amanha)
                with c7:
                    if st.button("❌ Erro número", use_container_width=True, key=f"fin_er_{sel['id']}"): registrar_evento(sel,"nao_atendeu","Número errado")

if st.session_state.leads:
    df_all=pd.DataFrame(st.session_state.leads)
    pend=len(df_all[df_all["status"]=="pendente"]); nunca=len(df_all[(df_all["status"]=="pendente") & (df_all["ultima"]=="Nunca")]); vendas=len(df_all[df_all["status"]=="venda_finalizada"]); tempo_total=df_all["duracao_seg"].sum()
    tmo=tempo_total/max(len(df_all[df_all["status"]!="pendente"]),1)
    st.markdown(f'<div class="mini-dash">📥 {pend} | 🆕 {nunca} nunca | ⏱️ TMO {formatar_tempo(tmo)} | 💰 {vendas} | 📦 {len(st.session_state.lotes)} lotes | 🔄 Auto conv</div>', unsafe_allow_html=True)
