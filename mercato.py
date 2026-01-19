import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="LFM - Gestione Mercato Strategica", layout="wide", page_icon="🏃")

# --- FUNZIONE CARICAMENTO DATI (BLINDATA) ---
@st.cache_data
def load_and_process_data():
    try:
        # Lettura file con parametri specifici (es. separatori)
        df_rosters = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
        df_leghe = pd.read_csv('leghe.csv', encoding='latin1')
        df_quot = pd.read_csv('quot.csv', encoding='latin1')
        df_esclusi = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')

        # Standardizzazione ID (rimuove errori di casting)
        for df in [df_rosters, df_quot, df_esclusi]:
            df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)

        # Pulizia colonne numeriche per i calcoli
        df_quot['Qt.I'] = pd.to_numeric(df_quot['Qt.I'], errors='coerce').fillna(0)
        df_quot['FVM'] = pd.to_numeric(df_quot['FVM'], errors='coerce').fillna(0)

        # Unione dati: Rose + Leghe
        df_base = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')

        # Unione con Quotazioni (per Nome, R, Qt.I, FVM)
        df_base = pd.merge(df_base, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')

        # GESTIONE NaN: Fondamentale per evitare IntCastingNaNError
        # Se un giocatore è in rosa ma non in quot.csv, impostiamo i valori a 0
        df_base['Qt.I'] = df_base['Qt.I'].fillna(0)
        df_base['FVM'] = df_base['FVM'].fillna(0)
        df_base['Nome'] = df_base['Nome'].fillna("Sconosciuto")

        # Identifica giocatori Asteriscati (*) incrociando con esclusi.csv
        ids_esclusi = set(df_esclusi['Id'])
        df_base['In_Esclusi'] = df_base['Id'].isin(ids_esclusi)

        # --- FORMULE DI RIMBORSO (Lab3(3).py) ---
        # Svincoli (*): FVM + (Qt.I / 2) -> Arrotondato per eccesso
        df_base['Rimborso_Star'] = np.ceil(df_base['FVM'] + (df_base['Qt.I'] / 2)).astype(int)
        
        # Tagli Volontari: (FVM + Qt.I) / 2 -> Arrotondato per eccesso
        df_base['Rimborso_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)

        # Chiave tecnica per i tagli (Id + Squadra)
        df_base['Taglio_Key'] = df_base['Id'].astype(str) + "_" + df_base['Squadra_LFM'].astype(str)

        return df_base, df_leghe
    except Exception as e:
        st.error(f"Errore fatale nel caricamento dati: {e}")
        return None, None

# --- INIZIALIZZAZIONE ---
if 'star_ids' not in st.session_state: st.session_state.star_ids = set()
if 'tagli_keys' not in st.session_state: st.session_state.tagli_keys = set()

data = load_and_process_data()

if data and data[0] is not None:
    df_base, df_leghe_orig = data
    
    # Flag rimborsi attivi
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.star_ids)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_keys)

    st.title("🏃 LFM - Gestione Mercato Ufficiale")
    st.divider()

    t1, t2, t3 = st.tabs(["✈️ Svincoli (*)", "✂️ Tagli Volontari", "💰 Bilancio"])

    # --- TAB 1: SVINCOLI (*) ---
    with t1:
        st.subheader("Giocatori Esclusi dal Listone (*)")
        st.info("Regola: Recupero 100% FVM + 50% Quotazione Iniziale")
        
        df_star_list = df_base[df_base['In_Esclusi']].copy()
        
        if df_star_list.empty:
            st.info("Nessun giocatore della tua rosa risulta nel file degli esclusi.")
        else:
            ed_star = st.data_editor(
                df_star_list[['Id', 'Rimborsato_Star', 'Nome', 'Squadra_LFM', 'FVM', 'Qt.I', 'Rimborso_Star']],
                hide_index=True,
                column_config={"Id": None}, # Nasconde l'ID ma lo mantiene nei dati
                key="ed_star"
            )
            
            if st.button("Conferma Svincoli (*)"):
                for r in ed_star.to_dict('records'):
                    p_id = int(r['Id'])
                    if r['Rimborsato_Star']: st.session_state.star_ids.add(p_id)
                    else: st.session_state.star_ids.discard(p_id)
                st.rerun()

    # --- TAB 2: TAGLI VOLONTARI ---
    with t2:
        st.subheader("Tagli Classici della Rosa")
        st.info("Regola: Recupero 50% FVM + 50% Quotazione Iniziale")
        
        c2 = st.text_input("Cerca giocatore da tagliare:")
        if c2:
            df_t_search = df_base[df_base['Nome'].str.contains(c2, case=False, na=False)].copy()
            ed_taglio = st.data_editor(
                df_t_search[['Taglio_Key', 'Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'FVM', 'Qt.I', 'Rimborso_Taglio']],
                hide_index=True,
                column_config={"Taglio_Key": None},
                key="ed_taglio"
            )
            
            if st.button("Conferma Tagli"):
                for r in ed_taglio.to_dict('records'):
                    t_k = r['Taglio_Key']
                    if r['Rimborsato_Taglio']: st.session_state.tagli_keys.add(t_k)
                    else: st.session_state.tagli_keys.discard(t_k)
                st.rerun()

    # --- TAB 3: BILANCIO ---
    with t3:
        st.subheader("Situazione Crediti Aggiornata")
        
        # Somma rimborsi
        bonus_star = df_base[df_base['Rimborsato_Star']].groupby('Squadra_LFM')['Rimborso_Star'].sum()
        bonus_taglio = df_base[df_base['Rimborsato_Taglio']].groupby('Squadra_LFM')['Rimborso_Taglio'].sum()
        
        res = df_leghe_orig.copy().set_index('Squadra')
        res['Recupero_Star'] = bonus_star.reindex(res.index, fill_value=0)
        res['Recupero_Tagli'] = bonus_taglio.reindex(res.index, fill_value=0)
        res['Crediti_Totali'] = res['Crediti'] + res['Recupero_Star'] + res['Recupero_Tagli']
        
        st.table(res.reset_index()[['Squadra', 'Lega', 'Crediti', 'Recupero_Star', 'Recupero_Tagli', 'Crediti_Totali']])

# --- BARRA LATERALE ---
st.sidebar.divider()
if st.sidebar.button("🗑️ Reset Sessione"):
    st.session_state.star_ids = set()
    st.session_state.tagli_keys = set()
    st.rerun()
