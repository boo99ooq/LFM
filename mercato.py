import streamlit as st
import pandas as pd
import numpy as np
import math
from github import Github
import io

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="LFM Mercato & Riepilogo", layout="wide", page_icon="⚖️")

# --- COSTANTI ---
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

# --- CONNESSIONE GITHUB ---
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except Exception as e:
    st.error("Errore Configurazione GitHub Secrets. Verifica GITHUB_TOKEN e REPO_NAME nelle impostazioni di Streamlit Cloud.")

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
    # Caricamento file base da GitHub (o locali)
    df_rosters = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
    df_leghe = pd.read_csv('leghe.csv', encoding='latin1')
    df_quot = pd.read_csv('quot.csv', encoding='latin1')
    df_esclusi = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')
    
    # Pulizia ID
    for df in [df_rosters, df_quot, df_esclusi]:
        df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
    
    # Merge Rose + Leghe + Quotazioni
    df_merged = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_merged, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
    
    # Pulizia valori numerici e nomi
    df_base['Qt.I'] = pd.to_numeric(df_base['Qt.I'], errors='coerce').fillna(0)
    df_base['FVM'] = pd.to_numeric(df_base['FVM'], errors='coerce').fillna(0)
    df_base['Nome'] = df_base['Nome'].fillna("Sconosciuto").astype(str)
    
    # FORMULE RIMBORSO ORIGINALI
    df_base['Rimb_Star'] = np.ceil(df_base['FVM'] + (df_base['Qt.I'] / 2)).astype(int)
    df_base['Rimb_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    # Incrocio Esclusi
    ids_esclusi = set(df_esclusi['Id'])
    df_base['Status_Escluso'] = df_base['Id'].isin(ids_esclusi)
    
    return df_base, df_leghe, df_rosters

df_base, df_leghe_orig, df_rosters_orig = load_data()

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("⚖️ LFM Manager")
menu = st.sidebar.radio("Vai a:", ["✈️ Gestione Mercato", "📋 Riepilogo Rose & Crediti"])

# --- SEZIONE 1: GESTIONE MERCATO ---
if menu == "✈️ Gestione Mercato":
    st.title("🏃 Azioni di Mercato")
    tab_star, tab_volontari = st.tabs(["✈️ Svincoli (*) Automatici", "✂️ Tagli Volontari"])

    with tab_star:
        st.subheader("Svincoli Globali (*) (da file Esclusi)")
        df_star_presenti = df_base[df_base['Status_Escluso']].copy()
        
        if df_star_presenti.empty:
            st.success("Nessun giocatore in rosa appartiene alla lista esclusi.")
        else:
            nomi_esclusi = sorted(df_star_presenti['Nome'].unique())
            scelta_star = st.selectbox("Seleziona Giocatore Asteriscato:", [""] + nomi_esclusi)
            
            if scelta_star:
                proprietari = df_star_presenti[df_star_presenti['Nome'] == scelta_star]
                st.warning(f"Svincolo per {len(proprietari)} squadre. Rimborso: {proprietari.iloc[0]['Rimb_Star']} cr.")
                st.dataframe(proprietari[['Squadra_LFM', 'Lega', 'Rimb_Star']], hide_index=True)
                
                if st.button(f"ESEGUI SVINCOLO GLOBALE: {scelta_star}"):
                    # 1. Aggiorna Crediti
                    for _, row in proprietari.iterrows():
                        df_leghe_orig.loc[df_leghe_orig['Squadra'] == row['Squadra_LFM'], 'Crediti'] += row['Rimb_Star']
                    
                    # 2. Rimuovi da Roster (Globale)
                    id_p = proprietari.iloc[0]['Id']
                    df_rosters_upd = df_rosters_orig[df_rosters_orig['Id'] != id_p]
                    
                    # 3. Aggiorna Log
                    log_entry = proprietari[['Nome', 'Squadra_LFM', 'Lega', 'Rimb_Star']].copy()
                    log_entry.columns = ['Giocatore', 'Squadra', 'Lega', 'Rimborso']
                    log_entry['Data'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                    log_entry['Tipo'] = "STAR"

                    save_to_github('leghe.csv', df_leghe_orig, f"Svincolo Star {scelta_star}")
                    save_to_github('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimosso {scelta_star}")
                    save_to_github('svincolati_gennaio.csv', log_entry, f"Log {scelta_star}")
                    
                    st.success("GitHub sincronizzato!")
                    st.cache_data.clear()
                    st.rerun()

    with tab_volontari:
        st.subheader("Taglio Volontario (Singolo)")
        sq_sel = st.selectbox("Seleziona Squadra:", sorted(df_base['Squadra_LFM'].unique()))
        giocatori_sq = df_base[df_base['Squadra_LFM'] == sq_sel]
        gioc_sel = st.selectbox("Giocatore da tagliare:", giocatori_sq['Nome'].tolist())
        
        if st.button("CONFERMA TAGLIO"):
            info = giocatori_sq[giocatori_sq['Nome'] == gioc_sel].iloc[0]
            df_leghe_orig.loc[df_leghe_orig['Squadra'] == sq_sel, 'Crediti'] += info['Rimb_Taglio']
            
            df_rosters_upd = df_rosters_orig[~((df_rosters_orig['Squadra_LFM'] == sq_sel) & (df_rosters_orig['Id'] == info['Id']))]
            
            log_t = pd.DataFrame([{'Giocatore': gioc_sel, 'Squadra': sq_sel, 'Lega': info['Lega'], 'Rimborso': info['Rimb_Taglio'], 'Data': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), 'Tipo': 'TAGLIO'}])
            
            save_to_github('leghe.csv', df_leghe_orig, f"Taglio {gioc_sel}")
            save_to_github('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimosso {gioc_sel}")
            save_to_github('tagli_volontari.csv', log_t, f"Log Taglio {gioc_sel}")
            
            st.success("Taglio salvato su GitHub!")
            st.cache_data.clear()
            st.rerun()

# --- SEZIONE 2: RIEPILOGO ---
elif menu == "📋 Riepilogo Rose & Crediti":
    st.title("📋 Riepilogo Generale Rose e Bilanci")
    
    # 1. BILANCIO FINANZIARIO
    st.header("💰 Situazione Crediti")
    try:
        df_log_s = pd.read_csv('svincolati_gennaio.csv')
        df_log_t = pd.read_csv('tagli_volontari.csv')
        tutti_log = pd.concat([df_log_s, df_log_t])
        bonus_mappa = tutti_log.groupby('Squadra')['Rimborso'].sum()
    except:
        bonus_mappa = pd.Series()

    bilancio = df_leghe_orig.copy()
    bilancio['Bonus_Mercato'] = bilancio['Squadra'].map(bonus_mappa).fillna(0).astype(int)
    bilancio['Crediti_Finali'] = bilancio['Crediti'] + bilancio['Bonus_Mercato']
    
    st.dataframe(bilancio[['Lega', 'Squadra', 'Crediti', 'Bonus_Mercato', 'Crediti_Finali']].sort_values(['Lega', 'Squadra']), use_container_width=True, hide_index=True)

    # 2. ROSE AGGIORNATE
    st.divider()
    st.header("📋 Rose Definitive")
    lega_f = st.selectbox("Filtra per Campionato:", ["Tutti"] + sorted(df_base['Lega'].unique().tolist()))
    
    df_view = df_base.copy()
    if lega_f != "Tutti":
        df_view = df_view[df_view['Lega'] == lega_f]
    
    df_view = df_view.sort_values(by=['Lega', 'Squadra_LFM'])
    
    for squadra in df_view['Squadra_LFM'].unique():
        with st.expander(f"Rosa {squadra} ({df_view[df_view['Squadra_LFM'] == squadra]['Lega'].iloc[0]})"):
            rosa = df_view[df_view['Squadra_LFM'] == squadra].copy()
            rosa['Priority'] = rosa['R'].map(ORDINE_RUOLI)
            st.table(rosa.sort_values('Priority')[['R', 'Nome', 'Qt.I', 'FVM']])

    # 3. STORICO MOVIMENTI
    st.divider()
    st.header("❌ Elenco Giocatori Svincolati/Tagliati")
    try:
        tutti_log = tutti_log.sort_values(['Lega', 'Squadra'])
        st.dataframe(tutti_log[['Lega', 'Squadra', 'Giocatore', 'Tipo', 'Rimborso', 'Data']], use_container_width=True, hide_index=True)
    except:
        st.info("Nessun movimento registrato.")
