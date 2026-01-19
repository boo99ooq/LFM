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
        
        # Carichiamo il file degli esclusi (separatore TAB)
        esclusi = read_csv_safe('esclusi.csv', delimiter='\t')
        # Assegniamo nomi colonne se mancano
        if len(esclusi.columns) >= 5:
            esclusi.columns = ['Id', 'R', 'Nome', 'Qt.I', 'FVM']
        
        # Pulizia ID
        for df in [rosters, quot, esclusi]:
            df['Id'] = pd.to_numeric(df['Id'], errors='coerce')
            df.dropna(subset=['Id'], inplace=True)
            df['Id'] = df['Id'].astype(int)
            
        return rosters, leghe, quot, esclusi
    except Exception as e:
        st.error(f"Errore nel caricamento: {e}")
        return None, None, None, None

df_rosters, df_leghe, df_quot, df_esclusi = load_data()

if df_rosters is not None:
    st.sidebar.header("Filtri Draft")
    campionato = st.sidebar.selectbox("Seleziona Campionato", ['Serie A', 'Premier League', 'Liga BBVA', 'Bundesliga'])
    
    df_full = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra')
    df_lega = df_full[df_full['Lega'] == campionato]
    
    st.title(f"🏆 Draft Temporaneo: {campionato}")

    # 1. IDENTIFICAZIONE ASTERISCATI (Chi è nelle rose AND nel file esclusi)
    ids_esclusi = set(df_esclusi['Id'])
    asteriscati_base = df_lega[df_lega['Id'].isin(ids_esclusi)]
    asteriscati = pd.merge(asteriscati_base, df_esclusi[['Id', 'Nome', 'R', 'Qt.I']], on='Id', how='left')

    # 2. SVINCOLATI REALI (In quot.csv AND NON nelle rose AND NON negli esclusi)
    ids_occupati_lega = set(df_lega['Id'])
    
    # FILTRO CRUCIALE: Escludiamo chi non è più listato dalle proposte
    svincolati = df_quot[
        (~df_quot['Id'].isin(ids_occupati_lega)) & 
        (~df_quot['Id'].isin(ids_esclusi))
    ]

    if asteriscati.empty:
        st.info(f"✅ Nessun giocatore di {campionato} da sostituire.")
    else:
        st.subheader("📋 Ordine di Scelta (Priorità per Quotazione)")
        asteriscati_ordinati = asteriscati.sort_values(by='Qt.I', ascending=False)
        
        for index, row in asteriscati_ordinati.iterrows():
            with st.expander(f"🔴 {row['Squadra_LFM']}: sostituisce {row['Nome']} (Quota {row['Qt.I']})"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric("Budget Quota", f"<= {row['Qt.I']}")
                    st.write(f"**Ruolo:** {row['R']}")
                
                with col2:
                    st.write("**Opzioni valide (Solo giocatori listati):**")
                    # Filtro: stesso ruolo e quota <=
                    possibili = svincolati[(svincolati['R'] == row['R']) & (svincolati['Qt.I'] <= row['Qt.I'])]
                    
                    if possibili.empty:
                        st.warning("Nessun sostituto valido trovato con questa quota.")
                    else:
                        st.dataframe(possibili.sort_values(by='Qt.I', ascending=False)[['Nome', 'Qt.I', 'FVM']], height=200)

    st.divider()
    st.subheader("💰 Situazione Crediti")
    st.dataframe(df_leghe[df_leghe['Lega'] == campionato][['Squadra', 'Crediti']], use_container_width=True)
