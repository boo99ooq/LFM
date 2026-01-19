import streamlit as st
import pandas as pd
import math
import numpy as np
import os
import re

st.set_page_config(page_title="LFM Mercato - Fix Ufficiale", layout="wide", page_icon="⚖️")

# --- FUNZIONI UTILITY ---
def fix_league_names(df):
    if 'Lega' in df.columns:
        df['Lega'] = df['Lega'].replace(['Lega A', 'nan', 'Da Assegnare', None, 0], 'Serie A')
    return df

# --- CARICAMENTO DATI (LOGICA BLINDATA) ---
@st.cache_data
def load_data():
    try:
        # Caricamento file CSV
        df_r = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
        df_l = pd.read_csv('leghe.csv', encoding='latin1')
        df_q = pd.read_csv('quot.csv', encoding='latin1')
        
        # Pulizia ID iniziali
        df_r['Id'] = pd.to_numeric(df_r['Id'], errors='coerce').fillna(0).astype(int)
        df_q['Id'] = pd.to_numeric(df_q['Id'], errors='coerce').fillna(0).astype(int)
        
        # Caricamento file esclusi (TAB separated)
        try:
            df_e = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')
            id_col = 'Id' if 'Id' in df_e.columns else df_e.columns[0]
            ids_esclusi = set(pd.to_numeric(df_e[id_col], errors='coerce').dropna().astype(int))
        except:
            ids_esclusi = set()

        # Unione Rose + Leghe
        df_merged = pd.merge(df_r, df_l, left_on='Squadra_LFM', right_on='Squadra', how='left')
        df_merged = fix_league_names(df_merged)

        # Unione con Quotazioni (per Nome, R, Qt.I, FVM)
        df_final = pd.merge(df_merged, df_q[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
        
        # --- SOLUZIONE AL VALUENERROR (NA or inf) ---
        # Forza Qt.I e FVM a essere numerici e sostituisce i NaN con 0
        df_final['Qt.I'] = pd.to_numeric(df_final['Qt.I'], errors='coerce').fillna(0)
        df_final['FVM'] = pd.to_numeric(df_final['FVM'], errors='coerce').fillna(0)
        
        # Identificazione Asteriscati (*)
        df_final['In_Esclusi'] = df_final['Id'].isin(ids_esclusi)
        
        # --- LE TUE FORMULE ORIGINALI (lab3(3).py Righe 52-53) ---
        # Svincoli (*): FVM + (Qt.I / 2) -> Arrotondato per eccesso
        df_final['Rimborso_Star'] = np.ceil(df_final['FVM'] + (df_final['Qt.I'] / 2)).astype(int)
        
        # Tagli Volontari: (FVM + Qt.I) / 2 -> Arrotondato per eccesso
        df_final['Rimborso_Taglio'] = np.ceil((df_final['FVM'] + df_final['Qt.I']) / 2).astype(int)
        
        # Chiave univoca per i tagli
        df_final['Taglio_Key'] = df_final['Id'].astype(str) + "_" + df_final['Squadra_LFM'].astype(str)
        
        return df_final, df_l, df_q
    except Exception as e:
        st.error(f"Errore nel caricamento: {e}")
        return None, None, None

# --- INIZIALIZZAZIONE ---
if 'refunded_ids' not in st.session_state: st.session_state.refunded_ids = set()
if 'tagli_map' not in st.session_state: st.session_state.tagli_map = set()

data = load_data()

if data and data[0] is not None:
    df_base, df_leghe_orig, df_all_quot = data
    
    # Sincronizza stato rimborsi
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.title("🏃 Gestione Mercato LFM")
    t1, t2, t3 = st.tabs(["✈️ Svincoli (*)", "✂️ Tagli Volontari", "💰 Situazione Crediti"])

    # --- TAB 1: SVINCOLI ASTERISCATI ---
    with t1:
        st.subheader("Giocatori Esclusi dal Listone (*)")
        st.info("Formula originale: FVM + 50% Quotazione Iniziale")
        
        df_star = df_base[df_base['In_Esclusi']].copy()
        if df_star.empty:
            st.write("Nessun giocatore asteriscato trovato in rosa.")
        else:
            # Id incluso ma nascosto per evitare KeyError
            ed_star = st.data_editor(
                df_star[['Id', 'Rimborsato_Star', 'Nome', 'Squadra_LFM', 'FVM', 'Qt.I', 'Rimborso_Star']], 
                hide_index=True,
                column_config={"Id": st.column_config.Column(hidden=True)},
                key="ed_svincoli"
            )
            if st.button("Conferma Svincoli (*)"):
                for row in ed_star.to_dict('records'):
                    p_id = int(row['Id'])
                    if row['Rimborsato_Star']: st.session_state.refunded_ids.add(p_id)
                    else: st.session_state.refunded_ids.discard(p_id)
                st.rerun()

    # --- TAB 2: TAGLI VOLONTARI ---
    with t2:
        st.subheader("Tagli Volontari della Rosa")
        st.info("Formula originale: (FVM + Quotazione Iniziale) / 2")
        c = st.text_input("Cerca giocatore da tagliare:")
        if c:
            df_t_list = df_base[df_base['Nome'].str.contains(c, case=False, na=False)].copy()
            ed_taglio = st.data_editor(
                df_t_list[['Taglio_Key', 'Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'FVM', 'Qt.I', 'Rimborso_Taglio']], 
                hide_index=True,
                column_config={"Taglio_Key": st.column_config.Column(hidden=True)},
                key="ed_tagli"
            )
            if st.button("Conferma Tagli"):
                for row in ed_taglio.to_dict('records'):
                    t_k = row['Taglio_Key']
                    if row['Rimborsato_Taglio']: st.session_state.tagli_map.add(t_k)
                    else: st.session_state.tagli_map.discard(t_k)
                st.rerun()

    # --- TAB 3: BILANCIO CREDITI ---
    with t3:
        st.subheader("Bilancio Crediti Residui Aggiornato")
        bonus_star = df_base[df_base['Rimborsato_Star']].groupby('Squadra_LFM')['Rimborso_Star'].sum()
        bonus_taglio = df_base[df_base['Rimborsato_Taglio']].groupby('Squadra_LFM')['Rimborso_Taglio'].sum()
        
        stats = df_leghe_orig.copy().set_index('Squadra')
        stats['Base'] = stats['Crediti']
        stats['Recupero_Star'] = bonus_star.reindex(stats.index, fill_value=0)
        stats['Recupero_Tagli'] = bonus_taglio.reindex(stats.index, fill_value=0)
        stats['Tot_Disponibile'] = stats['Base'] + stats['Recupero_Star'] + stats['Recupero_Tagli']
        
        st.table(stats.reset_index()[['Squadra', 'Lega', 'Base', 'Recupero_Star', 'Recupero_Tagli', 'Tot_Disponibile']])

# --- BACKUP ---
st.sidebar.divider()
if st.sidebar.button("Reset Totale Sessione"):
    st.session_state.refunded_ids = set()
    st.session_state.tagli_map = set()
    st.rerun()
