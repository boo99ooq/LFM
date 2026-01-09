import streamlit as st
import pandas as pd
import math
import os
import re

st.set_page_config(page_title="LFM Dashboard - Golden Edition", layout="wide", page_icon="⚖️")

# --- COSTANTI GLOBALI ---
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}

# --- FUNZIONI UTILITY ---
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def calculate_stadium_bonus(capienza):
    casa = capienza / 20
    # Arrotondamento per difetto allo 0.5 più vicino
    trasferta = math.floor((casa / 2) * 2) / 2
    return casa, trasferta

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
            
            # Calcolo rimborsi (Svincolo * = 100% FVM + 50% Quotazione)
            df_owned['Rimborso_Star'] = df_owned['FVM'] + (df_owned['Qt.I'] / 2)
            # Calcolo rimborsi (Taglio = 50% di FVM + Quotazione)
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
        st.session_state.df_leghe_full = df_temp
    except: st.session_state.df_leghe_full = pd.DataFrame(columns=['Squadra', 'Lega', 'Crediti'])

try:
    df_stadi = pd.read_csv('stadi.csv', encoding='latin1')
    df_stadi['Squadra'] = df_stadi['Squadra'].str.strip()
    df_stadi['Stadio'] = pd.to_numeric(df_stadi['Stadio'], errors='coerce').fillna(0)
except: df_stadi = pd.DataFrame(columns=['Squadra', 'Stadio'])

df_base, df_all_quot = load_static_data()

if df_base is not None:
    df_base = pd.merge(df_base, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    menu = st.sidebar.radio("Navigazione:", ["🏠 Dashboard", "🗓️ Calendari Campionati", "🏆 Coppe e Preliminari", "🏃 Gestione Mercato", "📊 Ranking FVM", "📋 Rose Complete", "🟢 Giocatori Liberi", "⚙️ Gestione Squadre"])

    # --- 🏠 DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Dashboard Golden Edition")
        leghe_eff = [l for l in ORDINE_LEGHE if l in df_base['Lega'].values]
        cols = st.columns(2)
        for i, lega_nome in enumerate(leghe_eff):
            with cols[i % 2]:
                df_l = df_base[df_base['Lega'] == lega_nome]
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum', 'Nome': lambda x: ", ".join(x)}).reset_index()
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum', 'Nome': lambda x: ", ".join(x)}).reset_index()
                attivi = df_l[~(df_l['Rimborsato_Star']) & ~(df_l['Rimborsato_Taglio'])].groupby('Squadra_LFM').size().reset_index(name='NG')
                
                tabella = pd.merge(df_l[['Squadra_LFM', 'Crediti']].drop_duplicates(), res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli.rename(columns={'Nome':'N_T'}), on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, attivi, on='Squadra_LFM', how='left').fillna(0)
                tabella['Totale'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                
                st.markdown(f"### 🏆 {lega_nome}")
                for _, sq in tabella.sort_values(by='Squadra_LFM').iterrows():
                    cap = df_stadi[df_stadi['Squadra'] == sq['Squadra_LFM']]['Stadio'].values
                    cap_txt = f"{int(cap[0]):,}" if len(cap)>0 else "N.D."
                    
                    st.markdown(f"""<div style="background-color: {MAPPATURA_COLORI.get(lega_nome)}; padding: 12px; border-radius: 10px; margin-bottom: 8px; color: white;">
                        <div style="display: flex; justify-content: space-between;"><b>{sq['Squadra_LFM']}</b> <span style="font-size:10px;">🏟️ {cap_txt}</span></div>
                        <div style="font-size:20px; font-weight:bold;">{int(sq['Totale'])} cr <small style="font-size:10px; font-weight:normal;">({sq['NG']} giog.)</small></div>
                        <div style="font-size:10px; opacity:0.8;">✈️ {sq['Nome'] if sq['Nome'] != 0 else '-'}</div>
                        <div style="font-size:10px; opacity:0.8;">✂️ {sq['N_T'] if sq['N_T'] != 0 else '-'}</div>
                    </div>""", unsafe_allow_html=True)

    # --- 🗓️ CALENDARI ---
    elif menu == "🗓️ Calendari Campionati":
        st.title("🗓️ Calendari Campionati")
        files = [f for f in os.listdir('.') if f.startswith("Calendario_") and "CHAMPIONS" not in f.upper() and f.endswith(".csv")]
        if files:
            camp = st.selectbox("Seleziona:", files)
            df_c = pd.read_csv(camp, header=None, encoding='latin1').fillna("")
            g_pos = [(str(df_c.iloc[r, c]).strip(), r, c) for c in [0, 6] for r in range(len(df_c)) if "Giornata" in str(df_c.iloc[r, c]) and "serie a" not in str(df_c.iloc[r, c]).lower()]
            sel_g = st.selectbox("Giornata:", sorted(list(set([x[0] for x in g_pos])), key=natural_sort_key))
            res = []
            for _, r, c in [x for x in g_pos if x[0] == sel_g]:
                for i in range(1, 10):
                    if r+i < len(df_c):
                        row = df_c.iloc[r+i]
                        if "Giornata" in str(row[c]): break
                        h, a = str(row[c]).strip(), str(row[c+3]).strip()
                        if not h or h == "nan": continue
                        try:
                            sh, sa = str(row[c+1]).replace(',','.'), str(row[c+2]).replace(',','.')
                            if float(sh) == 0 and float(sa) == 0:
                                cap_h = df_
