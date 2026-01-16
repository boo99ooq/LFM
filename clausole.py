import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math
from datetime import datetime

# --- 1. CONFIGURAZIONE ---
SCADENZA = datetime(2026, 8, 1) 
OGGI = datetime.now()
PORTALE_APERTO = OGGI >= SCADENZA
ADMIN_SQUADRE = ["Liverpool Football Club", "Villarreal", "Reggina Calcio 1914", "Siviglia"]

try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except:
    st.error("Errore configurazione GitHub.")
    st.stop()

# --- 2. FUNZIONI ---
def carica_csv(file_name):
    try:
        content = repo.get_contents(file_name)
        return pd.read_csv(StringIO(content.decoded_content.decode("latin1")))
    except: return pd.DataFrame()

def salva_file_github(path, df, msg):
    csv_buffer = df.to_csv(index=False)
    f = repo.get_contents(path)
    repo.update_file(path, msg, csv_buffer, f.sha)

def registra_richiesta_scippo(acquirente, proprietario, player_id, nome, costo):
    path = "richieste_scippo.csv"
    orario = datetime.now().strftime("%H:%M:%S")
    nuova_riga = f"{acquirente},{proprietario},{player_id},{nome},{costo},PENDENTE,{orario}\n"
    try:
        f = repo.get_contents(path)
        contenuto = f.decoded_content.decode("utf-8") + nuova_riga
        repo.update_file(path, f"Scippo: {nome} alle {orario}", contenuto, f.sha)
    except:
        header = "Acquirente,Proprietario,Id,Nome,Costo,Stato,Orario\n"
        repo.create_file(path, "Init Scippi", header + nuova_riga)

def calcola_tassa(valore):
    if valore <= 200: tassa = valore * 0.10
    elif valore <= 300: tassa = 20 + (valore - 200) * 0.15
    else: tassa = 20 + 15 + (valore - 300) * 0.20
    return math.ceil(tassa)

# --- 3. UI ---
st.set_page_config(page_title="LFM - Portale Clausole", layout="wide")
st.markdown("""<style>
    .player-name { color: #1E3A8A; font-size: 2.5rem !important; font-weight: 900; text-transform: uppercase; }
    input[type="number"] { font-size: 2.5rem !important; font-weight: 900 !important; color: #1E3A8A !important; }
    .budget-box { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #1E3A8A; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
</style>""", unsafe_allow_html=True)

if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

df_leghe = carica_csv("leghe.csv")

if not st.session_state.loggato:
    st.title("🛡️ LFM - Accesso")
    lega = st.selectbox("Lega", df_leghe['Lega'].unique())
    squadra = st.selectbox("Squadra", df_leghe[df_leghe['Lega'] == lega]['Squadra'].unique())
    pin = st.text_input("PIN", type="password")
    if st.button("ACCEDI"):
        pin_r = df_leghe[df_leghe['Squadra'] == squadra]['PIN'].values[0]
        if str(pin) == str(pin_r):
            st.session_state.loggato = True
            st.session_state.squadra = squadra
            st.rerun()
        else: st.error("PIN errato.")
else:
    # --- ADMIN ---
    if st.session_state.squadra in ADMIN_SQUADRE:
        with st.sidebar:
            if st.checkbox("Gestisci Scippi"):
                df_sc = carica_csv("richieste_scippo.csv")
                if not df_sc.empty:
                    for i, r in df_sc[df_sc['Stato']=='PENDENTE'].iterrows():
                        st.warning(f"{r['Orario']} - {r['Acquirente']} su {r['Nome']}")
                        if st.button(f"APPROVA {i}"):
                            # Logica aggiornamento file (Crediti e Roster)
                            df_l = carica_csv("leghe.csv")
                            df_l.loc[df_l['Squadra'] == r['Acquirente'], 'Crediti'] -= r['Costo']
                            df_l.loc[df_l['Squadra'] == r['Proprietario'], 'Crediti'] += r['Costo']
                            salva_file_github("leghe.csv", df_l, "Update Crediti")
                            
                            df_ros = carica_csv("fantamanager-2021-rosters.csv")
                            df_ros.loc[df_ros['Id'].astype(str) == str(r['Id']), 'Squadra_LFM'] = r['Acquirente']
                            salva_file_github("fantamanager-2021-rosters.csv", df_ros, "Update Roster")
                            
                            df_sc.at[i, 'Stato'] = 'APPROVATO'
                            salva_file_github("richieste_scippo.csv", df_sc, "Scippo OK")
                            st.rerun()

    # --- TABELLONE (MERCATO APERTO) ---
    if PORTALE_APERTO:
        st.title("🔓 Mercato Clausole Aperto")
        lega_sel = st.selectbox("Filtra Lega", df_leghe['Lega'].unique())
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

        for sq in df_leghe[df_leghe['Lega'] == lega_sel]['Squadra']:
            sq_cred = df_leghe[df_leghe['Squadra'] == sq]['Crediti'].values[0]
            with st.expander(f"🏟️ {sq.upper()} (Budget: {sq_cred} cr)"):
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
                    # Logica Clausola d'ufficio = FVM
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

    # --- BLINDAGGIO (MERCATO CHIUSO) ---
    else:
        # (Qui rimane il codice del blindaggio con numeri giganti visto prima)
        pass
