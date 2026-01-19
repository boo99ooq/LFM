import streamlit as st
import pandas as pd
import math
import os

st.set_page_config(page_title="LFM Mercato Ufficiale", layout="wide", page_icon="⚖️")

# --- CARICAMENTO DATI ---
def load_data():
    # Caricamento file (separatori corretti)
    df_r = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
    df_l = pd.read_csv('leghe.csv', encoding='latin1')
    df_q = pd.read_csv('quot.csv', encoding='latin1')
    # esclusi.csv è tab-separated
    df_e = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')
    
    # Pulizia ID
    for d in [df_r, df_q, df_e]:
        d['Id'] = pd.to_numeric(d['Id'], errors='coerce').fillna(0).astype(int)
    
    # Merge Rose + Quotazioni per avere i valori attuali (Nome, Ruolo, Qt.I, FVM)
    df_owned = pd.merge(df_r, df_q[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
    
    # Identificazione automatica Asteriscati (*)
    ids_esclusi = set(df_e['Id'])
    df_owned['In_Esclusi'] = df_owned['Id'].isin(ids_esclusi)
    
    # --- LE TUE FORMULE ORIGINALI (Righe 52-53 del tuo file) ---
    df_owned['Rimborso_Star'] = df_owned['FVM'] + (df_owned['Qt.I'] / 2)
    df_owned['Rimborso_Taglio'] = (df_owned['FVM'] + df_owned['Qt.I']) / 2
    
    # Chiave tecnica per i tagli
    df_owned['Taglio_Key'] = df_owned['Id'].astype(str) + "_" + df_owned['Squadra_LFM'].astype(str)
    
    return df_owned, df_l

# --- STATO DELLA SESSIONE ---
if 'refunded_ids' not in st.session_state: st.session_state.refunded_ids = set()
if 'tagli_map' not in st.session_state: st.session_state.tagli_map = set()

df_base, df_leghe_orig = load_data()

# Applicazione flag rimborsi
df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

st.title("🏃 Gestione Mercato LFM")

t1, t2, t3 = st.tabs(["✈️ Svincoli (*)", "✂️ Tagli Volontari", "💰 Situazione Crediti"])

with t1:
    st.subheader("Giocatori non più in lista (Asteriscati)")
    st.info("Formula: FVM Totale + 50% Quotazione Iniziale")
    
    # Filtriamo solo chi è effettivamente nel file esclusi.csv
    df_asteriscabili = df_base[df_base['In_Esclusi']].copy()
    
    if df_asteriscabili.empty:
        st.write("Nessun giocatore della tua rosa risulta tra gli esclusi.")
    else:
        # CORREZIONE KEYERROR: Id incluso e nascosto
        ed_star = st.data_editor(
            df_asteriscabili[['Id', 'Rimborsato_Star', 'Nome', 'Squadra_LFM', 'FVM', 'Qt.I', 'Rimborso_Star']],
            hide_index=True,
            column_config={
                "Id": st.column_config.Column(hidden=True),
                "Rimborsato_Star": "Svincola (*)",
                "Rimborso_Star": st.column_config.NumberColumn("Rimborso Spettante", format="%.1f")
            },
            key="ed_star"
        )
        
        if st.button("Conferma Svincoli (*)"):
            # Metodo to_dict per stabilità totale
            for row in ed_star.to_dict('records'):
                if row['Rimborsato_Star']: st.session_state.refunded_ids.add(int(row['Id']))
                else: st.session_state.refunded_ids.discard(int(row['Id']))
            st.rerun()

with t2:
    st.subheader("Tagli Volontari della Rosa")
    st.info("Formula: 50% FVM + 50% Quotazione Iniziale")
    
    c2 = st.text_input("Cerca giocatore da tagliare:")
    if c2:
        df_t = df_base[df_base['Nome'].str.contains(c2, case=False, na=False)].copy()
        # CORREZIONE KEYERROR: Taglio_Key incluso e nascosto
        ed_taglio = st.data_editor(
            df_t[['Taglio_Key', 'Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'FVM', 'Qt.I', 'Rimborso_Taglio']],
            hide_index=True,
            column_config={
                "Taglio_Key": st.column_config.Column(hidden=True),
                "Rimborsato_Taglio": "Taglia",
                "Rimborso_Taglio": st.column_config.NumberColumn("Rimborso Spettante", format="%.1f")
            },
            key="ed_taglio"
        )
        
        if st.button("Conferma Tagli"):
            for row in ed_taglio.to_dict('records'):
                if row['Rimborsato_Taglio']: st.session_state.tagli_map.add(row['Taglio_Key'])
                else: st.session_state.tagli_map.discard(row['Taglio_Key'])
            st.rerun()

with t3:
    st.subheader("Calcolo Crediti Aggiornato")
    
    # Calcolo bonus rimborsi (Logica originale)
    bonus_star = df_base[df_base['Rimborsato_Star']].groupby('Squadra_LFM')['Rimborso_Star'].sum()
    bonus_taglio = df_base[df_base['Rimborsato_Taglio']].groupby('Squadra_LFM')['Rimborso_Taglio'].sum()
    
    res = df_leghe_orig.copy().set_index('Squadra')
    res['Crediti_Base'] = res['Crediti']
    res['Tot_Rimborso_Star'] = bonus_star.reindex(res.index, fill_value=0)
    res['Tot_Rimborso_Taglio'] = bonus_taglio.reindex(res.index, fill_value=0)
    res['Crediti_Finali'] = res['Crediti_Base'] + res['Tot_Rimborso_Star'] + res['Tot_Rimborso_Taglio']
    
    st.table(res[['Lega', 'Crediti_Base', 'Tot_Rimborso_Star', 'Tot_Rimborso_Taglio', 'Crediti_Finali']])

# Sidebar per Reset e Backup
st.sidebar.download_button("Scarica Log Svincoli", df_base[df_base['Rimborsato_Star'] | df_base['Rimborsato_Taglio']].to_csv(index=False), "mercato_log.csv")
if st.sidebar.button("Reset Sessione"):
    st.session_state.refunded_ids = set()
    st.session_state.tagli_map = set()
    st.rerun()
