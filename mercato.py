import streamlit as st
import pandas as pd
import numpy as np
import math
from github import Github
import io

# --- CONFIGURAZIONE GITHUB ---
# Questi valori vengono letti dai Secrets di Streamlit
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except:
    st.error("Configura i GITHUB_TOKEN e REPO_NAME nei Secrets di Streamlit!")

# --- FUNZIONI DI SALVATAGGIO SU GITHUB ---
def save_to_github(file_path, df, message):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    content = csv_buffer.getvalue()
    try:
        contents = repo.get_contents(file_path)
        repo.update_file(contents.path, message, content, contents.sha)
    except:
        repo.create_file(file_path, message, content)

# --- CARICAMENTO DATI ---
@st.cache_data
def load_data():
    df_rosters = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
    df_leghe = pd.read_csv('leghe.csv', encoding='latin1')
    df_quot = pd.read_csv('quot.csv', encoding='latin1')

    for df in [df_rosters, df_quot]:
        df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
    
    df_quot['Qt.I'] = pd.to_numeric(df_quot['Qt.I'], errors='coerce').fillna(0)
    df_quot['FVM'] = pd.to_numeric(df_quot['FVM'], errors='coerce').fillna(0)

    df_base = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_base, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
    
    # Riempimento NaN per evitare errori di calcolo
    df_base[['Qt.I', 'FVM']] = df_base[['Qt.I', 'FVM']].fillna(0)
    
    # Formule di Rimborso
    df_base['Rimb_Star'] = np.ceil(df_base['FVM'] + (df_base['Qt.I'] / 2)).astype(int)
    df_base['Rimb_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    return df_base, df_leghe

# --- LOGICA DI MERCATO ---
df_base, df_leghe_orig = load_data()

st.title("🏃 LFM Mercato Sync GitHub")

tab1, tab2 = st.tabs(["✈️ Azioni Mercato", "📜 Bilancio & Log"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("✈️ Svincolo Globale (*)")
        scelta = st.selectbox("Seleziona Giocatore Asteriscato:", [""] + sorted(df_base['Nome'].unique()))
        
        if scelta:
            proprietari = df_base[df_base['Nome'] == scelta]
            st.warning(f"Svincolo per {len(proprietari)} squadre.")
            
            if st.button(f"Esegui Svincolo Globale: {scelta}"):
                # 1. Aggiorna Crediti in leghe.csv
                for _, row in proprietari.iterrows():
                    df_leghe_orig.loc[df_leghe_orig['Squadra'] == row['Squadra_LFM'], 'Crediti'] += row['Rimb_Star']
                
                # 2. Rimuovi dalla rosa in rosters.csv
                df_rosters_new = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
                df_rosters_new = df_rosters_new[df_rosters_new['Id'] != proprietari.iloc[0]['Id']]
                
                # 3. Aggiorna Log Svincolati Gennaio
                log_new = proprietari[['Nome', 'Squadra_LFM', 'Lega', 'Rimb_Star']].rename(columns={'Rimb_Star': 'Rimborso'})
                log_new['Data'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                
                # Salvataggi incrociati
                save_to_github('leghe.csv', df_leghe_orig, f"Update crediti svincolo {scelta}")
                save_to_github('fantamanager-2021-rosters.csv', df_rosters_new, f"Rimozione {scelta} dalle rose")
                save_to_github('svincolati_gennaio.csv', log_new, f"Log svincolo {scelta}")
                
                st.success("GitHub Aggiornato con successo!")
                st.cache_data.clear()
                st.rerun()

    with col2:
        st.subheader("✂️ Taglio Volontario")
        sq_sel = st.selectbox("Seleziona Squadra:", sorted(df_base['Squadra_LFM'].unique()))
        gioc_sel = st.selectbox("Giocatore da tagliare:", df_base[df_base['Squadra_LFM'] == sq_sel]['Nome'].tolist())
        
        if st.button("Conferma Taglio"):
            info = df_base[(df_base['Squadra_LFM'] == sq_sel) & (df_base['Nome'] == gioc_sel)].iloc[0]
            
            # Aggiorna Crediti
            df_leghe_orig.loc[df_leghe_orig['Squadra'] == sq_sel, 'Crediti'] += info['Rimb_Taglio']
            
            # Rimuovi da Roster (solo per quella squadra)
            df_rosters_new = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
            index_to_drop = df_rosters_new[(df_rosters_new['Squadra_LFM'] == sq_sel) & (df_rosters_new['Id'] == info['Id'])].index
            df_rosters_new = df_rosters_new.drop(index_to_drop)
            
            # Log Tagli
            log_taglio = pd.DataFrame([{'Nome': gioc_sel, 'Squadra': sq_sel, 'Rimborso': info['Rimb_Taglio'], 'Data': pd.Timestamp.now()}])
            
            save_to_github('leghe.csv', df_leghe_orig, f"Update crediti taglio {gioc_sel}")
            save_to_github('fantamanager-2021-rosters.csv', df_rosters_new, f"Rimozione {gioc_sel} da {sq_sel}")
            save_to_github('tagli_volontari.csv', log_taglio, f"Log taglio {gioc_sel}")
            
            st.success("Taglio salvato su GitHub!")
            st.cache_data.clear()
            st.rerun()
