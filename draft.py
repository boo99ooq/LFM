import streamlit as st
import pandas as pd

st.set_page_config(page_title="Draft LFM Agosto", layout="wide")

def read_csv_safe(file_name, delimiter=','):
    try:
        return pd.read_csv(file_name, encoding='utf-8', sep=delimiter)
    except:
        return pd.read_csv(file_name, encoding='ISO-8859-1', sep=delimiter)

def load_data():
    try:
        rosters = read_csv_safe('fantamanager-2021-rosters.csv')
        leghe = read_csv_safe('leghe.csv')
        quot = read_csv_safe('quot.csv')
        
        # Carichiamo il file degli esclusi (noto che usa il tabulatore \t come separatore)
        esclusi = read_csv_safe('esclusi.csv', delimiter='\t')
        # Se il file non ha intestazioni corrette, rinominiamo le colonne per trovarle
        # Basandomi sul tuo file, la prima colonna è l'ID
        esclusi.columns = ['Id', 'R', 'Nome', 'Qt.I', 'FVM']
        
        # Pulizia ID
        rosters = rosters[pd.to_numeric(rosters['Id'], errors='coerce').notna()].copy()
        rosters['Id'] = rosters['Id'].astype(int)
        
        quot['Id'] = pd.to_numeric(quot['Id'], errors='coerce')
        quot = quot.dropna(subset=['Id'])
        quot['Id'] = quot['Id'].astype(int)
        
        esclusi['Id'] = pd.to_numeric(esclusi['Id'], errors='coerce')
        esclusi = esclusi.dropna(subset=['Id'])
        esclusi['Id'] = esclusi['Id'].astype(int)
        
        return rosters, leghe, quot, esclusi
    except Exception as e:
        st.error(f"Errore nel caricamento: {e}")
        return None, None, None, None

df_rosters, df_leghe, df_quot, df_esclusi = load_data()

if df_rosters is not None:
    st.sidebar.header("Filtri Draft")
    campionato = st.sidebar.selectbox("Seleziona Campionato", ['Serie A', 'Premier League', 'Liga BBVA', 'Bundesliga'])
    
    # 1. Unione Rose e Leghe
    df_full = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra')
    df_lega = df_full[df_full['Lega'] == campionato]
    
    st.title(f"🏆 Draft Temporaneo: {campionato}")

    # 2. IDENTIFICAZIONE ASTERISCATI
    # Sono i giocatori presenti sia nelle ROSE che nel file ESCLUSI
    ids_esclusi = set(df_esclusi['Id'])
    asteriscati_base = df_lega[df_lega['Id'].isin(ids_esclusi)]
    
    # Recuperiamo i dati (Nome, Ruolo, Qt.I) dal file esclusi per la priorità
    asteriscati = pd.merge(asteriscati_base, df_esclusi[['Id', 'Nome', 'R', 'Qt.I']], on='Id', how='left')

    # 3. SVINCOLATI (Presenti nel listone quot.csv ma non nelle rose della lega)
    ids_occupati_lega = set(df_lega['Id'])
    svincolati = df_quot[~df_quot['Id'].isin(ids_occupati_lega)]

    if asteriscati.empty:
        st.info(f"✅ Ottime notizie! Nessun giocatore di {campionato} è nella lista degli esclusi.")
    else:
        st.subheader("📋 Giocatori da sostituire (In ordine di Priorità)")
        
        # Priorità per Quotazione Iniziale (Qt.I)
        asteriscati_ordinati = asteriscati.sort_values(by='Qt.I', ascending=False)
        
        for index, row in asteriscati_ordinati.iterrows():
            with st.expander(f"🔴 {row['Squadra_LFM']}: sostituisce {row['Nome']} (Quota {row['Qt.I']})"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric("Quota da rispettare", f"<= {row['Qt.I']}")
                    st.write(f"**Ruolo:** {row['R']}")
                    st.write(f"**Crediti:** {row['Crediti']}")
                
                with col2:
                    st.write("**Opzioni disponibili (Svincolati):**")
                    # Filtro regolamento: Stesso ruolo e quota pari o inferiore
                    possibili = svincolati[(svincolati['R'] == row['R']) & (svincolati['Qt.I'] <= row['Qt.I'])]
                    st.dataframe(possibili.sort_values(by='Qt.I', ascending=False)[['Nome', 'Qt.I', 'FVM']], height=200)

    st.divider()
    st.subheader("💰 Situazione Crediti")
    st.dataframe(df_leghe[df_leghe['Lega'] == campionato][['Squadra', 'Crediti']], use_container_width=True)
