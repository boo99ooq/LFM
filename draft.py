import streamlit as st
import pandas as pd

st.set_page_config(page_title="Draft Agosto LFM", layout="wide")

st.title("⚽ Dashboard Draft di Agosto")
st.write("Caricamento dati in corso...")

# Funzione per caricare i dati in sicurezza
def load_data():
    try:
        rosters = pd.read_csv('fantamanager-2021-rosters.csv')
        leghe = pd.read_csv('leghe.csv')
        quot = pd.read_csv('quot.csv')
        return rosters, leghe, quot
    except Exception as e:
        st.error(f"Errore nel caricamento dei file: {e}")
        return None, None, None

df_rosters, df_leghe, df_quot = load_data()

if df_rosters is not None:
    st.success("Dati caricati correttamente!")
    
    # Sidebar per scegliere il campionato
    campionato = st.sidebar.selectbox("Seleziona Campionato", 
                                    ['Serie A', 'Premier League', 'Liga BBVA', 'Bundesliga'])
    
    st.header(f"Analisi per: {campionato}")
    
    # Mostriamo un'anteprima delle squadre per confermare che funzioni
    squadre_lega = df_leghe[df_leghe['Lega'] == campionato]
    st.table(squadre_lega[['Squadra', 'Crediti']])
else:
    st.warning("Assicurati che i file CSV siano nella stessa cartella del file draft.py")
