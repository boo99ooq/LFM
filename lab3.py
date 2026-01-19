import streamlit as st
import pandas as pd
import math
import numpy as np
import os

st.set_page_config(page_title="LFM - Gestione Mercato", layout="wide", page_icon="🏃")

# --- FUNZIONE CARICAMENTO DATI (LOGICA ORIGINALE RIGOROSA) ---
@st.cache_data
def load_data():
    try:
        # Caricamento file come nel tuo script originale
        df_r = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
        df_l = pd.read_csv('leghe.csv', encoding='latin1')
        df_q = pd.read_csv('quot.csv', encoding='latin1')
        # esclusi.csv usa il separatore TAB (\t)
        df_e = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')
        
        # 1. PULIZIA PREVENTIVA (Risolve NameError e TypeError)
        # Assicuriamoci che gli ID siano numeri interi ovunque
        for df in [df_r, df_q, df_e]:
            df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
        
        # Pulizia Quotazioni (Qt.I e FVM devono essere numeri per il calcolo rimborsi)
        df_q['Qt.I'] = pd.to_numeric(df_q['Qt.I'], errors='coerce').fillna(0)
        df_q['FVM'] = pd.to_numeric(df_q['FVM'], errors='coerce').fillna(0)

        # 2. CREAZIONE DATABASE ROSE (Merge Rose + Leghe + Quotazioni)
        df_merged = pd.merge(df_r, df_l, left_on='Squadra_LFM', right_on='Squadra', how='left')
        df_final = pd.merge(df_merged, df_q[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
        
        # Identificazione Asteriscati (*) - Presenti nel file esclusi
        ids_esclusi = set(df_e['Id'])
        df_final['In_Esclusi'] = df_final['Id'].isin(ids_esclusi)
        
        # 3. LE TUE FORMULE ORIGINALI (Righe 52-53 del tuo file lab3(3).py)
        # Svincoli (*): FVM totale + metà Quotazione Iniziale
        df_final['Rimborso_Star'] = np.ceil(df_final['FVM'] + (df_final['Qt.I'] / 2)).astype(int)
        
        # Tagli: (FVM + Quotazione Iniziale) / 2
        df_final['Rimborso_Taglio'] = np.ceil((df_final['FVM'] + df_final['Qt.I']) / 2).astype(int)
        
        # Chiave tecnica per i tagli
        df_final['Taglio_Key'] = df_final['Id'].astype(str) + "_" + df_final['Squadra_LFM'].astype(str)
        
        return df_final, df_l
    except Exception as e:
        st.error(f"Errore nel caricamento dei dati: {e}")
        return None, None

# --- INIZIALIZZAZIONE ---
if 'refunded_star_ids' not in st.session_state:
    st.session_state.refunded_star_ids = set()
if 'tagli_keys' not in st.session_state:
    st.session_state.tagli_keys = set()

data = load_data()

if data[0] is not None:
    df_base, df_leghe_orig = data
    
    # Applichiamo lo stato della sessione ai dati
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_star_ids)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_keys)

    st.title("🏃 Gestione Mercato LFM")
    tab1, tab2, tab3 = st.tabs(["✈️ Svincoli (*)", "✂️ Tagli Volontari", "💰 Situazione Crediti"])

    # --- TAB 1: SVINCOLI (*) ---
    with tab1:
        st.subheader("Giocatori Esclusi dal Listone (*)")
        st.info("Formula originale: FVM + (Qt.I / 2)")
        df_star = df_base[df_base['In_Esclusi']].copy()
        
        if df_star.empty:
            st.write("Nessun giocatore della tua rosa è tra gli esclusi.")
        else:
            # Id incluso e nascosto per stabilità totale (evita KeyError)
            ed_star = st.data_editor(
                df_star[['Id', 'Rimborsato_Star', 'Nome', 'Squadra_LFM', 'FVM', 'Qt.I', 'Rimborso_Star']],
                hide_index=True,
                column_config={"Id": st.column_config.Column(hidden=True)},
                key="ed_star"
            )
            
            if st.button("Salva Svincoli (*)"):
                for row in ed_star.to_dict('records'):
                    p_id = int(row['Id'])
                    if row['Rimborsato_Star']: st.session_state.refunded_star_ids.add(p_id)
                    else: st.session_state.refunded_star_ids.discard(p_id)
                st.rerun()

    # --- TAB 2: TAGLI VOLONTARI ---
    with tab2:
        st.subheader("Tagli Volontari")
        st.info("Formula originale: (FVM + Qt.I) / 2")
        cerca = st.text_input("Cerca giocatore da tagliare:")
        if cerca:
            df_t = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].copy()
            ed_taglio = st.data_editor(
                df_t[['Taglio_Key', 'Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'FVM', 'Qt.I', 'Rimborso_Taglio']],
                hide_index=True,
                column_config={"Taglio_Key": st.column_config.Column(hidden=True)},
                key="ed_taglio"
            )
            if st.button("Salva Tagli"):
                for row in ed_taglio.to_dict('records'):
                    t_k = row['Taglio_Key']
                    if row['Rimborsato_Taglio']: st.session_state.tagli_keys.add(t_k)
                    else: st.session_state.tagli_map.discard(t_k)
                st.rerun()

    # --- TAB 3: BILANCIO ---
    with tab3:
        st.subheader("Bilancio Crediti Residui")
        # Calcolo rimborsi (Logica originale righe 120-125)
        bonus_star = df_base[df_base['Rimborsato_Star']].groupby('Squadra_LFM')['Rimborso_Star'].sum()
        bonus_taglio = df_base[df_base['Rimborsato_Taglio']].groupby('Squadra_LFM')['Rimborso_Taglio'].sum()
        
        res = df_leghe_orig.copy().set_index('Squadra')
        res['Bonus_Star'] = bonus_star.reindex(res.index, fill_value=0)
        res['Bonus_Taglio'] = bonus_taglio.reindex(res.index, fill_value=0)
        res['Crediti_Aggiornati'] = res['Crediti'] + res['Bonus_Star'] + res['Bonus_Taglio']
        
        st.table(res.reset_index()[['Squadra', 'Lega', 'Crediti', 'Bonus_Star', 'Bonus_Taglio', 'Crediti_Aggiornati']])
