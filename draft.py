import streamlit as st
import pandas as pd

st.set_page_config(page_title="Draft Agosto LFM", layout="wide")

st.title("⚽ Dashboard Draft di Agosto")
st.write("Caricamento dati in corso...")

def load_data():
    # Definiamo una piccola funzione interna per leggere i CSV con la codifica corretta
    def read_csv_safe(file_name):
        try:
            # Prova prima lo standard UTF-8
            return pd.read_csv(file_name, encoding='utf-8')
        except UnicodeDecodeError:
            # Se fallisce, prova la codifica tipica di Excel/Windows
            return pd.read_csv(file_name, encoding='ISO-8859-1')

    try:
        rosters = read_csv_safe('fantamanager-2021-rosters.csv')
        leghe = read_csv_safe('leghe.csv')
        quot = read_csv_safe('quot.csv')
        return rosters, leghe, quot
    except Exception as e:
        st.error(f"Errore critico: {e}")
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
