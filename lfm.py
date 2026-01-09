import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM - Manager League", layout="wide", page_icon="⚽")

# --- CONFIGURAZIONE LEGHE (Modifica i nomi qui sotto) ---
LEGHE = {
    "Lega A": ["Reggina Calcio 1914", "Villarreal", "As Roma", "Borussia Mgladbach", "Valencia", "Tottenham Hotspur", "Chelsea", "Udinese", "Sampdoria", "Hoffenheim"],
    "Lega B": ["Inter", "Napoli", "Deportivo La Coruna", "West Ham United", "Atletico Madrid", "Arsenal", "Manchester City", "Milan", "Liverpool", "Juventus"],
    "Lega C": ["Real Madrid", "Fiorentina", "Barcelona", "Lazio", "Bayern Munchen", "Atalanta", "Paris Saint Germain", "Manchester United", "Parma", "Bologna"],
    "Lega D": ["Monza", "Como", "Venezia", "Empoli", "Verona", "Cagliari", "Lecce", "Genoa", "Torino", "Red Bull Lipsia"]
}

@st.cache_data
def carica_dati():
    for codifica in ['latin1', 'cp1252', 'utf-8']:
        try:
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=codifica)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=codifica)
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            df_merged = pd.merge(df_rose, df_quot, on='Id', how='left')
            
            # Assegnazione manuale della Lega
            def assegna_lega(squadra):
                for nome_lega, lista_squadre in LEGHE.items():
                    if squadra in lista_squadre:
                        return nome_lega
                return "Senza Lega"
            
            df_merged['Lega'] = df_merged['Squadra_LFM'].apply(assegna_lega)
            return df_merged
        except:
            continue
    return None

try:
    dati = carica_dati()
    if dati is not None:
        st.sidebar.header("🏆 Filtri Lega")
        
        # Filtro per Lega nella Sidebar
        lega_selezionata = st.sidebar.selectbox("Seleziona la Lega:", ["Tutte"] + list(LEGHE.keys()))
        
        if lega_selezionata != "Tutte":
            dati_filtrati = dati[dati['Lega'] == lega_selezionata]
        else:
            dati_filtrati = dati

        modalita = st.sidebar.radio("Cosa vuoi visualizzare?", ["🔍 Cerca Giocatore", "📋 Rosa Squadra"])

        if modalita == "🔍 Cerca Giocatore":
            st.title(f"🔍 Ricerca - {lega_selezionata}")
            input_utente = st.text_input("Nome giocatore:")
            if input_utente:
                risultati = dati_filtrati[dati_filtrati['Nome'].str.contains(input_utente, case=False, na=False)]
                st.dataframe(risultati[['Nome', 'R', 'Squadra_LFM', 'Prezzo_Asta', 'FVM', 'Lega']], use_container_width=True)

        else:
            st.title(f"📋 Rose {lega_selezionata}")
            elenco_squadre = sorted(dati_filtrati['Squadra_LFM'].unique())
            squadra_scelta = st.selectbox("Seleziona squadra:", elenco_squadre)
            
            if squadra_scelta:
                df_sq = dati_filtrati[dati_filtrati['Squadra_LFM'] == squadra_scelta]
                st.metric("Valore Totale FVM Rosa", f"{int(df_sq['FVM'].sum())} cr")
                st.table(df_sq[['Nome', 'R', 'Prezzo_Asta', 'FVM']])
    else:
        st.error("Errore nel caricamento file.")
except Exception as e:
    st.error(f"Errore: {e}")
