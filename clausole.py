import streamlit as st
import pandas as pd
from github import Github
import base64
from datetime import datetime

# --- CONFIGURAZIONE GITHUB (Prende i dati dai Secrets di Streamlit) ---
try:
    TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_NAME = st.secrets["REPO_NAME"]
    g = Github(TOKEN)
    repo = g.get_repo(REPO_NAME)
except:
    st.error("Configura i Secrets GITHUB_TOKEN e REPO_NAME su Streamlit Cloud.")

# --- FUNZIONI DI SERVIZIO ---
def carica_csv_da_github(file_name):
    content = repo.get_contents(file_name)
    return pd.read_csv(content.download_url)

def salva_clausola_blindata(squadra, dati_clausole):
    file_path = "clausole_segrete.csv"
    messaggio = f"Update clausole segrete: {squadra}"
    
    # Crea il contenuto CSV (append o update)
    # Nota: In una versione pro, qui criptiamo i valori
    nuova_riga = f"{squadra},{dati_clausole}\n"
    
    try:
        contents = repo.get_contents(file_path)
        # Qui servirebbe una logica per non duplicare le righe della stessa squadra
        # Per ora facciamo un update semplice del file
        old_data = base64.b64decode(contents.content).decode("utf-8")
        updated_data = old_data + nuova_riga
        repo.update_file(contents.path, messaggio, updated_data, contents.sha)
    except:
        # Se il file non esiste, lo crea
        repo.create_file(file_path, "Inizializzazione file clausole", nuova_riga)

# --- INTERFACCIA APP ---
st.title("🛡️ LFM - Portale Clausole Blindato")

# 1. Identificazione Manager (Leggendo dalle tue leghe.csv)
df_leghe = carica_csv_da_github("leghe.csv")
lista_squadre = df_leghe['Squadra'].unique() # Adatta il nome colonna se diverso

squadra_scelta = st.selectbox("Seleziona la tua Squadra", lista_squadre)
pin = st.text_input("Inserisci il tuo PIN Squadra", type="password")

if pin: # Aggiungeremo controllo PIN reale nel database
    st.divider()
    
    # 2. Selezione dei 3 Top Player (Filtrando fantamanager-2021-rosters.csv)
    df_rose = carica_csv_da_github("fantamanager-2021-rosters.csv")
    rosa_squadra = df_rose[df_rose['Squadra'] == squadra_scelta]
    
    st.subheader(f"Configura i 3 Top Player di {squadra_scelta}")
    st.info("I dati inseriti rimarranno segreti fino al 31 Luglio.")

    # Qui l'app dovrebbe proporre i 3 con FVM più alto o farli scegliere
    # Per ora facciamo scelta libera tra i propri giocatori
    scelti = st.multiselect("Seleziona i 3 giocatori da sottoporre a clausola", 
                            rosa_squadra['Giocatore'].tolist(), max_selections=3)

    if len(scelti) == 3:
        clausole_dict = {}
        for g in scelti:
            # Recupera FVM da lfm.csv o quot.csv
            fvm_min = 100 # Esempio, qui andrà la logica di look-up
            val = st.number_input(f"Clausola per {g} (Min FVM: {fvm_min})", min_value=fvm_min)
            clausole_dict[g] = val
        
        if st.button("Invia Clausole (Consegna al Buio)"):
            stringa_dati = ";".join([f"{k}:{v}" for k,v in clausole_dict.items()])
            salva_clausola_blindata(squadra_scelta, stringa_dati)
            st.success("Consegna effettuata con successo su GitHub!")
            st.balloons()
