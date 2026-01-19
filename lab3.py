import streamlit as st
import pandas as pd
import math
import os
import re

st.set_page_config(page_title="LFM Dashboard - Golden Edition", layout="wide", page_icon="⚖️")

# --- COSTANTI GLOBALI ---
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

# --- FUNZIONI UTILITY ---
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def calculate_stadium_bonus(capienza):
    casa = capienza / 20
    trasferta = math.floor((casa / 2) * 2) / 2
    return casa, trasferta

def format_num(num):
    """Rimuove il .0 se presente per pulizia visiva"""
    if num == int(num):
        return str(int(num))
    return str(round(num, 1))

def fix_league_names(df):
    if 'Lega' in df.columns:
        df['Lega'] = df['Lega'].replace(['Lega A', 'nan', 'Da Assegnare', None], 'Serie A')
    return df

# --- INIZIALIZZAZIONE SESSION STATE ---
if 'refunded_ids' not in st.session_state:
    st.session_state.refunded_ids = set()
if 'tagli_map' not in st.session_state:
    st.session_state.tagli_map = set()
if 'df_leghe_full' not in st.session_state:
    st.session_state.df_leghe_full = None

# --- CARICAMENTO DATI ---
@st.cache_data
def load_data():
    if not os.path.exists('fantamanager-2021-rosters.csv') or not os.path.exists('leghe.csv') or not os.path.exists('quot.csv'):
        return None, None, None
    
    df_r = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
    df_l = pd.read_csv('leghe.csv', encoding='latin1')
    df_q = pd.read_csv('quot.csv', encoding='latin1')

    # Pulizia ID (Fondamentale per i rimborsi)
    df_r['Id'] = pd.to_numeric(df_r['Id'], errors='coerce').fillna(0).astype(int)
    df_q['Id'] = pd.to_numeric(df_q['Id'], errors='coerce').fillna(0).astype(int)

    # Merge Rose + Leghe
    df_merged = pd.merge(df_r, df_l, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_merged = fix_league_names(df_merged)

        # 1. Convertiamo Qt.I in numeri, forzando gli errori a NaN (Not a Number)
    df_final['Qt.I'] = pd.to_numeric(df_final['Qt.I'], errors='coerce').fillna(0)
    
    # 2. Eseguiamo il calcolo usando la funzione di arrotondamento di numpy (più veloce e sicura)
    import numpy as np
    df_final['Rimborso_Taglio'] = np.ceil(df_final['Qt.I'] / 2).astype(int)
    
    # Chiavi e rimborsi (Arrotondati per eccesso come da regolamento)
    df_final['Taglio_Key'] = df_final['Id'].astype(str) + "_" + df_final['Squadra_LFM'].astype(str)
    df_final['Rimborso_Star'] = (df_final['Qt.I'] / 2).apply(math.ceil)
    df_final['Rimborso_Taglio'] = (df_final['Qt.I'] / 2).apply(math.ceil)
    
    return df_final, df_l, df_q

df_base, df_leghe_orig, df_all_quot = load_data()

if df_base is not None:
    # Aggiornamento flag in base alla memoria della sessione
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    # Sidebar Navigation
    st.sidebar.title("⚖️ LFM Dashboard")
    menu = st.sidebar.radio("Scegli Sezione:", ["📊 Statistiche Leghe", "🏃 Gestione Mercato", "📊 Ranking FVM", "📋 Rose Squadre", "🟢 Giocatori Liberi", "⚙️ Gestione Squadre"])

    # --- LOGICA CALCOLO CREDITI RESIDUI ---
    bonus_star = df_base[df_base['Rimborsato_Star']].groupby('Squadra_LFM')['Rimborso_Star'].sum()
    bonus_taglio = df_base[df_base['Rimborsato_Taglio']].groupby('Squadra_LFM')['Rimborso_Taglio'].sum()
    
    df_stats_base = df_leghe_orig.copy()
    df_stats_base['Squadra_Key'] = df_stats_base['Squadra'].str.strip().str.upper()
    df_stats_base = df_stats_base.set_index('Squadra')
    df_stats_base['Crediti'] = df_stats_base['Crediti'] + bonus_star.reindex(df_stats_base.index, fill_value=0) + bonus_taglio.reindex(df_stats_base.index, fill_value=0)
    df_stats_base = df_stats_base.reset_index()

    if menu == "📊 Statistiche Leghe":
        st.title("📊 Statistiche e Analisi")
        
        # Logica Stadi e Bonus
        stadi_list = []
        df_stadi = pd.read_csv('leghe.csv') # Riusiamo il file per gli stadi
        stadi_puliti = df_stadi.copy()
        stadi_puliti['Squadra_Key'] = stadi_puliti['Squadra'].str.strip().str.upper()
        
        df_attivi = df_base[~(df_base['Rimborsato_Star']) & ~(df_base['Rimborsato_Taglio'])]
        tecnici = df_attivi.groupby('Squadra_Key').agg({'FVM': 'sum', 'Qt.I': 'sum'}).reset_index().rename(columns={'FVM': 'FVM_Tot', 'Qt.I': 'Quot_Tot'})
        
        df_final_stats = pd.merge(df_stats_base, tecnici, on='Squadra_Key', how='left').fillna(0)
        
        if 'Lega' in df_final_stats.columns:
            medie_lega = df_final_stats.groupby('Lega').agg({'Crediti': 'mean', 'FVM_Tot': 'mean', 'Quot_Tot': 'mean'}).reindex(ORDINE_LEGHE)
            
            # Tabella Medie
            st.table(medie_lega.style.format("{:.1f}"))
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Confronto FVM Medio")
                st.bar_chart(medie_lega['FVM_Tot'])
            with c2:
                st.subheader("Confronto Crediti Medi")
                st.bar_chart(medie_lega['Crediti'])

    elif menu == "🏃 Gestione Mercato":
        st.title("🏃 Gestione Mercato")
        t1, t2 = st.tabs(["✈️ Svincoli (*)", "✂️ Tagli"])
        
        with t1:
            c = st.text_input("Cerca per svincolo (*):")
            if c:
                df_f = df_base[df_base['Nome'].str.contains(c, case=False, na=False)].drop_duplicates('Id').copy()
                
                # --- CORREZIONE CHIRURGICA PER KEYERROR ID ---
                ed = st.data_editor(
                    df_f[['Id', 'Rimborsato_Star', 'Nome', 'Squadra_LFM', 'Qt.I', 'FVM', 'Rimborso_Star']], 
                    hide_index=True,
                    column_config={"Id": st.column_config.Column(hidden=True)},
                    key="ed_star_vfinal"
                )
                
                if st.button("Conferma Svincoli (*)"):
                    for row in ed.to_dict('records'):
                        p_id = int(row['Id'])
                        if row['Rimborsato_Star']: st.session_state.refunded_ids.add(p_id)
                        else: st.session_state.refunded_ids.discard(p_id)
                    st.rerun()
            
            st.write("**Svincolati (*) Attuali:**")
            st.dataframe(df_base[df_base['Rimborsato_Star']][['Nome', 'Squadra_LFM', 'Qt.I', 'Rimborso_Star']], hide_index=True)

        with t2:
            c2 = st.text_input("Cerca per taglio:")
            if c2:
                df_t = df_base[df_base['Nome'].str.contains(c2, case=False, na=False) | df_base['Squadra_LFM'].str.contains(c2, case=False, na=False)].copy()
                
                # --- CORREZIONE CHIRURGICA PER KEYERROR TAGLIO_KEY ---
                ed_t = st.data_editor(
                    df_t[['Taglio_Key', 'Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'Qt.I', 'FVM', 'Rimborso_Taglio']], 
                    hide_index=True,
                    column_config={"Taglio_Key": st.column_config.Column(hidden=True)},
                    key="ed_taglio_vfinal"
                )
                
                if st.button("Conferma Tagli"):
                    for row in ed_t.to_dict('records'):
                        t_key = row['Taglio_Key']
                        if row['Rimborsato_Taglio']: st.session_state.tagli_map.add(t_key)
                        else: st.session_state.tagli_map.discard(t_key)
                    st.rerun()
            
            st.write("**Tagliati Attuali:**")
            st.dataframe(df_base[df_base['Rimborsato_Taglio']][['Nome', 'Squadra_LFM', 'Qt.I', 'Rimborso_Taglio']], hide_index=True)

    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM Internazionale")
        c1, c2 = st.columns(2)
        r_f = c1.multiselect("Ruolo:", ["P", "D", "C", "A"], default=["P", "D", "C", "A"])
        l_f = c2.multiselect("Lega:", ORDINE_LEGHE, default=ORDINE_LEGHE)
        
        df_rank = df_base[(df_base['R'].isin(r_f)) & (df_base['Lega'].isin(l_f)) & ~(df_base['Rimborsato_Star']) & ~(df_base['Rimborsato_Taglio'])]
        st.dataframe(df_rank.sort_values('FVM', ascending=False)[['Nome', 'Squadra_LFM', 'R', 'FVM']], use_container_width=True, hide_index=True)

    elif menu == "📋 Rose Squadre":
        l_sel = st.sidebar.selectbox("Filtra Lega:", ORDINE_LEGHE)
        sq_l = sorted(df_stats_base[df_stats_base['Lega'] == l_sel]['Squadra'].unique())
        sq_sel = st.sidebar.selectbox("Filtra Squadra:", sq_l)
        
        st.title(f"📋 Rosa {sq_sel}")
        rosa = df_base[(df_base['Squadra_LFM'] == sq_sel) & ~(df_base['Rimborsato_Star']) & ~(df_base['Rimborsato_Taglio'])].copy()
        rosa['R_Priority'] = rosa['R'].map(ORDINE_RUOLI)
        st.dataframe(rosa.sort_values('R_Priority')[['R', 'Nome', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)
        st.metric("FVM Totale Rosa", int(rosa['FVM'].sum()))

    elif menu == "🟢 Giocatori Liberi":
        st.title("🟢 Calciatori Liberi")
        try:
            df_esc = pd.read_csv('esclusi.csv', sep='\t', header=0)
            ids_esc = set(df_esc['Id'])
        except: 
            ids_esc = set()
        
        ids_occ = set(df_base[~(df_base['Rimborsato_Star']) & ~(df_base['Rimborsato_Taglio'])]['Id'])
        df_lib = df_all_quot[~df_all_quot['Id'].isin(ids_occ) & ~df_all_quot['Id'].isin(ids_esc)]
        st.dataframe(df_lib.sort_values('FVM', ascending=False)[['Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione & Backup")
        if st.session_state.df_leghe_full is None:
            st.session_state.df_leghe_full = df_stats_base
        
        edited = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Salva Modifiche Crediti"):
            st.session_state.df_leghe_full = edited
            st.success("Crediti aggiornati in sessione!")
        
        st.divider()
        c1, c2 = st.columns(2)
        c1.download_button("Scarica Backup Svincoli (*)", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False), "backup_star.csv")
        c2.download_button("Scarica Backup Tagli", pd.DataFrame({'Key': list(st.session_state.tagli_map)}).to_csv(index=False), "backup_tagli.csv")
