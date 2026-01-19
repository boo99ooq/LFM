import streamlit as st
import pandas as pd
import numpy as np
import math
from github import Github
import io

st.set_page_config(page_title="LFM Mercato Sync GitHub", layout="wide", page_icon="⚖️")

# --- CONNESSIONE GITHUB (Secrets) ---
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except Exception as e:
    st.error("Errore Configurazione GitHub Secrets. Verifica GITHUB_TOKEN e REPO_NAME.")

# --- FUNZIONE SALVATAGGIO SU GITHUB ---
def save_to_github(file_path, df, message):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    content = csv_buffer.getvalue()
    try:
        contents = repo.get_contents(file_path)
        repo.update_file(contents.path, message, content, contents.sha)
    except:
        repo.create_file(file_path, message, content)

# --- CARICAMENTO E INCROCIO DATI ---
@st.cache_data
def load_data():
    # Caricamento file base
    df_rosters = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
    df_leghe = pd.read_csv('leghe.csv', encoding='latin1')
    df_quot = pd.read_csv('quot.csv', encoding='latin1')
    # Caricamento esclusi (TAB separated)
    df_esclusi = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')
    
    # Pulizia ID
    for df in [df_rosters, df_quot, df_esclusi]:
        df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
    
    # Merge Rose + Leghe + Quotazioni
    df_base = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_base, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
    
    # Pulizia valori numerici
    df_base[['Qt.I', 'FVM']] = df_base[['Qt.I', 'FVM']].fillna(0)
    df_base['Nome'] = df_base['Nome'].fillna("Sconosciuto").astype(str)
    
    # FORMULE RIMBORSO (Lab3.py)
    df_base['Rimb_Star'] = np.ceil(df_base['FVM'] + (df_base['Qt.I'] / 2)).astype(int)
    df_base['Rimb_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    # INCROCIO: Trova i nomi degli esclusi che sono effettivamente posseduti da qualcuno
    ids_esclusi = set(df_esclusi['Id'])
    df_base['Da_Svincolare_Star'] = df_base['Id'].isin(ids_esclusi)
    
    return df_base, df_leghe, df_rosters

df_base, df_leghe_orig, df_rosters_orig = load_data()

# --- INTERFACCIA ---
st.title("🏃 LFM Mercato - Automazione Gennaio")

tab1, tab2 = st.tabs(["✈️ Svincoli (*) Automatici", "✂️ Tagli Volontari"])

with tab1:
    st.subheader("✈️ Svincoli Globali (*) da file Esclusi")
    st.caption("Questi giocatori sono stati rimossi dal listone e sono presenti nelle tue rose.")
    
    # Filtriamo solo i giocatori in rosa che sono nel file esclusi
    df_star_presenti = df_base[df_base['Da_Svincolare_Star']].copy()
    
    if df_star_presenti.empty:
        st.success("Ottimo! Nessun giocatore nelle tue rose risulta tra gli esclusi.")
    else:
        nomi_esclusi_ordinati = sorted(df_star_presenti['Nome'].unique())
        scelta_star = st.selectbox("Seleziona Giocatore Escluso da rimborsare a tutti:", [""] + nomi_esclusi_ordinati)
        
        if scelta_star:
            proprietari = df_star_presenti[df_star_presenti['Nome'] == scelta_star]
            st.warning(f"Il giocatore **{scelta_star}** verrà rimosso da {len(proprietari)} squadre.")
            st.table(proprietari[['Squadra_LFM', 'Lega', 'Rimb_Star']])
            
            if st.button(f"ESEGUI SVINCOLO GLOBALE: {scelta_star}"):
                # 1. Aggiorna Crediti
                for _, row in proprietari.iterrows():
                    df_leghe_orig.loc[df_leghe_orig['Squadra'] == row['Squadra_LFM'], 'Crediti'] += row['Rimb_Star']
                
                # 2. Rimuovi da Roster (Globale per quell'Id)
                id_giocatore = proprietari.iloc[0]['Id']
                df_rosters_upd = df_rosters_orig[df_rosters_orig['Id'] != id_giocatore]
                
                # 3. Log Deposito
                log_new = proprietari[['Nome', 'Squadra_LFM', 'Lega', 'Rimb_Star']].copy()
                log_new.columns = ['Giocatore', 'Squadra', 'Lega', 'Rimborso']
                log_new['Data'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                
                # SALVATAGGIO
                save_to_github('leghe.csv', df_leghe_orig, f"Svincolo Star: {scelta_star}")
                save_to_github('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimozione Rose: {scelta_star}")
                save_to_github('svincolati_gennaio.csv', log_new, f"Log Svincolo: {scelta_star}")
                
                st.success(f"{scelta_star} svincolato correttamente su GitHub!")
                st.cache_data.clear()
                st.rerun()

with tab2:
    st.subheader("✂️ Taglio Volontario (Singola Squadra)")
    sq_sel = st.selectbox("Seleziona Squadra:", sorted(df_base['Squadra_LFM'].unique()))
    giocatori_sq = df_base[df_base['Squadra_LFM'] == sq_sel]
    gioc_sel = st.selectbox("Giocatore da tagliare:", giocatori_sq['Nome'].tolist())
    
    if st.button("CONFERMA TAGLIO SINGOLO"):
        info = giocatori_sq[giocatori_sq['Nome'] == gioc_sel].iloc[0]
        
        # Aggiorna Crediti
        df_leghe_orig.loc[df_leghe_orig['Squadra'] == sq_sel, 'Crediti'] += info['Rimb_Taglio']
        
        # Rimuovi da Roster (Solo quella squadra)
        df_rosters_upd = df_rosters_orig[~((df_rosters_orig['Squadra_LFM'] == sq_sel) & (df_rosters_orig['Id'] == info['Id']))]
        
        # Log Deposito
        log_taglio = pd.DataFrame([{'Giocatore': gioc_sel, 'Squadra': sq_sel, 'Rimborso': info['Rimb_Taglio'], 'Data': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}])
        
        # SALVATAGGIO
        save_to_github('leghe.csv', df_leghe_orig, f"Taglio: {gioc_sel}")
        save_to_github('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimozione Rosa: {gioc_sel}")
        save_to_github('tagli_volontari.csv', log_taglio, f"Log Taglio: {gioc_sel}")
        
        st.success(f"Taglio di {gioc_sel} salvato su GitHub!")
        st.cache_data.clear()
        st.rerun()
