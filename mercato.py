import streamlit as st
import pandas as pd
import numpy as np
from github import Github
import io
import time

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="LFM Mercato Pro", layout="wide", page_icon="⚖️")
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

# --- CONNESSIONE GITHUB ---
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except:
    st.error("Verifica GITHUB_TOKEN e REPO_NAME nei Secrets di Streamlit!")

# --- FUNZIONE SALVATAGGIO LOG (CREA O AGGIUNGE) ---
def save_log_to_github(file_path, df_new_row, message):
    try:
        # Prova a leggere il file esistente
        contents = repo.get_contents(file_path)
        existing_df = pd.read_csv(io.StringIO(contents.decoded_content.decode('utf-8')))
        final_df = pd.concat([existing_df, df_new_row], ignore_index=True)
        repo.update_file(contents.path, message, final_df.to_csv(index=False), contents.sha)
    except:
        # Se il file non esiste (404), lo crea da zero
        repo.create_file(file_path, message, df_new_row.to_csv(index=False))

# --- FUNZIONE AGGIORNAMENTO FILE ESISTENTI (ROSE/CREDITI) ---
def update_existing_file(file_path, df, message):
    contents = repo.get_contents(file_path)
    repo.update_file(contents.path, message, df.to_csv(index=False), contents.sha)

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=10)
def load_data():
    ts = str(time.time()) # Forza GitHub a non usare la cache vecchia
    df_rosters = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/fantamanager-2021-rosters.csv?v={ts}', encoding='latin1')
    df_leghe = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/leghe.csv?v={ts}', encoding='latin1')
    df_quot = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/quot.csv?v={ts}', encoding='latin1')
    
    # Lettura file esclusi fornito
    df_esclusi = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')
    
    # Pulizia ID e conversione numerica
    for df in [df_rosters, df_quot, df_esclusi]:
        df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
    
    # Merge Dati
    df_merged = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_merged, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
    
    # Pulizia stringhe e valori
    df_base['Lega'] = df_base['Lega'].fillna("N/A").astype(str)
    df_base['Nome'] = df_base['Nome'].fillna("Sconosciuto").astype(str)
    df_base[['Qt.I', 'FVM']] = df_base[['Qt.I', 'FVM']].fillna(0)
    
    # Calcolo Rimborsi (Arrotondati per eccesso)
    df_base['Rimb_Star'] = np.ceil(df_base['FVM'] + (df_base['Qt.I'] / 2)).astype(int)
    df_base['Rimb_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    # Identificazione Esclusi (es. Pavard ID 4177 o Castellanos ID 6226)
    ids_esclusi = set(df_esclusi['Id'])
    df_base['Status_Escluso'] = df_base['Id'].isin(ids_esclusi)
    
    return df_base, df_leghe, df_rosters

df_base, df_leghe_orig, df_rosters_orig = load_data()

# --- INTERFACCIA SIDEBAR ---
menu = st.sidebar.radio("Navigazione:", ["1️⃣ Svincoli (*)", "2️⃣ Tagli", "3️⃣ Bilancio Finanziario", "4️⃣ Rose Aggiornate"])

# --- 1. SVINCOLI (*) ---
if menu == "1️⃣ Svincoli (*)":
    st.title("✈️ Svincoli (*) Automatici")
    st.info("Incrocio automatico tra Rose e file Esclusi.csv")
    
    df_star = df_base[df_base['Status_Escluso']].copy()
    if df_star.empty:
        st.success("Nessun giocatore attualmente in rosa appartiene alla lista esclusi.")
    else:
        nomi_star = sorted(df_star['Nome'].unique().tolist())
        scelta = st.selectbox("Seleziona Giocatore Asteriscato da rimuovere ovunque:", [""] + nomi_star)
        
        if scelta:
            coinvolti = df_star[df_star['Nome'] == scelta]
            st.warning(f"Il giocatore {scelta} verrà rimosso da {len(coinvolti)} squadre.")
            st.table(coinvolti[['Squadra_LFM', 'Lega', 'Rimb_Star']])
            
            if st.button(f"ESEGUI SVINCOLO GLOBALE: {scelta}"):
                # Aggiorna Crediti
                for _, row in coinvolti.iterrows():
                    df_leghe_orig.loc[df_leghe_orig['Squadra'] == row['Squadra_LFM'], 'Crediti'] += row['Rimb_Star']
                
                # Rimuovi da Rose
                id_giocatore = coinvolti.iloc[0]['Id']
                df_rosters_upd = df_rosters_orig[df_rosters_orig['Id'] != id_giocatore]
                
                # Log Operazione
                log_data = coinvolti[['Nome', 'Squadra_LFM', 'Lega', 'Rimb_Star']].copy()
                log_data.columns = ['Giocatore', 'Squadra', 'Lega', 'Rimborso']
                log_data['Data'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                log_data['Tipo'] = "STAR (*)"
                
                update_existing_file('leghe.csv', df_leghe_orig, f"Svincolo Star {scelta}")
                update_existing_file('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimozione {scelta}")
                save_log_to_github('svincolati_gennaio.csv', log_data, f"Log {scelta}")
                
                st.cache_data.clear()
                st.success(f"{scelta} svincolato correttamente!")
                time.sleep(1)
                st.rerun()

# --- 2. TAGLI ---
elif menu == "2️⃣ Tagli":
    st.title("✂️ Tagli Volontari")
    sq = st.selectbox("Seleziona Squadra:", sorted(df_base['Squadra_LFM'].unique().tolist()))
    giocatori_sq = df_base[df_base['Squadra_LFM'] == sq]
    gioc = st.selectbox("Seleziona Giocatore da tagliare:", giocatori_sq['Nome'].tolist())
    
    if st.button("CONFERMA TAGLIO"):
        info = giocatori_sq[giocatori_sq['Nome'] == gioc].iloc[0]
        # Aggiorna Crediti
        df_leghe_orig.loc[df_leghe_orig['Squadra'] == sq, 'Crediti'] += info['Rimb_Taglio']
        # Rimuovi da Rosa
        df_rosters_upd = df_rosters_orig[~((df_rosters_orig['Squadra_LFM'] == sq) & (df_rosters_orig['Id'] == info['Id']))]
        # Log
        log_t = pd.DataFrame([{'Giocatore': gioc, 'Squadra': sq, 'Lega': info['Lega'], 'Rimborso': info['Rimb_Taglio'], 'Data': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), 'Tipo': 'TAGLIO'}])
        
        update_existing_file('leghe.csv', df_leghe_orig, f"Taglio {gioc}")
        update_existing_file('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimozione {gioc}")
        save_log_to_github('tagli_volontari.csv', log_t, f"Log Taglio {gioc}")
        
        st.cache_data.clear()
        st.success(f"Taglio di {gioc} eseguito!")
        time.sleep(1)
        st.rerun()

# --- 3. BILANCIO ---
elif menu == "3️⃣ Bilancio Finanziario":
    st.title("💰 Bilancio Crediti")
    lega_sel = st.selectbox("Campionato:", sorted(df_base['Lega'].unique().tolist()))
    
    # Recupero log aggiornati
    ts = str(time.time())
    try:
        df_s = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/svincolati_gennaio.csv?v={ts}')
        df_t = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/tagli_volontari.csv?v={ts}')
        mov = pd.concat([df_s, df_t])
        bonus = mov.groupby('Squadra')['Rimborso'].sum()
    except: bonus = pd.Series()
    
    bil = df_leghe_orig[df_leghe_orig['Lega'] == lega_sel].copy()
    bil['Bonus Recuperato'] = bil['Squadra'].map(bonus).fillna(0).astype(int)
    bil['Crediti Iniziali'] = bil['Crediti'] - bil['Bonus Recuperato']
    
    st.table(bil[['Squadra', 'Crediti Iniziali', 'Bonus Recuperato', 'Crediti']].rename(columns={'Crediti': 'Crediti Attuali'}))

# --- 4. ROSE ---
elif menu == "4️⃣ Rose Aggiornate":
    st.title("📋 Rose e Resoconto Uscite")
    lega_sel = st.selectbox("Filtra Lega:", sorted(df_base['Lega'].unique().tolist()))
    
    df_v = df_base[df_base['Lega'] == lega_sel].sort_values('Squadra_LFM')
    for s in df_v['Squadra_LFM'].unique():
        with st.expander(f"Rosa {s}"):
            d_sq = df_v[df_v['Squadra_LFM'] == s].copy()
            d_sq['Ord'] = d_sq['R'].map(ORDINE_RUOLI)
            st.table(d_sq.sort_values('Ord')[['R', 'Nome', 'Qt.I', 'FVM']])
    
    st.divider()
    st.subheader("❌ Registro Operazioni (Svincoli e Tagli)")
    ts = str(time.time())
    try:
        df_s = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/svincolati_gennaio.csv?v={ts}')
        df_t = pd.read_csv(f'https://raw.githubusercontent.com/{repo_name}/main/tagli_volontari.csv?v={ts}')
        res = pd.concat([df_s, df_t])
        res_view = res[res['Lega'] == lega_sel].sort_values(['Squadra', 'Data'], ascending=[True, False])
        st.dataframe(res_view[['Squadra', 'Giocatore', 'Tipo', 'Rimborso', 'Data']], use_container_width=True, hide_index=True)
    except:
        st.info("Nessuna operazione registrata per questa lega.")
