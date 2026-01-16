import streamlit as st
import pandas as pd
from github import Github
from io import StringIO
import math

# --- 1. CONFIGURAZIONE GITHUB (Assicurati di aver impostato i Secrets su Streamlit Cloud) ---
try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error("Errore di configurazione: Controlla i Secrets 'GITHUB_TOKEN' e 'REPO_NAME' su Streamlit Cloud.")
    st.stop()

# --- 2. FUNZIONI DI UTILITÀ ---
def carica_csv_da_github(file_name):
    """Carica un file dal repo GitHub gestendo la codifica latin1 per gli accenti."""
    try:
        content = repo.get_contents(file_name)
        decoded_content = content.decoded_content.decode("latin1") 
        return pd.read_csv(StringIO(decoded_content))
    except Exception as e:
        st.error(f"Errore nel caricamento del file {file_name}: {e}")
        return pd.DataFrame()

def calcola_tassa_blindaggio(valore):
    """Calcola la commissione progressiva (10%, 15%, 20%)."""
    tassa = 0
    if valore <= 200:
        tassa = valore * 0.10
    elif valore <= 300:
        tassa = (200 * 0.10) + (valore - 200) * 0.15
    else:
        tassa = (200 * 0.10) + (100 * 0.15) + (valore - 300) * 0.20
    return math.ceil(tassa)

def salva_su_github(squadra, dati_testo):
    """Salva le clausole inserite in un file segreto su GitHub."""
    file_path = "clausole_segrete.csv"
    commit_msg = f"Consegna clausole: {squadra}"
    nuova_riga = f"{squadra},{dati_testo}\n"
    
    try:
        contents = repo.get_contents(file_path)
        # Legge il contenuto esistente e aggiunge la nuova riga
        old_data = contents.decoded_content.decode("utf-8")
        # Nota: In produzione qui andrebbe aggiunto un controllo per non duplicare la stessa squadra
        updated_data = old_data + nuova_riga
        repo.update_file(contents.path, commit_msg, updated_data, contents.sha)
    except:
        # Se il file non esiste ancora, lo crea
        repo.create_file(file_path, "Inizializzazione clausole segrete", nuova_riga)

# --- 3. LOGICA DI AUTENTICAZIONE (Basata su PIN in leghe.csv) ---
if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

# Caricamento dati iniziali per il login
df_leghe = carica_csv_da_github("leghe.csv")

if not st.session_state.loggato:
    st.header("🔑 LFM - Accesso Blindato")
    
    lega_lista = df_leghe['Lega'].unique()
    lega_scelta = st.selectbox("Seleziona la tua Lega", lega_lista)
    
    squadre_lista = df_leghe[df_leghe['Lega'] == lega_scelta]['Squadra'].unique()
    squadra_scelta = st.selectbox("Seleziona la tua Squadra", squadre_lista)
    
    pin_input = st.text_input("Inserisci il PIN della tua squadra", type="password")
    
    if st.button("Accedi"):
        pin_reale = df_leghe[df_leghe['Squadra'] == squadra_scelta]['PIN'].values[0]
        if str(pin_input) == str(pin_reale):
            st.session_state.loggato = True
            st.session_state.squadra = squadra_scelta
            st.rerun()
        else:
            st.error("PIN Errato! Riprova.")

# --- 4. DASHBOARD MANAGER (Dopo il Login) ---
else:
    st.title(f"🛡️ Gestione Clausole: {st.session_state.squadra}")
    if st.sidebar.button("Esci / Logout"):
        st.session_state.loggato = False
        st.rerun()

    # Caricamento file per incrocio dati
    df_rosters = carica_csv_da_github("fantamanager-2021-rosters.csv")
    df_quot = carica_csv_da_github("quot.csv")

    # Identificazione ID giocatori della squadra
    ids_miei = df_rosters[df_rosters['Squadra_LFM'] == st.session_state.squadra]['Id'].tolist()
    miei_giocatori = df_quot[df_quot['Id'].isin(ids_miei)].copy()

    st.subheader("Configura i tuoi 3 Top Player")
    st.write("Scegli i 3 giocatori per i quali vuoi fissare la clausola rescissoria.")

    # Selezione dei 3 giocatori (default i 3 con FVM più alto)
    default_top = miei_giocatori.nlargest(3, 'FVM')['Nome'].tolist()
    scelti = st.multiselect("Seleziona 3 giocatori:", miei_giocatori['Nome'].tolist(), default=default_top, max_selections=3)

    if len(scelti) == 3:
        tot_tasse = 0
        risultati = []
        
        col1, col2 = st.columns(2)
        
        for i, nome in enumerate(scelti):
            fvm_p = miei_giocatori[miei_giocatori['Nome'] == nome]['FVM'].values[0]
            with col1 if i < 2 else col2:
                val_clausola = st.number_input(f"Clausola per {nome} (FVM: {fvm_p})", 
                                               min_value=int(fvm_p), 
                                               value=int(fvm_p*2), 
                                               key=nome)
                tassa = calcola_tassa_blindaggio(val_clausola)
                tot_tasse += tassa
                risultati.append(f"{nome}:{val_clausola}")

        # Calcolo Bonus
        spesa_netta = max(0, tot_tasse - 60)

        st.divider()
        st.write(f"**Totale Tasse Blindaggio:** {tot_tasse} cr")
        st.write(f"**Bonus Lega Applicato:** -60 cr")
        st.metric("Costo Netto su Budget Asta", f"{spesa_netta} cr")

        if st.button("Consegna Clausole (Segreto)"):
            stringa_finale = ";".join(risultati)
            salva_su_github(st.session_state.squadra, stringa_finale)
            st.success("Dati inviati correttamente! Le clausole rimarranno segrete fino alla pubblicazione.")
            st.balloons()
