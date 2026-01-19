import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="LFM - Gestione Mercato", layout="wide")

# --- CARICAMENTO DATI ---
@st.cache_data
def load_data():
    # Caricamento file certi
    df_rosters = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
    df_leghe = pd.read_csv('leghe.csv', encoding='latin1')
    df_quot = pd.read_csv('quot.csv', encoding='latin1')
    # esclusi.csv è separato da TAB (\t)
    df_esclusi = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')

    # Pulizia ID e Numeri per evitare TypeError/ValueError
    for df in [df_rosters, df_quot, df_esclusi]:
        df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
    
    df_quot['Qt.I'] = pd.to_numeric(df_quot['Qt.I'], errors='coerce').fillna(0)
    df_quot['FVM'] = pd.to_numeric(df_quot['FVM'], errors='coerce').fillna(0)

    # 1. Creiamo il database delle rose attuali
    df_base = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_base, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')

    # 2. Identifichiamo chi è un Svincolo (*) (presente in esclusi.csv)
    ids_esclusi = set(df_esclusi['Id'])
    df_base['Is_Star_Candidate'] = df_base['Id'].isin(ids_esclusi)

    # 3. Applichiamo le TUE formule originali
    df_base['Rimborso_Star'] = np.ceil(df_base['FVM'] + (df_base['Qt.I'] / 2)).astype(int)
    df_base['Rimborso_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)

    # Chiave univoca per i tagli (Id + Squadra)
    df_base['Taglio_Key'] = df_base['Id'].astype(str) + "_" + df_base['Squadra_LFM'].astype(str)

    return df_base, df_leghe

# --- INIZIALIZZAZIONE SESSIONE ---
if 'star_ids' not in st.session_state: st.session_state.star_ids = set()
if 'tagli_keys' not in st.session_state: st.session_state.tagli_keys = set()

df_base, df_leghe_orig = load_data()

# Flag rimborsi attivi
df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.star_ids)
df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_keys)

st.title("🏃 LFM - Gestione Mercato Strategica")

t1, t2, t3 = st.tabs(["✈️ Svincoli (*)", "✂️ Tagli Volontari", "💰 Situazione Crediti"])

with t1:
    st.subheader("Giocatori Esclusi dal Listone (*)")
    st.info("Formula: FVM + 50% Quotazione Iniziale")
    
    df_star = df_base[df_base['Is_Star_Candidate']].copy()
    
    # Editor tabella con Id nascosto (column_order per stabilità)
    ed_star = st.data_editor(
        df_star,
        column_order=['Rimborsato_Star', 'Nome', 'Squadra_LFM', 'FVM', 'Qt.I', 'Rimborso_Star'],
        hide_index=True,
        key="ed_star"
    )
    
    if st.button("Conferma Svincoli (*)"):
        for row in ed_star.to_dict('records'):
            p_id = int(row['Id'])
            if row['Rimborsato_Star']: st.session_state.star_ids.add(p_id)
            else: st.session_state.star_ids.discard(p_id)
        st.rerun()

with t2:
    st.subheader("Tagli Volontari della Rosa")
    st.info("Formula: (FVM + Quotazione Iniziale) / 2")
    
    c = st.text_input("Cerca giocatore:")
    if c:
        df_t = df_base[df_base['Nome'].str.contains(c, case=False, na=False)].copy()
        ed_taglio = st.data_editor(
            df_t,
            column_order=['Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'FVM', 'Qt.I', 'Rimborso_Taglio'],
            hide_index=True,
            key="ed_taglio"
        )
        
        if st.button("Conferma Tagli"):
            for row in ed_taglio.to_dict('records'):
                t_k = row['Taglio_Key']
                if row['Rimborsato_Taglio']: st.session_state.tagli_keys.add(t_k)
                else: st.session_state.tagli_keys.discard(t_k)
            st.rerun()

with t3:
    st.subheader("Crediti Aggiornati per Squadra")
    
    bonus_star = df_base[df_base['Rimborsato_Star']].groupby('Squadra_LFM')['Rimborso_Star'].sum()
    bonus_taglio = df_base[df_base['Rimborsato_Taglio']].groupby('Squadra_LFM')['Rimborso_Taglio'].sum()
    
    res = df_leghe_orig.copy().set_index('Squadra')
    res['Recupero_Star'] = bonus_star.reindex(res.index, fill_value=0)
    res['Recupero_Tagli'] = bonus_taglio.reindex(res.index, fill_value=0)
    res['Crediti_Totali'] = res['Crediti'] + res['Recupero_Star'] + res['Recupero_Tagli']
    
    st.table(res.reset_index()[['Squadra', 'Lega', 'Crediti', 'Recupero_Star', 'Recupero_Tagli', 'Crediti_Totali']])

st.sidebar.button("Reset Sessione", on_click=lambda: (st.session_state.clear()))
