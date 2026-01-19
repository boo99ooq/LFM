import streamlit as st
import pandas as pd
import numpy as np
import math
from github import Github
import io

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="LFM Mercato & Rose", layout="wide", page_icon="⚖️")

# --- COSTANTI ---
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

# --- CONNESSIONE GITHUB (Secrets) ---
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except Exception as e:
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
    
    df_base[['Qt.I', 'FVM']] = df_base[['Qt.I', 'FVM']].fillna(0)
    df_base['Nome'] = df_base['Nome'].fillna("Sconosciuto").astype(str)
    
    # Formule di rimborso originali
    df_base['Rimb_Star'] = np.ceil(df_base['FVM'] + (df_base['Qt.I'] / 2)).astype(int)
    df_base['Rimb_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    # Identificazione automatica esclusi
    ids_esclusi = set(df_esclusi['Id'])
    df_base['In_Esclusi'] = df_base['Id'].isin(ids_esclusi)
    
    return df_base, df_leghe, df_rosters

df_base, df_leghe_orig, df_rosters_orig = load_data()

# --- NAVIGAZIONE ---
st.sidebar.title("🎮 LFM Control Panel")
menu = st.sidebar.radio("Seleziona Pagina:", ["🏃 Gestione Mercato", "📋 Riepilogo Rose & Bilancio"])

# --- PAGINA 1: GESTIONE MERCATO ---
if menu == "🏃 Gestione Mercato":
    st.title("🏃 Operazioni di Mercato")
    t1, t2 = st.tabs(["✈️ Svincoli (*) Automatici", "✂️ Tagli Volontari"])
    
    with t1:
        st.subheader("Svincoli Globali (*) da file Esclusi")
        df_esclusi_in_rosa = df_base[df_base['In_Esclusi']].copy()
        
        if df_esclusi_in_rosa.empty:
            st.success("Nessun giocatore in rosa è presente nel file esclusi.")
        else:
            lista_nomi = sorted(df_esclusi_in_rosa['Nome'].unique())
            scelta = st.selectbox("Giocatore da svincolare globalmente:", [""] + lista_nomi)
            
            if scelta:
                targets = df_esclusi_in_rosa[df_esclusi_in_rosa['Nome'] == scelta]
                st.warning(f"Rimuovo {scelta} da {len(targets)} squadre. Rimborso: {targets.iloc[0]['Rimb_Star']}")
                
                if st.button(f"ESEGUI SVINCOLO: {scelta}"):
                    # Logica rimborsi e rimozione (come i messaggi precedenti)
                    for _, row in targets.iterrows():
                        df_leghe_orig.loc[df_leghe_orig['Squadra'] == row['Squadra_LFM'], 'Crediti'] += row['Rimb_Star']
                    
                    df_rosters_upd = df_rosters_orig[df_rosters_orig['Id'] != targets.iloc[0]['Id']]
                    
                    log_entry = targets[['Nome', 'Squadra_LFM', 'Lega', 'Rimb_Star']].copy()
                    log_entry.columns = ['Giocatore', 'Squadra', 'Lega', 'Rimborso']
                    log_entry['Data'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                    log_entry['Tipo'] = "STAR (*)"
                    
                    save_to_github('leghe.csv', df_leghe_orig, f"Svincolo {scelta}")
                    save_to_github('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimosso {scelta}")
                    save_to_github('svincolati_gennaio.csv', log_entry, f"Log {scelta}")
                    
                    st.success("Sincronizzato con GitHub!")
                    st.cache_data.clear()
                    st.rerun()

    with t2:
        st.subheader("Taglio Singolo per Squadra")
        sq = st.selectbox("Squadra:", sorted(df_base['Squadra_LFM'].unique()))
        gioc = st.selectbox("Giocatore:", df_base[df_base['Squadra_LFM'] == sq]['Nome'].tolist())
        
        if st.button("CONFERMA TAGLIO"):
            info = df_base[(df_base['Squadra_LFM'] == sq) & (df_base['Nome'] == gioc)].iloc[0]
            df_leghe_orig.loc[df_leghe_orig['Squadra'] == sq, 'Crediti'] += info['Rimb_Taglio']
            df_rosters_upd = df_rosters_orig[~((df_rosters_orig['Squadra_LFM'] == sq) & (df_rosters_orig['Id'] == info['Id']))]
            
            log_t = pd.DataFrame([{'Giocatore': gioc, 'Squadra': sq, 'Lega': info['Lega'], 'Rimborso': info['Rimb_Taglio'], 'Data': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), 'Tipo': 'TAGLIO'}])
            
            save_to_github('leghe.csv', df_leghe_orig, f"Taglio {gioc}")
            save_to_github('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimosso {gioc}")
            save_to_github('tagli_volontari.csv', log_t, f"Log {gioc}")
            
            st.success("Taglio salvato!")
            st.cache_data.clear()
            st.rerun()

# --- PAGINA 2: RIEPILOGO ROSE E BILANCIO ---
elif menu == "📋 Riepilogo Rose & Bilancio":
    st.title("📋 Riepilogo Ufficiale Rose e Crediti")
    
    # 1. ANALISI CREDITI PRIMA/DOPO
    st.header("💰 Bilancio Finanziario")
    
    # Carichiamo i log per calcolare il "Bonus"
    try:
        df_s = pd.read_csv('svincolati_gennaio.csv')
        df_t = pd.read_csv('tagli_volontari.csv')
        movimenti = pd.concat([df_s, df_t])
        bonus_mappa = movimenti.groupby('Squadra')['Rimborso'].sum()
    except:
        movimenti = pd.DataFrame()
        bonus_mappa = pd.Series()

    bilancio = df_leghe_orig.copy()
    bilancio['Bonus Recuperato'] = bilancio['Squadra'].map(bonus_mappa).fillna(0).astype(int)
    # Calcolo: Crediti nel file sono già "Dopo", quindi il "Prima" è Crediti - Bonus
    bilancio['Crediti Iniziali'] = bilancio['Crediti'] - bilancio['Bonus Recuperato']
    
    st.dataframe(
        bilancio[['Lega', 'Squadra', 'Crediti Iniziali', 'Bonus Recuperato', 'Crediti']], 
        column_config={"Crediti": "Crediti Attuali (Post)"},
        use_container_width=True, hide_index=True
    )

    st.divider()

    # 2. ROSE PER CAMPIONATO E SQUADRA
    st.header("📋 Elenco Rose Attuali")
    lega_sel = st.selectbox("Filtra per Campionato:", ["Tutti"] + sorted(df_base['Lega'].unique().tolist()))
    
    df_view = df_base.copy()
    if lega_sel != "Tutti":
        df_view = df_view[df_view['Lega'] == lega_sel]
    
    # Ordinamento Campionato -> Squadra
    df_view = df_view.sort_values(['Lega', 'Squadra_LFM'])
    
    for squadra in df_view['Squadra_LFM'].unique():
        with st.expander(f"Rosa {squadra} ({df_view[df_view['Squadra_LFM'] == squadra]['Lega'].iloc[0]})"):
            df_sq = df_view[df_view['Squadra_LFM'] == squadra].copy()
            df_sq['Ord'] = df_sq['R'].map(ORDINE_RUOLI)
            st.table(df_sq.sort_values('Ord')[['R', 'Nome', 'Qt.I', 'FVM']])

    st.divider()

    # 3. ELENCO GIOCATORI RIMOSSI
    st.header("❌ Storico Giocatori Svincolati e Tagliati")
    if not movimenti.empty:
        # Riordino richiesto per campionato e per rosa
        movimenti = movimenti.sort_values(['Lega', 'Squadra'])
        st.dataframe(movimenti[['Lega', 'Squadra', 'Giocatore', 'Tipo', 'Rimborso', 'Data']], use_container_width=True, hide_index=True)
    else:
        st.info("Nessun giocatore rimosso finora.")
