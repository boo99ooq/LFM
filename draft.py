import streamlit as st
import pandas as pd

st.set_page_config(page_title="Draft LFM Agosto (FVM Edition)", layout="wide")

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
        
        # Assegniamo nomi colonne agli esclusi
        if len(esclusi.columns) >= 5:
            esclusi.columns = ['Id', 'R', 'Nome', 'Qt.I', 'FVM']
        
        # Pulizia e Conversione Numerica (Fondamentale per FVM e Id)
        for df in [rosters, quot, esclusi]:
            df['Id'] = pd.to_numeric(df['Id'], errors='coerce')
            if 'FVM' in df.columns:
                df['FVM'] = pd.to_numeric(df['FVM'], errors='coerce').fillna(0)
            if 'Qt.I' in df.columns:
                df['Qt.I'] = pd.to_numeric(df['Qt.I'], errors='coerce').fillna(0)
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
    
    # Unione Rose e Leghe
    df_full = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra')
    df_lega = df_full[df_full['Lega'] == campionato]
    
    st.title(f"🏆 Draft Temporaneo: {campionato}")
    st.info("💡 L'ordine di scelta e i sostituti sono basati sul valore **FVM**.")

    # 1. IDENTIFICAZIONE ASTERISCATI
    ids_esclusi = set(df_esclusi['Id'])
    asteriscati_base = df_lega[df_lega['Id'].isin(ids_esclusi)]
    
    # Recuperiamo i dati (Nome, Ruolo, FVM) dal file esclusi
    asteriscati = pd.merge(asteriscati_base, df_esclusi[['Id', 'Nome', 'R', 'FVM', 'Qt.I']], on='Id', how='left')

    # 2. SVINCOLATI REALI (Non in rosa AND Non esclusi)
    ids_occupati_lega = set(df_lega['Id'])
    svincolati = df_quot[
        (~df_quot['Id'].isin(ids_occupati_lega)) & 
        (~df_quot['Id'].isin(ids_esclusi))
    ]

    if asteriscati.empty:
        st.success(f"✅ Nessun giocatore da sostituire in {campionato}.")
    else:
        st.subheader("📋 Graduatoria Draft (Priorità per FVM)")
        
        # NUOVA LOGICA: Ordiniamo per FVM decrescente
        asteriscati_ordinati = asteriscati.sort_values(by='FVM', ascending=False)
        
        for index, row in asteriscati_ordinati.iterrows():
            with st.expander(f"🔴 {row['Squadra_LFM']}: {row['Nome']} (FVM {row['FVM']})"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric("FVM da rispettare", f"<= {row['FVM']}")
                    st.write(f"**Ruolo:** {row['R']}")
                    st.write(f"**Ex-Quota:** {row['Qt.I']}")
                
                with col2:
                    st.write("**Sostituti Suggeriti (Stesso Ruolo & FVM <=):**")
                    # NUOVA LOGICA: Filtro basato su FVM
                    filtro_sost = (svincolati['R'] == row['R']) & (svincolati['FVM'] <= row['FVM'])
                    possibili = svincolati[filtro_sost].sort_values(by='FVM', ascending=False)
                    
                    if possibili.empty:
                        st.warning("Nessun sostituto con FVM compatibile.")
                    else:
                        st.dataframe(possibili[['Nome', 'FVM', 'Qt.I']].head(15), height=250)

    st.divider()
    st.subheader("💰 Situazione Crediti Residui")
    st.dataframe(df_leghe[df_leghe['Lega'] == campionato][['Squadra', 'Crediti']], use_container_width=True)
