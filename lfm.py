import streamlit as st
import pandas as pd

# 1. IMPOSTAZIONI DELLA PAGINA
st.set_page_config(page_title="LFM - Manager League", layout="wide", page_icon="⚽")

# 2. FUNZIONE PER CARICARE I DATI
@st.cache_data
def carica_dati():
    for codifica in ['latin1', 'cp1252', 'utf-8']:
        try:
            # Carichiamo le rose
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=codifica)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            
            # Carichiamo le quotazioni
            df_quot = pd.read_csv('quot.csv', encoding=codifica)
            
            # Pulizia ID e conversione
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            
            # Rimuoviamo righe di disturbo (come quelle con $)
            df_rose = df_rose.dropna(subset=['Id'])
            
            # UNIONE LEFT: tiene tutti i giocatori delle rose anche se mancano le quotazioni
            df_merged = pd.merge(df_rose, df_quot, on='Id', how='left')
            
            # Gestione nomi mancanti (giocatori che hanno lasciato la A)
            df_merged['Nome'] = df_merged['Nome'].fillna("Giocatore uscito dalla lista (ID: " + df_merged['Id'].astype(str) + ")")
            df_merged['R'] = df_merged['R'].fillna("-")
            df_merged['Qt.I'] = df_merged['Qt.I'].fillna(0)
            df_merged['FVM'] = df_merged['FVM'].fillna(0)
            
            return df_merged
        except:
            continue
    return None

# 3. INTERFACCIA
st.title("⚽ LFM - Manager League")
st.info("Nota: I giocatori che hanno lasciato la Serie A appariranno come 'Giocatori usciti dalla lista'.")

try:
    dati = carica_dati()

    if dati is not None:
        st.sidebar.header("Menu")
        modalita = st.sidebar.selectbox("Cosa vuoi fare?", ["🔍 Cerca Giocatore", "📋 Rosa Completa Squadra"])

        if modalita == "🔍 Cerca Giocatore":
            st.header("Ricerca Calciatore")
            input_utente = st.text_input("Scrivi parte del nome:")
            
            if input_utente:
                risultati = dati[dati['Nome'].str.contains(input_utente, case=False, na=False)]
                if not risultati.empty:
                    st.dataframe(risultati[['Nome', 'R', 'Squadra_LFM', 'Prezzo_Asta', 'Qt.I', 'FVM']], use_container_width=True)
                else:
                    st.warning("Nessun risultato. Se il giocatore è uscito dalla Serie A, cercalo tramite la 'Rosa Completa' della sua squadra.")

        else:
            st.header("Analisi Rose")
            elenco_squadre = sorted(dati['Squadra_LFM'].unique())
            squadra_scelta = st.selectbox("Seleziona squadra:", elenco_squadre)
            
            if squadra_scelta:
                df_sq = dati[dati['Squadra_LFM'] == squadra_scelta]
                st.table(df_sq[['Nome', 'R', 'Prezzo_Asta', 'Qt.I', 'FVM']])
    else:
        st.error("Caricamento file fallito.")
except Exception as e:
    st.error(f"Errore: {e}")
