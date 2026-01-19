import streamlit as st
import pandas as pd

st.set_page_config(page_title="Draft LFM - Sessioni per Ruolo", layout="wide")

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
        esclusi = read_csv_safe('esclusi.csv', delimiter='\t')
        
        if len(esclusi.columns) >= 5:
            esclusi.columns = ['Id', 'R', 'Nome', 'Qt.I', 'FVM']
        
        for df in [rosters, quot, esclusi]:
            df['Id'] = pd.to_numeric(df['Id'], errors='coerce')
            if 'FVM' in df.columns:
                df['FVM'] = pd.to_numeric(df['FVM'], errors='coerce').fillna(0)
            df.dropna(subset=['Id'], inplace=True)
            df['Id'] = df['Id'].astype(int)
            
        return rosters, leghe, quot, esclusi
    except Exception as e:
        st.error(f"Errore nel caricamento: {e}")
        return None, None, None, None

df_rosters, df_leghe, df_quot, df_esclusi = load_data()

if df_rosters is not None:
    st.sidebar.header("Navigazione")
    campionato = st.sidebar.selectbox("Seleziona Campionato", ['Serie A', 'Premier League', 'Liga BBVA', 'Bundesliga'])
    
    df_full = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra')
    df_lega = df_full[df_full['Lega'] == campionato]
    
    st.title(f"🏆 Draft Temporaneo: {campionato}")
    st.subheader("Suddivisione Sessioni per Ruolo")

    # 1. Identificazione Asteriscati
    ids_esclusi = set(df_esclusi['Id'])
    asteriscati_base = df_lega[df_lega['Id'].isin(ids_esclusi)]
    asteriscati = pd.merge(asteriscati_base, df_esclusi[['Id', 'Nome', 'R', 'FVM']], on='Id', how='left')

    # 2. Svincolati Reali (Escludendo chi è già in rosa o nel file esclusi)
    ids_occupati_lega = set(df_lega['Id'])
    svincolati = df_quot[(~df_quot['Id'].isin(ids_occupati_lega)) & (~df_quot['Id'].isin(ids_esclusi))]

    if asteriscati.empty:
        st.success(f"✅ Nessuna sostituzione necessaria per {campionato}.")
    else:
        # 3. Definizione dei Ruoli in ordine di Draft
        ruoli_nomi = {'P': 'Portieri', 'D': 'Difensori', 'C': 'Centrocampisti', 'A': 'Attaccanti'}
        ordine_ruoli = ['P', 'D', 'C', 'A']

        # Creiamo dei Tab per navigare tra i ruoli
        tabs = st.tabs([ruoli_nomi[r] for r in ordine_ruoli])

        for i, r_code in enumerate(ordine_ruoli):
            with tabs[i]:
                # Filtriamo gli asteriscati per questo ruolo
                asteriscati_ruolo = asteriscati[asteriscati['R'] == r_code].sort_values(by='FVM', ascending=False)
                
                if asteriscati_ruolo.empty:
                    st.info(f"Nessun {ruoli_nomi[r_code][:-1]} da sostituire.")
                else:
                    st.markdown(f"### 📋 Ordine di chiamata {ruoli_nomi[r_code]}")
                    
                    for index, row in asteriscati_ruolo.iterrows():
                        with st.expander(f"⭐ {row['Squadra_LFM']} -> Sostituisce {row['Nome']} (FVM {row['FVM']})"):
                            col_info, col_list = st.columns([1, 2])
                            
                            with col_info:
                                st.metric("FVM Massimo", row['FVM'])
                                st.write(f"**Crediti:** {row['Crediti']}")
                            
                            with col_list:
                                st.write(f"**Svincolati {ruoli_nomi[r_code]} (FVM <= {row['FVM']}):**")
                                # Filtro svincolati: stesso ruolo e FVM <=
                                options = svincolati[(svincolati['R'] == r_code) & (svincolati['FVM'] <= row['FVM'])]
                                st.dataframe(options.sort_values(by='FVM', ascending=False)[['Nome', 'FVM', 'Qt.I']].head(12))

    st.divider()
    st.subheader("💰 Bilancio Crediti")
    st.dataframe(df_leghe[df_leghe['Lega'] == campionato][['Squadra', 'Crediti']], use_container_width=True)
