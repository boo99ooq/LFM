import streamlit as st
import pandas as pd
import numpy as np
from github import Github
import io
import time

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="LFM Mercato Manager", layout="wide", page_icon="⚖️")
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

# --- CONNESSIONE GITHUB ---
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except:
    st.error("Errore Secrets: Controlla GITHUB_TOKEN e REPO_NAME.")

# --- FUNZIONI DI SALVATAGGIO ---
def save_log_to_github(file_path, df_new_row, message):
    try:
        contents = repo.get_contents(file_path)
        existing_df = pd.read_csv(io.StringIO(contents.decoded_content.decode('utf-8')))
        final_df = pd.concat([existing_df, df_new_row], ignore_index=True)
        repo.update_file(contents.path, message, final_df.to_csv(index=False), contents.sha)
    except:
        repo.create_file(file_path, message, df_new_row.to_csv(index=False))

def update_existing_file(file_path, df, message):
    contents = repo.get_contents(file_path)
    repo.update_file(contents.path, message, df.to_csv(index=False), contents.sha)

# --- CARICAMENTO DATI CON BYPASS CACHE ---
@st.cache_data(ttl=5) # Cache brevissima per aggiornamenti rapidi
def load_data():
    ts = str(time.time())
    # File dinamici (cambiano con l'app)
    df_rosters = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/fantamanager-2021-rosters.csv?v={ts}', encoding='latin1')
    df_leghe = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/leghe.csv?v={ts}', encoding='latin1')
    
    # File statici o semistatici
    df_quot = pd.read_csv('quot.csv', encoding='latin1')
    df_esclusi = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')
    
    # Pulizia ID
    for df in [df_rosters, df_quot, df_esclusi]:
        df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
    
    # Merge
    df_merged = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_merged, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
    
    # Pulizia e Rimozione Decimali
    df_base['Lega'] = df_base['Lega'].fillna("N/A").astype(str)
    df_base['Nome'] = df_base['Nome'].fillna("Sconosciuto").astype(str)
    for col in ['Qt.I', 'FVM', 'Crediti']:
        if col in df_base.columns:
            df_base[col] = pd.to_numeric(df_base[col], errors='coerce').fillna(0).astype(int)
    
    # Formule Rimborso
    df_base['Rimb_Star'] = np.ceil(df_base['FVM'] + (df_base['Qt.I'] / 2)).astype(int)
    df_base['Rimb_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    # Incrocio Esclusi
    ids_esclusi = set(df_esclusi['Id'])
    df_base['Status_Escluso'] = df_base['Id'].isin(ids_esclusi)
    
    return df_base, df_leghe, df_rosters

df_base, df_leghe_orig, df_rosters_orig = load_data()

# --- NAVBAR ---
menu = st.sidebar.radio("Navigazione:", ["1️⃣ Svincoli (*)", "2️⃣ Tagli", "3️⃣ Bilancio Finanziario", "4️⃣ Rose Aggiornate"])

# --- 1. SVINCOLI (*) ---
if menu == "1️⃣ Svincoli (*)":
    st.title("✈️ Svincoli (*) Automatici")
    df_star = df_base[df_base['Status_Escluso']].copy()
    if df_star.empty:
        st.success("Tutti i giocatori asteriscati sono stati rimossi.")
    else:
        scelta = st.selectbox("Giocatore da svincolare globalmente:", [""] + sorted(df_star['Nome'].unique().tolist()))
        if scelta:
            targets = df_star[df_star['Nome'] == scelta]
            st.warning(f"Rimuovo {scelta} da {len(targets)} squadre.")
            if st.button("ESEGUI SVINCOLO GLOBALE"):
                # 1. Aggiorna Crediti (in locale)
                for _, row in targets.iterrows():
                    df_leghe_orig.loc[df_leghe_orig['Squadra'] == row['Squadra_LFM'], 'Crediti'] += row['Rimb_Star']
                
                # 2. Aggiorna Rose (rimuovi ID)
                id_p = targets.iloc[0]['Id']
                df_rosters_upd = df_rosters_orig[df_rosters_orig['Id'] != id_p]
                
                # 3. Log
                log = targets[['Nome', 'Squadra_LFM', 'Lega', 'Rimb_Star']].copy()
                log.columns = ['Giocatore', 'Squadra', 'Lega', 'Rimborso']
                log['Data'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                log['Tipo'] = "STAR (*)"
                
                # 4. Upload GitHub
                update_existing_file('leghe.csv', df_leghe_orig, f"Update Crediti {scelta}")
                update_existing_file('fantamanager-2021-rosters.csv', df_rosters_upd, f"Update Rose {scelta}")
                save_log_to_github('svincolati_gennaio.csv', log, f"Log {scelta}")
                
                st.cache_data.clear()
                st.success(f"{scelta} eliminato con successo!")
                time.sleep(2)
                st.rerun()

# --- 2. TAGLI ---
elif menu == "2️⃣ Tagli":
    st.title("✂️ Tagli Volontari")
    sq = st.selectbox("Squadra:", sorted(df_base['Squadra_LFM'].unique().tolist()))
    gioc = st.selectbox("Giocatore:", df_base[df_base['Squadra_LFM'] == sq]['Nome'].tolist())
    if st.button("CONFERMA TAGLIO"):
        info = df_base[(df_base['Squadra_LFM'] == sq) & (df_base['Nome'] == gioc)].iloc[0]
        df_leghe_orig.loc[df_leghe_orig['Squadra'] == sq, 'Crediti'] += info['Rimb_Taglio']
        df_rosters_upd = df_rosters_orig[~((df_rosters_orig['Squadra_LFM'] == sq) & (df_rosters_orig['Id'] == info['Id']))]
        log = pd.DataFrame([{'Giocatore': gioc, 'Squadra': sq, 'Lega': info['Lega'], 'Rimborso': info['Rimb_Taglio'], 'Data': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), 'Tipo': 'TAGLIO'}])
        
        update_existing_file('leghe.csv', df_leghe_orig, f"Taglio {gioc}")
        update_existing_file('fantamanager-2021-rosters.csv', df_rosters_upd, f"Update Rose {gioc}")
        save_log_to_github('tagli_volontari.csv', log, f"Log Taglio {gioc}")
        
        st.cache_data.clear()
        st.success(f"Taglio effettuato!")
        time.sleep(2)
        st.rerun()

# --- 3. BILANCIO ---
elif menu == "3️⃣ Bilancio Finanziario":
    st.title("💰 Situazione Crediti")
    lega_sel = st.selectbox("Lega:", sorted(df_base['Lega'].unique().tolist()))
    
    # Rilettura log da GitHub per il calcolo Bonus
    ts = str(time.time())
    try:
        df_s = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/svincolati_gennaio.csv?v={ts}')
        df_t = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/tagli_volontari.csv?v={ts}')
        mov = pd.concat([df_s, df_t])
        bonus = mov.groupby('Squadra')['Rimborso'].sum()
    except: bonus = pd.Series()
    
    # Dati puliti
    bil = df_leghe_orig[df_leghe_orig['Lega'] == lega_sel].copy()
    bil['Bonus'] = bil['Squadra'].map(bonus).fillna(0).astype(int)
    bil['Crediti Attuali'] = pd.to_numeric(bil['Crediti'], errors='coerce').fillna(0).astype(int)
    bil['Crediti Iniziali'] = bil['Crediti Attuali'] - bil['Bonus']
    
    st.table(bil[['Squadra', 'Crediti Iniziali', 'Bonus', 'Crediti Attuali']])

# --- 4. ROSE ---
elif menu == "4️⃣ Rose Aggiornate":
    st.title("📋 Riepilogo Rose e Registro")
    lega_sel = st.selectbox("Filtra Campionato:", sorted(df_base['Lega'].unique().tolist()))
    
    df_v = df_base[df_base['Lega'] == lega_sel].sort_values(['Squadra_LFM'])
    for s in df_v['Squadra_LFM'].unique():
        with st.expander(f"Rosa {s}"):
            d_sq = df_v[df_v['Squadra_LFM'] == s].copy()
            d_sq['Ord'] = d_sq['R'].map(ORDINE_RUOLI)
            # Rimozione .0 anche qui
            d_sq['Qt.I'] = d_sq['Qt.I'].astype(int)
            d_sq['FVM'] = d_sq['FVM'].astype(int)
            st.table(d_sq.sort_values('Ord')[['R', 'Nome', 'Qt.I', 'FVM']])
    
    st.divider()
    st.subheader("❌ Registro Uscite")
    ts = str(time.time())
    try:
        df_s = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/svincolati_gennaio.csv?v={ts}')
        df_t = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/tagli_volontari.csv?v={ts}')
        res = pd.concat([df_s, df_t])
        res['Rimborso'] = res['Rimborso'].astype(int)
        st.dataframe(res[res['Lega'] == lega_sel].sort_values(['Squadra', 'Data'], ascending=[True, False]), use_container_width=True, hide_index=True)
    except: st.info("Nessun registro disponibile.")
