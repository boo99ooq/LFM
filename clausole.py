import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math
from datetime import datetime

# --- 1. CONFIGURAZIONE TEMPORALE E ADMIN ---
SCADENZA = datetime(2025, 8, 1) 
OGGI = datetime.now()
PORTALE_APERTO = OGGI >= SCADENZA
ADMIN_SQUADRE = ["Liverpool Football Club", "Villarreal", "Reggina Calcio 1914", "Siviglia"]

try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error(f"Errore configurazione GitHub Secrets: {e}")
    st.stop()

# --- 2. FUNZIONI DI SUPPORTO ---
def carica_csv(file_name):
    try:
        content = repo.get_contents(file_name)
        return pd.read_csv(StringIO(content.decoded_content.decode("latin1")))
    except: return pd.DataFrame()

def salva_file_github(path, df, msg):
    csv_buffer = df.to_csv(index=False)
    f = repo.get_contents(path)
    repo.update_file(path, msg, csv_buffer, f.sha)

def salva_clausola_singola(squadra, dati_stringa):
    path = "clausole_segrete.csv"
    nuova_riga = f"{squadra},{dati_stringa}"
    try:
        f = repo.get_contents(path)
        contenuto = f.decoded_content.decode("utf-8")
        righe = [r for r in contenuto.splitlines() if not r.startswith(f"{squadra},")]
        righe.append(nuova_riga)
        repo.update_file(path, f"Update {squadra}", "\n".join(righe), f.sha)
    except:
        repo.create_file(path, "Inizializzazione", nuova_riga)

def registra_richiesta_scippo(acquirente, proprietario, player_id, nome, costo):
    path = "richieste_scippo.csv"
    orario = datetime.now().strftime("%H:%M:%S")
    nuova_riga = f"{acquirente},{proprietario},{player_id},{nome},{costo},PENDENTE,{orario}\n"
    try:
        f = repo.get_contents(path)
        contenuto = f.decoded_content.decode("utf-8") + nuova_riga
        repo.update_file(path, f"Richiesta Scippo: {nome} alle {orario}", contenuto, f.sha)
    except:
        header = "Acquirente,Proprietario,Id,Nome,Costo,Stato,Orario\n"
        repo.create_file(path, "Init Scippi", header + nuova_riga)

def calcola_tassa(valore):
    if valore <= 200: tassa = valore * 0.10
    elif valore <= 300: tassa = 20 + (valore - 200) * 0.15
    else: tassa = 20 + 15 + (valore - 300) * 0.20
    return math.ceil(tassa)

def recupera_precedenti(squadra):
    try:
        f = repo.get_contents("clausole_segrete.csv")
        testo = f.decoded_content.decode("utf-8")
        for riga in testo.splitlines():
            if riga.startswith(f"{squadra},"):
                dati = riga.split(",")[1]
                return {item.split(":")[0]: int(item.split(":")[1]) for item in dati.split(";")}
    except: return {}
    return {}

# --- 3. UI E CSS ---
st.set_page_config(page_title="LFM - Portale Clausole", layout="wide")
st.markdown("""
    <style>
    .player-name { color: #1E3A8A; font-size: 2.8rem !important; font-weight: 900 !important; margin-bottom: -10px; text-transform: uppercase; }
    .fvm-sub { color: #6B7280; font-size: 1.2rem; margin-bottom: 25px; }
    div[data-baseweb="input"] { border: 3px solid #1E3A8A !important; border-radius: 15px !important; }
    input[type="number"] { font-size: 3rem !important; font-weight: 900 !important; color: #1E3A8A !important; text-align: center !important; }
    .budget-box { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #1E3A8A; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

df_leghe = carica_csv("leghe.csv")

# --- 4. ACCESSO ---
if not st.session_state.loggato:
    st.title("🛡️ LFM - Accesso Portale")
    if not df_leghe.empty:
        lega = st.selectbox("Lega", df_leghe['Lega'].unique())
        squadra = st.selectbox("Squadra", df_leghe[df_leghe['Lega'] == lega]['Squadra'].unique())
        pin = st.text_input("PIN Segreto", type="password")
        if st.button("ACCEDI"):
            pin_r = df_leghe[df_leghe['Squadra'] == squadra]['PIN'].values[0]
            if str(pin) == str(pin_r):
                st.session_state.loggato = True
                st.session_state.squadra = squadra
                st.rerun()
            else: st.error("PIN errato.")
else:
    # --- AREA ADMIN ---
    if st.session_state.squadra in ADMIN_SQUADRE:
        with st.sidebar:
            st.subheader("🕵️ Pannello Admin")
            if st.checkbox("Gestisci Scippi Pendenti"):
                df_sc = carica_csv("richieste_scippo.csv")
                if not df_sc.empty:
                    pendenti = df_sc[df_sc['Stato'] == 'PENDENTE']
                    for i, r in pendenti.iterrows():
                        st.warning(f"{r['Orario']} - {r['Acquirente']} su {r['Nome']} ({r['Costo']} cr)")
                        if st.button(f"APPROVA SCIPPO #{i}"):
                            # Update Crediti
                            df_l = carica_csv("leghe.csv")
                            df_l.loc[df_l['Squadra'] == r['Acquirente'], 'Crediti'] -= r['Costo']
                            df_l.loc[df_l['Squadra'] == r['Proprietario'], 'Crediti'] += r['Costo']
                            salva_file_github("leghe.csv", df_l, "Update Crediti")
                            # Update Roster
                            df_ros = carica_csv("fantamanager-2021-rosters.csv")
                            df_ros.loc[df_ros['Id'].astype(str) == str(r['Id']), 'Squadra_LFM'] = r['Acquirente']
                            salva_file_github("fantamanager-2021-rosters.csv", df_ros, "Update Roster")
                            # Segna Approva
                            df_sc.at[i, 'Stato'] = 'APPROVATO'
                            salva_file_github("richieste_scippo.csv", df_sc, "Scippo OK")
                            st.rerun()

    # --- 5. LOGICA MERCATO (POST SCADENZA) ---
    if PORTALE_APERTO:
        st.title("🔓 LFM - Mercato Clausole Aperto")
        lega_view = st.selectbox("Filtra Lega", df_leghe['Lega'].unique())
        my_cred = df_leghe[df_leghe['Squadra'] == st.session_state.squadra]['Crediti'].values[0]
        st.sidebar.metric("Il tuo Budget", f"{my_cred} cr")

        salvati = {}
        try:
            f = repo.get_contents("clausole_segrete.csv")
            for riga in f.decoded_content.decode("utf-8").splitlines():
                if riga.strip(): 
                    s, d = riga.split(",")
                    salvati[s] = d
        except: pass

        df_r = carica_csv("fantamanager-2021-rosters.csv")
        df_q = carica_csv("quot.csv")
        df_r['Squadra_LFM'] = df_r['Squadra_LFM'].astype(str).str.strip()
        df_q['Id'] = df_q['Id'].astype(str)

        for sq in df_leghe[df_leghe['Lega'] == lega_view]['Squadra']:
            sq_c = df_leghe[df_leghe['Squadra'] == sq]['Crediti'].values[0]
            with st.expander(f"🏟️ {sq.upper()} (Budget: {sq_c} cr)"):
                if sq in salvati:
                    for p in salvati[sq].split(";"):
                        pid, pnm, pvl = p.split(":")
                        c1, c2, c3 = st.columns([3,1,2])
                        c1.write(f"**{pnm}**"); c2.write(f"{pvl} cr")
                        if sq != st.session_state.squadra:
                            if c3.button(f"PAGA LA CLAUSOLA", key=f"p_{pid}"):
                                if my_cred >= int(pvl):
                                    registra_richiesta_scippo(st.session_state.squadra, sq, pid, pnm, pvl)
                                    st.success("Richiesta inviata!")
                                else: st.error("Budget insufficiente!")
                else:
                    st.caption("⚠️ Clausole d'ufficio applicate (FVM)")
                    ids = df_r[df_r['Squadra_LFM'] == sq]['Id'].astype(str).tolist()
                    for _, row in df_q[df_q['Id'].isin(ids)].nlargest(3, 'FVM').iterrows():
                        pid, pnm, pvl = row['Id'], row['Nome'], int(row['FVM'])
                        c1, c2, c3 = st.columns([3,1,2])
                        c1.write(f"**{pnm}**"); c2.write(f"{pvl} cr")
                        if sq != st.session_state.squadra:
                            if c3.button(f"PAGA LA CLAUSOLA", key=f"a_{pid}"):
                                if my_cred >= pvl:
                                    registra_richiesta_scippo(st.session_state.squadra, sq, pid, pnm, pvl)
                                    st.success("Richiesta inviata!")
                                else: st.error("Budget insufficiente!")

    # --- 6. LOGICA BLINDAGGIO (PRIMA DELLA SCADENZA) ---
    else:
        st.title(f"🛡️ Terminale: {st.session_state.squadra}")
        crediti_totali = df_leghe[df_leghe['Squadra'] == st.session_state.squadra]['Crediti'].values[0]
        max_rivale = df_leghe[df_leghe['Squadra'] != st.session_state.squadra]['Crediti'].max()
        
        with st.container():
            st.markdown("<div class='budget-box'>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Budget Attuale", f"{crediti_totali} cr")
            c2.metric("🔝 Max Rivali", f"{max_rivale} cr")
            c3.info(f"Soglia Blindaggio: > {max_rivale}")
            st.markdown("</div>", unsafe_allow_html=True)

        df_r = carica_csv("fantamanager-2021-rosters.csv")
        df_q = carica_csv("quot.csv")
        df_r['Squadra_LFM'] = df_r['Squadra_LFM'].astype(str).str.strip()
        df_q['Id'] = df_q['Id'].astype(str)
        
        salvati_prev = recupera_precedenti(st.session_state.squadra)
        ids_miei = df_r[df_r['Squadra_LFM'] == st.session_state.squadra]['Id'].astype(str).tolist()
        top_3 = df_q[df_q['Id'].isin(ids_miei)].copy()
        top_3['FVM'] = pd.to_numeric(top_3['FVM'], errors='coerce').fillna(0)
        top_3 = top_3.nlargest(3, 'FVM')

        tot_tasse = 0
        dati_invio = []

        for i, (_, row) in enumerate(top_3.iterrows()):
            nome, fvm, p_id = row['Nome'], int(row['FVM']), row['Id']
            # Default è FVM o il valore già salvato in precedenza
            def_val = salvati_prev.get(p_id, fvm) # Default a FVM come chiesto
            
            st.markdown(f"<div class='player-name'>{nome}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='fvm-sub'>Valore di Mercato: {fvm} cr</div>", unsafe_allow_html=True)
            
            col_cl, col_stats = st.columns([1.8, 1.5])
            with col_cl:
                val = st.number_input(f"INSERISCI CLAUSOLA", min_value=fvm, value=int(def_val), key=f"c_{p_id}")
                st.progress(min(1.0, val / max_rivale) if max_rivale > 0 else 1.0)
            with col_stats:
                st.write("") 
                t = calcola_tassa(val); tot_tasse += t
                c_t, c_s = st.columns(2)
                c_t.metric("Tassa", f"{t} cr")
                if val <= max_rivale: c_s.error("VULNERABILE")
                else: c_s.success("BLINDATO")
            dati_invio.append(f"{p_id}:{nome}:{val}")

        st.write("---")
        eccedenza = max(0, tot_tasse - 60)
        budget_residuo = crediti_totali - eccedenza

        if tot_tasse <= 60:
            st.success(f"✅ Il Bonus Lega di 60cr copre interamente le tue tasse ({tot_tasse} cr). Il tuo budget resta intatto.")
        else:
            st.warning(f"⚠️ Il Bonus Lega copre le tue tasse fino a 60cr. Eccedi il bonus di **{eccedenza} crediti** (Tasse totali: {tot_tasse} cr), che verranno scalati dal tuo budget.")

        c_fin1, c_fin2, c_fin3 = st.columns(3)
        c_fin1.metric("Totale Tasse", f"{tot_tasse} cr")
        c_fin2.metric("Franchigia Bonus", "- 60 cr")
        c_fin3.metric("Budget Rimanente", f"{budget_residuo} cr", delta=-eccedenza if eccedenza > 0 else 0)

        if st.button("📥 REGISTRA CLAUSOLE DEFINITIVAMENTE", type="primary", use_container_width=True):
            salva_clausola_singola(st.session_state.squadra, ";".join(dati_invio))
            st.success("✅ Salvataggio completato!"); st.balloons()
