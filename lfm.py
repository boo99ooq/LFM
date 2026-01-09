import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Manager", layout="wide", page_icon="⚽")

@st.cache_data
def load_and_merge():
    # Carico le rose
    df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1)
    df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
    # Carico le quotazioni
    df_quot = pd.read_csv('quot.csv')
    # Unisco
    df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
    df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
    return pd.merge(df_rose, df_quot, on='Id', how='inner')

try:
    df = load_and_merge()

    st.sidebar.title("Menu LFM")
    modalita = st.sidebar.radio("Cosa vuoi fare?", ["Cerca Giocatore", "Vedi Squadra"])

    if modalita == "Cerca Giocatore":
        st.title("🔍 Ricerca Rapida")
        nome = st.text_input("Inserisci nome giocatore:")
        if nome:
            res = df[df['Nome'].str.contains(nome, case=False, na=False)]
            st.dataframe(res[['Nome', 'R', 'Squadra_LFM', 'Prezzo_Asta', 'Qt.I', 'FVM']])

    else:
        st.title("📋 Rose League")
        squadra = st.selectbox("Seleziona Squadra LFM:", sorted(df['Squadra_LFM'].unique()))
        res_squadra = df[df['Squadra_LFM'] == squadra]
        
        # Calcolo statistiche veloci
        spesa_tot = res_squadra['Prezzo_Asta'].sum()
        valore_fvm = res_squadra['FVM'].sum()
        
        col1, col2 = st.columns(2)
        col1.metric("Crediti Spesi", f"{spesa_tot} cr")
        col2.metric("Valore FVM Totale", f"{valore_fvm} cr")
        
        st.table(res_squadra[['Nome', 'R', 'Prezzo_Asta', 'Qt.I', 'FVM']])

except Exception as e:
    st.error(f"Errore: {e}. Controlla i file sulla repository lfm!")
