import streamlit as st
import pandas as pd

st.set_page_config(page_title="Draft LFM Agosto", layout="wide")

def read_csv_safe(file_name):
    try:
        return pd.read_csv(file_name, encoding='utf-8')
    except:
        return pd.read_csv(file_name, encoding='ISO-8859-1')

def load_data():
    try:
        rosters = read_csv_safe('fantamanager-2021-rosters.csv')
        leghe = read_csv_safe('leghe.csv')
        quot = read_csv_safe('quot.csv')
        # Pulizia ID per sicurezza
        rosters = rosters[pd.to_numeric(rosters['Id'], errors='coerce').notna()]
        rosters['Id'] = rosters['Id'].astype(int)
        quot['Id'] = pd.to_numeric(quot['Id'], errors='coerce')
        quot = quot.dropna(subset=['Id'])
        quot['Id'] = quot['Id'].astype(int)
        return rosters, leghe, quot
    except Exception as e:
        st.error(f"Errore: {e}")
        return None, None, None

df_rosters, df_leghe, df_quot = load_data()

if df_rosters is not None:
    st.sidebar.header("Impostazioni Draft")
    campionato = st.sidebar.selectbox("Seleziona Campionato", ['Serie A', 'Premier League', 'Liga BBVA', 'Bundesliga'])
    
    # 1. Uniamo rose e leghe
    df_full = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra')
    
    # 2. Filtriamo per la lega selezionata
    df_lega = df_full[df_full['Lega'] == campionato]
    ids_occupati_in_lega = set(df_lega['Id'])
    
    st.title(f"🏆 Draft Temporaneo: {campionato}")

    # 3. IDENTIFICAZIONE ASTERISCATI
    # (Per ora confrontiamo con se stesso. Se carichi un quot.csv nuovo, vedrai i risultati)
    ids_listone_nuovo = set(df_quot['Id'])
    asteriscati_base = df_lega[~df_lega['Id'].isin(ids_listone_nuovo)]
    
    # Per mostrare chi hai perso, ci serve il nome (lo prendiamo da quot.csv o da un backup)
    asteriscati = pd.merge(asteriscati_base, df_quot[['Id', 'Nome', 'R', 'Qt.I']], on='Id', how='left')

    # 4. SVINCOLATI NELLA LEGA
    svincolati = df_quot[~df_quot['Id'].isin(ids_occupati_in_lega)]

    if asteriscati.empty:
        st.info("✅ Al momento non ci sono giocatori da sostituire in questo campionato.")
    else:
        st.subheader("📋 Ordine di Scelta (Priorità per Quotazione)")
        
        # Ordiniamo per Qt.I decrescente come da regolamento
        asteriscati_ordinati = asteriscati.sort_values(by='Qt.I', ascending=False)
        
        for index, row in asteriscati_ordinati.iterrows():
            with st.expander(f"🔴 {row['Squadra_LFM']} deve sostituire {row['Nome']} ({row['R']}) - Quota: {row['Qt.I']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Giocatore Perso:** {row['Nome']}")
                    st.write(f"**Ruolo:** {row['R']}")
                    st.write(f"**Crediti Squadra:** {row['Crediti']}")
                with col2:
                    st.write("**Migliori Sostituti Svincolati:**")
                    # Filtro: stesso ruolo e quota <=
                    filtro = (svincolati['R'] == row['R']) & (svincolati['Qt.I'] <= row['Qt.I'])
                    possibili = svincolati[filtro].sort_values(by='Qt.I', ascending=False).head(10)
                    st.dataframe(possibili[['Nome', 'Qt.I', 'FVM']])

    # Visualizzazione Squadre e Crediti (quella che avevi già)
    st.divider()
    st.subheader("💰 Situazione Crediti Campionato")
    st.table(df_leghe[df_leghe['Lega'] == campionato][['Squadra', 'Crediti']])
