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
    """Formatta i numeri rimuovendo il .0 superfluo"""
    try:
        if num == int(num):
            return str(int(num))
        return str(round(num, 1))
    except:
        return str(num)

def fix_league_names(df):
    if 'Lega' in df.columns:
        df['Lega'] = df['Lega'].replace(['Lega A', 'nan', 'Da Assegnare', None], 'Serie A')
        df['Lega'] = df['Lega'].fillna('Serie A')
    return df

# --- 1. CARICAMENTO DATI ---
@st.cache_data
def load_static_data():
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            df_owned = pd.merge(df_rose, df_quot, on='Id', how='left')
            df_owned['Nome'] = df_owned['Nome'].fillna("ID: " + df_owned['Id'].astype(int, errors='ignore').astype(str))
            df_owned['Qt.I'] = pd.to_numeric(df_owned['Qt.I'], errors='coerce').fillna(0)
            df_owned['FVM'] = pd.to_numeric(df_owned['FVM'], errors='coerce').fillna(0)
            df_owned['Squadra_LFM'] = df_owned['Squadra_LFM'].str.strip()
            
            df_owned['Rimborso_Star'] = df_owned['FVM'] + (df_owned['Qt.I'] / 2)
            df_owned['Rimborso_Taglio'] = (df_owned['FVM'] + df_owned['Qt.I']) / 2
            
            return df_owned, df_quot
        except: continue
    return None, None

# --- 2. GESTIONE STATO ---
if 'refunded_ids' not in st.session_state:
    try:
        db_p = pd.read_csv('database_lfm.csv')
        st.session_state.refunded_ids = set(db_p['Id'].tolist())
    except: st.session_state.refunded_ids = set()

if 'tagli_map' not in st.session_state:
    try:
        db_t = pd.read_csv('database_tagli.csv')
        db_t['Key'] = db_t['Id'].astype(str) + "_" + db_t['Squadra'].astype(str)
        st.session_state.tagli_map = set(db_t['Key'].tolist())
    except: st.session_state.tagli_map = set()

if 'df_leghe_full' not in st.session_state:
    try:
        df_temp = pd.read_csv('leghe.csv', encoding='latin1')
        df_temp['Squadra'] = df_temp['Squadra'].str.strip()
        df_temp['Crediti'] = pd.to_numeric(df_temp['Crediti'], errors='coerce').fillna(0)
        st.session_state.df_leghe_full = fix_league_names(df_temp)
    except: 
        st.session_state.df_leghe_full = pd.DataFrame(columns=['Squadra', 'Lega', 'Crediti'])

try:
    df_stadi = pd.read_csv('stadi.csv', encoding='latin1')
    df_stadi['Squadra'] = df_stadi['Squadra'].str.strip()
    df_stadi['Stadio'] = pd.to_numeric(df_stadi['Stadio'], errors='coerce').fillna(0)
except: 
    df_stadi = pd.DataFrame(columns=['Squadra', 'Stadio'])

df_base, df_all_quot = load_static_data()

if df_base is not None:
    # --- UNIFORMITÀ DATI ---
    leghe_pulite = st.session_state.df_leghe_full.copy()
    leghe_pulite['Squadra_Key'] = leghe_pulite['Squadra'].str.strip().str.upper()
    df_base['Squadra_Key'] = df_base['Squadra_LFM'].str.strip().str.upper()
    
    if 'Lega' in df_base.columns: df_base = df_base.drop(columns=['Lega', 'Crediti'], errors='ignore')
    df_base = pd.merge(df_base, leghe_pulite.drop(columns=['Squadra']), on='Squadra_Key', how='left')
    
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    menu = st.sidebar.radio("Navigazione:", ["🏠 Dashboard", "🗓️ Calendari Campionati", "🏆 Coppe e Preliminari", "🏃 Gestione Mercato", "📊 Ranking FVM", "💰 Ranking Finanziario", "📋 Rose Complete", "🟢 Giocatori Liberi", "📈 Statistiche Leghe", "⚙️ Gestione Squadre"])

    # --- 💰 RANKING FINANZIARIO ---
    if menu == "💰 Ranking Finanziario":
        st.title("💰 Ranking Finanziario")
        
        # Selezione Ambito Ranking
        ambito = st.selectbox("Seleziona Ambito:", ["Mondiale (Top 40)"] + ORDINE_LEGHE)
        
        df_fin = st.session_state.df_leghe_full.copy()
        df_fin['Squadra_Key'] = df_fin['Squadra'].str.strip().str.upper()
        
        # Filtro per Lega se selezionato
        if ambito != "Mondiale (Top 40)":
            df_fin = df_fin[df_fin['Lega'] == ambito]

        stadi_fin = df_stadi.copy()
        stadi_fin['Squadra_Key'] = stadi_fin['Squadra'].str.strip().str.upper()
        df_fin = pd.merge(df_fin, stadi_fin[['Squadra_Key', 'Stadio']], on='Squadra_Key', how='left').fillna(0)
        
        res_star = df_base[df_base['Rimborsato_Star']].groupby('Squadra_Key')['Rimborso_Star'].sum().reset_index()
        res_tagli = df_base[df_base['Rimborsato_Taglio']].groupby('Squadra_Key')['Rimborso_Taglio'].sum().reset_index()
        df_fin = pd.merge(df_fin, res_star, on='Squadra_Key', how='left').fillna(0)
        df_fin = pd.merge(df_fin, res_tagli, on='Squadra_Key', how='left').fillna(0)
        df_fin['Crediti_Tot'] = df_fin['Crediti'] + df_fin['Rimborso_Star'] + df_fin['Rimborso_Taglio']
        
        df_attivi = df_base[~(df_base['Rimborsato_Star']) & ~(df_base['Rimborsato_Taglio'])]
        fvm_tot = df_attivi.groupby('Squadra_Key')['FVM'].sum().reset_index().rename(columns={'FVM': 'FVM_Rosa'})
        df_fin = pd.merge(df_fin, fvm_tot, on='Squadra_Key', how='left').fillna(0)
        
        # FORMULA ORIGINALE
        df_fin['Punteggio'] = df_fin['Crediti_Tot'] + df_fin['FVM_Rosa'] + (df_fin['Stadio'] * 10)
        
        df_fin = df_fin.sort_values(by='Punteggio', ascending=False).reset_index(drop=True)
        df_fin.index += 1
        
        display_fin = df_fin[['Squadra', 'Lega', 'Crediti_Tot', 'FVM_Rosa', 'Stadio', 'Punteggio']].copy()
        display_fin.columns = ['Squadra', 'Lega', 'Crediti', 'FVM Rosa', 'Stadio (k)', 'Punteggio TOT']
        for col in ['Crediti', 'FVM Rosa', 'Stadio (k)', 'Punteggio TOT']:
            display_fin[col] = display_fin[col].apply(format_num)
        
        st.dataframe(display_fin, use_container_width=True)
        st.caption("Formula: Crediti (x1) + FVM Rosa (x1) + (Stadio * 10)")

    # --- RESTANTI SEZIONI (Dashboard, Calendari, ecc. rimangono invariate) ---
    # [Qui il codice prosegue come nelle versioni precedenti...]
    elif menu == "🏠 Dashboard":
        # ... (Stesso codice della dashboard fornito prima)
