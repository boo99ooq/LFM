import streamlit as st
import pandas as pd
import numpy as np
import math
from github import Github
import io

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="LFM - Portale Mercato", layout="wide", page_icon="⚖️")

# --- COSTANTI ---
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

# --- CONNESSIONE GITHUB ---
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except:
    st.error("Errore GitHub Secrets. Verifica GITHUB_TOKEN e REPO_NAME.")

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

# --- CARICAMENTO DATI ---
@st.cache_data
def load_data():
    df_rosters = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
    df_leghe = pd.read_csv('leghe.csv', encoding='latin1')
    df_quot = pd.read_csv('quot.csv', encoding='latin1')
    df_esclusi = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')
    
    for df in [df_rosters, df_quot, df_esclusi]:
        df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
    
    df_base = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_base, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
    
    # Pulizia anti-TypeError
    df_base['Lega'] = df_base['Lega'].fillna("Serie A").astype(str)
    df_base['Nome'] = df_base['Nome'].fillna("Sconosciuto").astype(str)
    df_base[['Qt.I', 'FVM']] = df_base[['Qt.I', 'FVM']].fillna(0)
    
    # Formule originali
    df_base['Rimb_Star'] = np.ceil(df_base['FVM'] + (df_base['Qt.I'] / 2)).astype(int)
    df_base['Rimb_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    # Incrocio esclusi
    ids_esclusi = set(df_esclusi['Id'])
    df_base['Status_Escluso'] = df_base['Id'].isin(ids_esclusi)
    
    return df_base, df_leghe, df_rosters

df_base, df_leghe_orig, df_rosters_orig = load_data()

# --- NAVBAR 4 PAGINE ---
st.sidebar.title("🎮 LFM Control Panel")
menu = st.sidebar.radio("Navigazione:", [
    "1️⃣ Svincoli (*)", 
    "2️⃣ Tagli Volontari", 
    "3️⃣ Bilancio Finanziario", 
    "4️⃣ Rose Aggiornate"
])

# --- PAGINA 1: SVINCOLI (*) ---
if menu == "1️⃣ Svincoli (*)":
    st.title("✈️ Svincoli Automatici (*)")
    st.info("Giocatori in rosa presenti nel file esclusi.csv. Azione Globale.")
    
    df_star = df_base[df_base['Status_Escluso']].copy()
    if df_star.empty:
        st.success("Nessun giocatore in rosa è tra gli esclusi.")
    else:
        lista_nomi = sorted(df_star['Nome'].unique())
        scelta = st.selectbox("Seleziona Giocatore:", [""] + lista_nomi)
        if scelta:
            targets = df_star[df_star['Nome'] == scelta]
            st.warning(f"Svincolo per {len(targets)} squadre. Rimborso: {targets.iloc[0]['Rimb_Star']}")
            if st.button(f"ESEGUI SVINCOLO GLOBALE: {scelta}"):
                for _, row in targets.iterrows():
                    df_leghe_orig.loc[df_leghe_orig['Squadra'] == row['Squadra_LFM'], 'Crediti'] += row['Rimb_Star']
                df_rosters_upd = df_rosters_orig[df_rosters_orig['Id'] != targets.iloc[0]['Id']]
                log_entry = targets[['Nome', 'Squadra_LFM', 'Lega', 'Rimb_Star']].copy()
                log_entry.columns = ['Giocatore', 'Squadra', 'Lega', 'Rimborso']
                log_entry['Data'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                log_entry['Tipo'] = "STAR (*)"
                save_to_github('leghe.csv', df_leghe_orig, f"Star {scelta}")
                save_to_github('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimosso {scelta}")
                save_to_github('svincolati_gennaio.csv', log_entry, f"Log Star {scelta}")
                st.cache_data.clear()
                st.rerun()

# --- PAGINA 2: TAGLI VOLONTARI ---
elif menu == "2️⃣ Tagli Volontari":
    st.title("✂️ Tagli Volontari")
    st.info("Taglio di un giocatore da una singola squadra specifica.")
    sq = st.selectbox("Seleziona Squadra:", sorted(df_base['Squadra_LFM'].unique()))
    gioc = st.selectbox("Seleziona Giocatore:", df_base[df_base['Squadra_LFM'] == sq]['Nome'].tolist())
    if st.button("CONFERMA TAGLIO"):
        info = df_base[(df_base['Squadra_LFM'] == sq) & (df_base['Nome'] == gioc)].iloc[0]
        df_leghe_orig.loc[df_leghe_orig['Squadra'] == sq, 'Crediti'] += info['Rimb_Taglio']
        df_rosters_upd = df_rosters_orig[~((df_rosters_orig['Squadra_LFM'] == sq) & (df_rosters_orig['Id'] == info['Id']))]
        log_t = pd.DataFrame([{'Giocatore': gioc, 'Squadra': sq, 'Lega': info['Lega'], 'Rimborso': info['Rimb_Taglio'], 'Data': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), 'Tipo': 'TAGLIO'}])
        save_to_github('leghe.csv', df_leghe_orig, f"Taglio {gioc}")
        save_to_github('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimosso {gioc}")
        save_to_github('tagli_volontari.csv', log_t, f"Log Taglio {gioc}")
        st.cache_data.clear()
        st.rerun()

# --- PAGINA 3: BILANCIO FINANZIARIO ---
elif menu == "3️⃣ Bilancio Finanziario":
    st.title("💰 Bilancio Crediti")
    lega_list = sorted(df_base['Lega'].dropna().unique().tolist())
    lega_sel = st.selectbox("Seleziona Campionato:", lega_list)
    
    try:
        df_s = pd.read_csv('svincolati_gennaio.csv'); df_t = pd.read_csv('tagli_volontari.csv')
        movimenti = pd.concat([df_s, df_t])
        bonus_mappa = movimenti.groupby('Squadra')['Rimborso'].sum()
    except: bonus_mappa = pd.Series()

    bilancio = df_leghe_orig[df_leghe_orig['Lega'] == lega_sel].copy()
    bilancio['Bonus'] = bilancio['Squadra'].map(bonus_mappa).fillna(0).astype(int)
    bilancio['Prima'] = bilancio['Crediti'] - bilancio['Bonus']
    
    st.table(bilancio[['Squadra', 'Prima', 'Bonus', 'Crediti']].rename(columns={'Crediti': 'Dopo (Attuali)'}))

# --- PAGINA 4: ROSE AGGIORNATE ---
elif menu == "4️⃣ Rose Aggiornate":
    st.title("📋 Rose e Resoconto Uscite")
    lega_sel = st.selectbox("Filtra Campionato:", sorted(df_base['Lega'].unique().tolist()))
    
    df_view = df_base[df_base['Lega'] == lega_sel].sort_values('Squadra_LFM')
    for squadra in df_view['Squadra_LFM'].unique():
        with st.expander(f"Rosa {squadra}"):
            df_sq = df_view[df_view['Squadra_LFM'] == squadra].copy()
            df_sq['Ord'] = df_sq['R'].map(ORDINE_RUOLI)
            st.table(df_sq.sort_values('Ord')[['R', 'Nome', 'Qt.I', 'FVM']])

    st.divider()
    st.subheader("❌ Resoconto Giocatori Rimossi")
    try:
        df_s = pd.read_csv('svincolati_gennaio.csv'); df_t = pd.read_csv('tagli_volontari.csv')
        resoconto = pd.concat([df_s, df_t])
        resoconto = resoconto[resoconto['Lega'] == lega_sel].sort_values(['Squadra', 'Data'])
        st.dataframe(resoconto[['Squadra', 'Giocatore', 'Tipo', 'Rimborso', 'Data']], use_container_width=True, hide_index=True)
    except:
        st.info("Nessuna operazione per questo campionato.")
