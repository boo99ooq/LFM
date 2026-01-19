import streamlit as st
import pandas as pd
import numpy as np
import math

st.set_page_config(page_title="LFM Mercato Globale", layout="wide")

# --- CARICAMENTO DATI ---
@st.cache_data
def load_data():
    df_rosters = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
    df_leghe = pd.read_csv('leghe.csv', encoding='latin1')
    df_quot = pd.read_csv('quot.csv', encoding='latin1')
    df_esclusi = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')

    for df in [df_rosters, df_quot, df_esclusi]:
        df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
    
    df_quot['Qt.I'] = pd.to_numeric(df_quot['Qt.I'], errors='coerce').fillna(0)
    df_quot['FVM'] = pd.to_numeric(df_quot['FVM'], errors='coerce').fillna(0)

    # Database Rose Completo
    df_base = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_base, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')

    # Calcolo rimborsi (TUE FORMULE ORIGINALI)
    df_base['Rimb_Star'] = np.ceil(df_base['FVM'] + (df_base['Qt.I'] / 2)).astype(int)
    df_base['Rimb_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    return df_base, df_leghe

# --- INIZIALIZZAZIONE SESSIONE ---
if 'storico' not in st.session_state:
    st.session_state.storico = pd.DataFrame(columns=['Giocatore', 'Squadra', 'Lega', 'Tipo', 'Rimborso'])
if 'bonus_extra' not in st.session_state:
    st.session_state.bonus_extra = {} # { (Squadra, Lega): valore }

df_base, df_leghe_orig = load_data()

st.title("🏃 LFM Mercato - Svincoli Globali & Tagli")

tab1, tab2 = st.tabs(["✈️ Gestione Mercato", "📜 Riepilogo Rimborsi"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Svincolo Globale (*)")
        st.caption("Usa questo per i giocatori usciti dal listone (es. Castellanos). Rimborsa TUTTI i proprietari.")
        
        # Lista nomi per ricerca rapida
        nomi_giocatori = sorted(df_base['Nome'].unique())
        scelta = st.selectbox("Cerca Giocatore da Svincolare:", [""] + nomi_giocatori)
        
        if scelta != "":
            proprietari = df_base[df_base['Nome'] == scelta]
            st.write(f"Trovate {len(proprietari)} squadre che possiedono questo giocatore.")
            st.dataframe(proprietari[['Squadra_LFM', 'Lega', 'Rimb_Star']], hide_index=True)
            
            if st.button(f"Svincola {scelta} per tutti"):
                for _, row in proprietari.iterrows():
                    chiave = (row['Squadra_LFM'], row['Lega'])
                    valore = row['Rimb_Star']
                    st.session_state.bonus_extra[chiave] = st.session_state.bonus_extra.get(chiave, 0) + valore
                    
                    # Aggiungi allo storico
                    nuovo_rec = pd.DataFrame([{'Giocatore': scelta, 'Squadra': row['Squadra_LFM'], 'Lega': row['Lega'], 'Tipo': 'STAR (*)', 'Rimborso': valore}])
                    st.session_state.storico = pd.concat([st.session_state.storico, nuovo_rec], ignore_index=True)
                st.success("Svincolo globale completato!")
                st.rerun()

    with col2:
        st.subheader("Taglio Volontario (Singolo)")
        st.caption("Usa questo per tagliare un giocatore da una singola squadra specifica.")
        
        sq_sel = st.selectbox("Seleziona Squadra:", sorted(df_base['Squadra_LFM'].unique()))
        rosa_sq = df_base[df_base['Squadra_LFM'] == sq_sel]
        gioc_sel = st.selectbox("Giocatore da tagliare:", rosa_sq['Nome'].tolist())
        
        if st.button("Conferma Taglio Singolo"):
            info = rosa_sq[rosa_sq['Nome'] == gioc_sel].iloc[0]
            chiave = (info['Squadra_LFM'], info['Lega'])
            valore = info['Rimb_Taglio']
            
            st.session_state.bonus_extra[chiave] = st.session_state.bonus_extra.get(chiave, 0) + valore
            
            nuovo_rec = pd.DataFrame([{'Giocatore': gioc_sel, 'Squadra': info['Squadra_LFM'], 'Lega': info['Lega'], 'Tipo': 'TAGLIO', 'Rimborso': valore}])
            st.session_state.storico = pd.concat([st.session_state.storico, nuovo_rec], ignore_index=True)
            st.success(f"Taglio effettuato: +{valore} crediti a {sq_sel}")
            st.rerun()

with tab2:
    st.subheader("Bilancio Crediti Aggiornato")
    
    # Creazione tabella crediti finale
    res = df_leghe_orig.copy()
    res['Bonus_Recuperato'] = res.apply(lambda x: st.session_state.bonus_extra.get((x['Squadra'], x['Lega']), 0), axis=1)
    res['Crediti_Totali'] = res['Crediti'] + res['Bonus_Recuperato']
    
    st.table(res[['Squadra', 'Lega', 'Crediti', 'Bonus_Recuperato', 'Crediti_Totali']])
    
    st.divider()
    st.subheader("Dettaglio Operazioni Effettuate")
    st.dataframe(st.session_state.storico, use_container_width=True, hide_index=True)
    
    if st.button("Reset Totale"):
        st.session_state.clear()
        st.rerun()
