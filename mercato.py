import streamlit as st
import pandas as pd
import numpy as np
import math
from github import Github
import io

st.set_page_config(page_title="LFM Mercato Sync GitHub", layout="wide")

# --- CONNESSIONE GITHUB ---
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except Exception as e:
    st.error("Errore Configurazione GitHub Secrets. Verifica GITHUB_TOKEN e REPO_NAME.")

# --- FUNZIONE SALVATAGGIO ---
def save_to_github(file_path, df, message):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    content = csv_buffer.getvalue()
    try:
        contents = repo.get_contents(file_path)
        repo.update_file(contents.path, message, content, contents.sha)
    except:
        repo.create_file(file_path, message, content)

# --- CARICAMENTO E PULIZIA DATI ---
@st.cache_data
def load_data():
    df_rosters = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
    df_leghe = pd.read_csv('leghe.csv', encoding='latin1')
    df_quot = pd.read_csv('quot.csv', encoding='latin1')
    
    # Pulizia ID e Nomi (Risolve TypeError e IntCastingNaNError)
    for df in [df_rosters, df_quot]:
        df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
    
    df_quot['Nome'] = df_quot['Nome'].fillna("Sconosciuto").astype(str)
    df_quot['Qt.I'] = pd.to_numeric(df_quot['Qt.I'], errors='coerce').fillna(0)
    df_quot['FVM'] = pd.to_numeric(df_quot['FVM'], errors='coerce').fillna(0)

    # Merge Database
    df_base = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_base, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
    
    # Riempimento valori nulli post-merge
    df_base[['Qt.I', 'FVM']] = df_base[['Qt.I', 'FVM']].fillna(0)
    df_base['Nome'] = df_base['Nome'].fillna("Sconosciuto")
    
    # FORMULE ORIGINALI LAB3(3).PY (Righe 52-53)
    df_base['Rimb_Star'] = np.ceil(df_base['FVM'] + (df_base['Qt.I'] / 2)).astype(int)
    df_base['Rimb_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    return df_base, df_leghe

df_base, df_leghe_orig = load_data()

# --- INTERFACCIA ---
st.title("🏃 LFM Mercato Ufficiale")

tab1, tab2 = st.tabs(["✈️ Azioni Mercato", "💰 Bilancio e Log"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("✈️ Svincolo Globale (*)")
        st.caption("Rimborsa TUTTI i proprietari del giocatore selezionato.")
        
        # Pulizia lista nomi per selectbox
        nomi_ordinati = sorted([str(n) for n in df_base['Nome'].unique() if str(n) != "Sconosciuto"])
        scelta = st.selectbox("Seleziona Giocatore Asteriscato:", [""] + nomi_ordinati)
        
        if scelta:
            proprietari = df_base[df_base['Nome'] == scelta]
            st.warning(f"Svincolo per {len(proprietari)} squadre: rimborsi da {proprietari.iloc[0]['Rimb_Star']} cr.")
            
            if st.button(f"ESEGUI SVINCOLO GLOBALE: {scelta}"):
                # 1. Aggiorna Crediti
                for _, row in proprietari.iterrows():
                    df_leghe_orig.loc[df_leghe_orig['Squadra'] == row['Squadra_LFM'], 'Crediti'] += row['Rimb_Star']
                
                # 2. Rimuovi da Roster
                df_rosters_new = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
                df_rosters_new = df_rosters_new[df_rosters_new['Id'] != proprietari.iloc[0]['Id']]
                
                # 3. Log Svincolati Gennaio
                log_new = proprietari[['Nome', 'Squadra_LFM', 'Lega', 'Rimb_Star']].copy()
                log_new.columns = ['Giocatore', 'Squadra', 'Lega', 'Rimborso']
                log_new['Data'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                
                # Salvataggio sincronizzato su GitHub
                save_to_github('leghe.csv', df_leghe_orig, f"Update crediti svincolo {scelta}")
                save_to_github('fantamanager-2021-rosters.csv', df_rosters_new, f"Rimozione {scelta} dalle rose")
                save_to_github('svincolati_gennaio.csv', log_new, f"Log svincolo {scelta}")
                
                st.success("GitHub Aggiornato!")
                st.cache_data.clear()
                st.rerun()

    with col2:
        st.subheader("✂️ Taglio Volontario")
        st.caption("Rimborsa una singola squadra specifica.")
        
        sq_sel = st.selectbox("Seleziona Squadra:", sorted(df_base['Squadra_LFM'].unique()))
        giocatori_sq = df_base[df_base['Squadra_LFM'] == sq_sel]
        gioc_sel = st.selectbox("Giocatore da tagliare:", giocatori_sq['Nome'].tolist())
        
        if st.button("CONFERMA TAGLIO SINGOLO"):
            info = giocatori_sq[giocatori_sq['Nome'] == gioc_sel].iloc[0]
            
            # Aggiorna Crediti
            df_leghe_orig.loc[df_leghe_orig['Squadra'] == sq_sel, 'Crediti'] += info['Rimb_Taglio']
            
            # Rimuovi da Roster
            df_rosters_full = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
            df_rosters_new = df_rosters_full[~((df_rosters_full['Squadra_LFM'] == sq_sel) & (df_rosters_full['Id'] == info['Id']))]
            
            # Log Tagli
            log_taglio = pd.DataFrame([{'Giocatore': gioc_sel, 'Squadra': sq_sel, 'Rimborso': info['Rimb_Taglio'], 'Data': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}])
            
            save_to_github('leghe.csv', df_leghe_orig, f"Update crediti taglio {gioc_sel}")
            save_to_github('fantamanager-2021-rosters.csv', df_rosters_new, f"Rimozione {gioc_sel} da {sq_sel}")
            save_to_github('tagli_volontari.csv', log_taglio, f"Log taglio {gioc_sel}")
            
            st.success("Taglio salvato su GitHub!")
            st.cache_data.clear()
            st.rerun()

with tab2:
    st.subheader("💰 Crediti Attuali (da leghe.csv)")
    st.dataframe(df_leghe_orig[['Squadra', 'Lega', 'Crediti']].sort_values('Crediti', ascending=False), hide_index=True)
    
    st.divider()
    st.subheader("📜 Storico Operazioni Recenti")
    c1, c2 = st.columns(2)
    try:
        c1.write("Ultimi Svincoli (*):")
        c1.dataframe(pd.read_csv('svincolati_gennaio.csv').tail(10), hide_index=True)
        c2.write("Ultimi Tagli:")
        c2.dataframe(pd.read_csv('tagli_volontari.csv').tail(10), hide_index=True)
    except:
        st.info("Nessun log ancora disponibile su GitHub.")
