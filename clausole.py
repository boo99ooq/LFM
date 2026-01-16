import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math

# 1. CONFIGURAZIONE GITHUB
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["REPO_NAME"]
g = Github(TOKEN)
repo = g.get_repo(REPO_NAME)

# 2. INSERISCI QUI LA FUNZIONE
def carica_csv_da_github(file_name):
    content = repo.get_contents(file_name)
    # decode("latin1") risolve l'errore Unicode che hai ricevuto
    decoded_content = content.decoded_content.decode("latin1") 
    return pd.read_csv(StringIO(decoded_content))

# 3. IL RESTO DEL CODICE CHE USA LA FUNZIONE
st.title("🛡️ LFM - Portale Clausole")

# Esempio di utilizzo:
df_quot = carica_csv_da_github("quot.csv")
df_leghe = carica_csv_da_github("leghe.csv")
df_rosters = carica_csv_da_github("fantamanager-2021-rosters.csv")

# ... continua il codice ...

# --- FUNZIONI TECNICHE ---
def calcola_commissione(valore):
    """Calcola la tassa a scaglioni: 10% fino a 200, 15% fino a 300, 20% oltre."""
    tassa = 0
    if valore <= 200:
        tassa = valore * 0.10
    elif valore <= 300:
        tassa = (200 * 0.10) + (valore - 200) * 0.15
    else:
        tassa = (200 * 0.10) + (100 * 0.15) + (valore - 300) * 0.20
    return math.ceil(tassa)

# --- CARICAMENTO DATI (Simulato dai tuoi CSV) ---
# In produzione useremo la funzione carica_csv_da_github() definita prima
# Prova prima con latin1, che risolve il 90% dei casi con nomi accentati
df_quot = pd.read_csv("quot.csv", encoding='latin1')

# Se hai lo stesso errore anche sugli altri file, aggiungilo anche lì:
df_leghe = pd.read_csv("leghe.csv", encoding='latin1')
df_rosters = pd.read_csv("fantamanager-2021-rosters.csv", encoding='latin1')

# --- LOGIN STEP 1: SCELTA LEGA E SQUADRA ---
col1, col2 = st.columns(2)
with col1:
    lega_scelta = st.selectbox("Seleziona la tua Lega", df_leghe['Lega'].unique())
with col2:
    squadre_filtrate = df_leghe[df_leghe['Lega'] == lega_scelta]['Squadra'].unique()
    squadra_scelta = st.selectbox("Seleziona la tua Squadra", squadre_filtrate)

pin = st.text_input("Inserisci PIN Squadra", type="password")

if pin == "1234": # Esempio di PIN
    st.success(f"Accesso autorizzato: {squadra_scelta}")
    
    # --- LOGICA INCROCIO FILE ---
    # 1. Trovo gli ID dei giocatori della squadra dal roster
    ids_squadra = df_rosters[df_rosters['Squadra_LFM'] == squadra_scelta]['Id'].tolist()
    
    # 2. Prendo i dettagli di questi giocatori da quot.csv
    giocatori_squadra = df_quot[df_quot['Id'].isin(ids_squadra)].copy()
    
    # 3. Identifico i 3 Top Player per FVM (come da regolamento)
    top_3_default = giocatori_squadra.nlargest(3, 'FVM')
    
    st.subheader("I tuoi 3 Top Player (per FVM)")
    st.write("Puoi confermare questi o sceglierne altri tra i tuoi migliori 10.")

    scelti = st.multiselect("Seleziona i 3 da blindare:", 
                            giocatori_squadra.nlargest(10, 'FVM')['Nome'].tolist(), 
                            default=top_3_default['Nome'].tolist(),
                            max_selections=3)

    if len(scelti) == 3:
        totale_commissioni = 0
        clausole_finali = {}

        for nome in scelti:
            fvm_player = giocatori_squadra[giocatori_squadra['Nome'] == nome]['FVM'].values[0]
            clausola = st.number_input(f"Clausola per {nome} (FVM: {fvm_player})", 
                                       min_value=int(fvm_player), 
                                       value=int(fvm_player * 2))
            
            tassa = calcola_commissione(clausola)
            totale_commissioni += tassa
            clausole_finali[nome] = clausola
            st.caption(f"Costo blindaggio per {nome}: {tassa} cr")

        # --- CALCOLO BONUS 60 ---
        spesa_reale = max(0, totale_commissioni - 60)
        
        st.divider()
        st.metric("Totale Tasse Blindaggio", f"{totale_commissioni} cr")
        st.metric("Costo netto su Budget Asta (Bonus 60cr applicato)", f"{spesa_reale} cr")

        if st.button("Consegna e Cripta su GitHub"):
            # Qui inseriremo la funzione save_to_github() con il tuo TOKEN
            st.warning("Salvataggio in corso nel database segreto...")
            # save_to_github(...)
            st.balloons()
# --- LOGICA DI AUTENTICAZIONE ---
def check_login(squadra_scelta, pin_inserito):
    # In una versione avanzata, leggiamo da un file 'credenziali.csv'
    # Per ora facciamo un esempio: ogni squadra ha come PIN 'LFM' + le ultime 3 lettere del nome
    pin_corretto = "LFM2026" # Esempio di PIN universale per il primo test
    return pin_inserito == pin_corretto

# --- INTERFACCIA DI LOGIN ---
if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

if not st.session_state.loggato:
    st.subheader("🔑 Accesso Area Riservata")
    
    # 1. Scelta Lega e Squadra
    lega = st.selectbox("Seleziona la tua Lega", df_leghe['Lega'].unique())
    squadre = df_leghe[df_leghe['Lega'] == lega]['Squadra'].unique()
    squadra = st.selectbox("Seleziona la tua Squadra", squadre)
    
    # 2. Inserimento PIN
    pin = st.text_input("Inserisci il PIN della tua Squadra", type="password")
    
    if st.button("Entra"):
        if check_login(squadra, pin):
            st.session_state.loggato = True
            st.session_state.squadra = squadra
            st.rerun() # Ricarica l'app in stato 'loggato'
        else:
            st.error("PIN errato. Contatta l'admin se l'hai dimenticato.")
else:
    # --- COSA VEDE IL MANAGER UNA VOLTA LOGGATO ---
    st.sidebar.success(f"Loggato: {st.session_state.squadra}")
    if st.sidebar.button("Logout"):
        st.session_state.loggato = False
        st.rerun()
        
    # Qui inserisci tutto il resto del codice (Scelta Top 3, Inserimento Clausole, ecc.)
    mostra_dashboard_clausole(st.session_state.squadra)
