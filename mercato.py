import streamlit as st
import pandas as pd
import numpy as np
from github import Github
import io
import time

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="LFM - Registro Dettagliato", layout="wide", page_icon="⚖️")
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

# --- CONNESSIONE GITHUB ---
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except:
    st.error("Errore Secrets! Controlla GITHUB_TOKEN e REPO_NAME.")

# --- FUNZIONI API ---
def get_df_from_github(file_path):
    try:
        content = repo.get_contents(file_path)
        df = pd.read_csv(io.StringIO(content.decoded_content.decode('utf-8')))
        # FIX per KeyError: se esiste 'Rimborso' ma non 'Totale', rinomina
        if 'Rimborso' in df.columns and 'Totale' not in df.columns:
            df = df.rename(columns={'Rimborso': 'Totale'})
        return df
    except:
        return pd.DataFrame()

def save_to_github_direct(file_path, df, message):
    csv_content = df.to_csv(index=False)
    try:
        contents = repo.get_contents(file_path)
        repo.update_file(contents.path, message, csv_content, contents.sha)
    except:
        repo.create_file(file_path, message, csv_content)

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=2)
def load_all_data():
    df_rosters = get_df_from_github('fantamanager-2021-rosters.csv')
    df_leghe = get_df_from_github('leghe.csv')
    df_quot = pd.read_csv('quot.csv', encoding='latin1')
    df_esclusi = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')
    
    for df in [df_rosters, df_quot, df_esclusi, df_leghe]:
        if 'Id' in df.columns:
            df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
        if 'Crediti' in df.columns:
            df['Crediti'] = pd.to_numeric(df['Crediti'], errors='coerce').fillna(0).astype(int)

    df_m = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_m, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
    
    df_base['Lega'] = df_base['Lega'].fillna("N/A").astype(str)
    df_base['Nome'] = df_base['Nome'].fillna("Sconosciuto").astype(str)
    
    for c in ['Qt.I', 'FVM']:
        df_base[c] = pd.to_numeric(df_base[c], errors='coerce').fillna(0).astype(int)
    
    # CALCOLO COMPONENTI
    df_base['Meta_Qt'] = np.ceil(df_base['Qt.I'] / 2).astype(int)
    df_base['R_Star'] = (df_base['FVM'] + df_base['Meta_Qt']).astype(int)
    df_base['Meta_FVM'] = np.ceil(df_base['FVM'] / 2).astype(int)
    df_base['R_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    esclusi_ids = set(df_esclusi['Id'])
    df_base['Is_Escluso'] = df_base['Id'].isin(esclusi_ids)
    
    return df_base, df_leghe, df_rosters

df_base, df_leghe_upd, df_rosters_upd = load_all_data()

# --- NAVBAR ---
menu = st.sidebar.radio("Scegli Pagina:", ["1. Svincoli (*)", "2. Tagli", "3. Bilancio", "4. Rose"])

if menu == "1. Svincoli (*)":
    st.title("✈️ Svincoli (*) Automatici")
    df_star = df_base[df_base['Is_Escluso']].copy()
    if df_star.empty:
        st.success("Tutti i rimborsi (*) sono stati completati.")
    else:
        scelta = st.selectbox("Seleziona Giocatore:", [""] + sorted(df_star['Nome'].unique().tolist()))
        if scelta:
            targets = df_star[df_star['Nome'] == scelta]
            info = targets.iloc[0]
            st.warning(f"Svincolo di {scelta} ({info['R']}). Rimborso: FVM {info['FVM']} + 50% Quot ({info['Meta_Qt']}) = {info['R_Star']} cr.")
            
            if st.button("CONFERMA SVINCOLO GLOBALE"):
                for _, row in targets.iterrows():
                    df_leghe_upd.loc[df_leghe_upd['Squadra'] == row['Squadra_LFM'], 'Crediti'] += row['R_Star']
                
                id_target = info['Id']
                df_rosters_upd = df_rosters_upd[df_rosters_upd['Id'] != id_target]
                
                log = targets[['Nome', 'Squadra_LFM', 'Lega', 'R', 'FVM', 'Meta_Qt', 'R_Star']].copy()
                log.columns = ['Giocatore', 'Squadra', 'Lega', 'Ruolo', 'Quota_FVM', 'Quota_Qt', 'Totale']
                log['Tipo'] = "STAR (*)"
                
                save_to_github_direct('leghe.csv', df_leghe_upd, f"Svincolo {scelta}")
                save_to_github_direct('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimosso {scelta}")
                
                old_log = get_df_from_github('svincolati_gennaio.csv')
                save_to_github_direct('svincolati_gennaio.csv', pd.concat([old_log, log], ignore_index=True), f"Log {scelta}")
                
                st.cache_data.clear()
                st.rerun()

elif menu == "2. Tagli":
    st.title("✂️ Tagli Volontari")
    sq = st.selectbox("Squadra:", sorted(df_base['Squadra_LFM'].unique().tolist()))
    gioc = st.selectbox("Giocatore:", df_base[df_base['Squadra_LFM'] == sq]['Nome'].tolist())
    
    if st.button("ESEGUI TAGLIO"):
        info = df_base[(df_base['Squadra_LFM'] == sq) & (df_base['Nome'] == gioc)].iloc[0]
        df_leghe_upd.loc[df_leghe_upd['Squadra'] == sq, 'Crediti'] += info['R_Taglio']
        df_rosters_upd = df_rosters_upd[~((df_rosters_upd['Squadra_LFM'] == sq) & (df_rosters_upd['Id'] == info['Id']))]
        
        log_t = pd.DataFrame([{
            'Giocatore': gioc, 'Squadra': sq, 'Lega': info['Lega'], 'Ruolo': info['R'],
            'Quota_FVM': info['Meta_FVM'], 'Quota_Qt': info['Meta_Qt'], 
            'Totale': info['R_Taglio'], 'Tipo': 'TAGLIO'
        }])
        
        save_to_github_direct('leghe.csv', df_leghe_upd, f"Taglio {gioc}")
        save_to_github_direct('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimosso {gioc}")
        
        old_log_t = get_df_from_github('tagli_volontari.csv')
        save_to_github_direct('tagli_volontari.csv', pd.concat([old_log_t, log_t], ignore_index=True), f"Log {gioc}")
        
        st.cache_data.clear()
        st.rerun()

elif menu == "3. Bilancio":
    st.title("💰 Bilancio")
    lega_sel = st.selectbox("Lega:", sorted(df_base['Lega'].unique().tolist()))
    
    df_s = get_df_from_github('svincolati_gennaio.csv')
    df_t = get_df_from_github('tagli_volontari.csv')
    mov = pd.concat([df_s, df_t], ignore_index=True)
    
    # Calcolo bonus sicuro
    if not mov.empty and 'Totale' in mov.columns:
        bonus = mov.groupby('Squadra')['Totale'].sum()
    else:
        bonus = pd.Series()

    bil = df_leghe_upd[df_leghe_upd['Lega'] == lega_sel].copy()
    bil['Bonus'] = bil['Squadra'].map(bonus).fillna(0).astype(int)
    bil['Iniziale'] = bil['Crediti'] - bil['Bonus']
    
    st.table(bil[['Squadra', 'Iniziale', 'Bonus', 'Crediti']].rename(columns={'Crediti': 'Attuali'}))

elif menu == "4. Rose":
    st.title("📋 Rose e Registro")
    lega_sel = st.selectbox("Lega:", sorted(df_base['Lega'].unique().tolist()))
    
    df_v = df_base[df_base['Lega'] == lega_sel].sort_values('Squadra_LFM')
    for s in df_v['Squadra_LFM'].unique():
        with st.expander(f"Rosa {s}"):
            d_sq = df_v[df_v['Squadra_LFM'] == s].copy()
            d_sq['Ord'] = d_sq['R'].map(ORDINE_RUOLI)
            st.table(d_sq.sort_values('Ord')[['R', 'Nome', 'Qt.I', 'FVM']])
    
    st.divider()
    st.subheader("❌ Registro Uscite")
    df_s = get_df_from_github('svincolati_gennaio.csv')
    df_t = get_df_from_github('tagli_volontari.csv')
    res = pd.concat([df_s, df_t], ignore_index=True)
    
    if not res.empty:
        # Mostra colonne esistenti per evitare crash se il file è vecchio
        available_cols = [c for c in ['Squadra', 'Ruolo', 'Giocatore', 'Tipo', 'Quota_FVM', 'Quota_Qt', 'Totale'] if c in res.columns]
        res_view = res[res['Lega'] == lega_sel].sort_values(['Squadra', 'Giocatore'])
        st.dataframe(res_view[available_cols], use_container_width=True, hide_index=True)
    else:
        st.info("Nessun registro disponibile.")
