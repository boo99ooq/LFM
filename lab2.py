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
    try:
        if num == int(num): return str(int(num))
        return str(round(num, 1))
    except: return str(num)

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
    leghe_pulite = st.session_state.df_leghe_full.copy()
    leghe_pulite['Squadra_Key'] = leghe_pulite['Squadra'].str.strip().str.upper()
    df_base['Squadra_Key'] = df_base['Squadra_LFM'].str.strip().str.upper()
    if 'Lega' in df_base.columns: df_base = df_base.drop(columns=['Lega', 'Crediti'], errors='ignore')
    df_base = pd.merge(df_base, leghe_pulite.drop(columns=['Squadra']), on='Squadra_Key', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    menu = st.sidebar.radio("Navigazione:", ["🏠 Dashboard", "🗓️ Calendari Campionati", "🏆 Coppe e Preliminari", "📊 Ranking FVM", "💰 Ranking Finanziario", "📋 Rose Complete", "🟢 Giocatori Liberi", "📈 Statistiche Leghe", "⚙️ Gestione Squadre"])

    # --- 🏠 DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Dashboard Riepilogo")
        leghe_eff = [l for l in ORDINE_LEGHE if l in df_base['Lega'].dropna().unique()]
        cols = st.columns(2)
        for i, lega_nome in enumerate(leghe_eff):
            with cols[i % 2]:
                df_l = df_base[df_base['Lega'] == lega_nome]
                
                # Calcolo stats e liste giocatori svincolati/tagliati
                df_attivi = df_l[~(df_l['Rimborsato_Star']) & ~(df_l['Rimborsato_Taglio'])]
                att_stats = df_attivi.groupby('Squadra_LFM').agg({'Nome': 'count', 'FVM': 'sum', 'Qt.I': 'sum'}).rename(columns={'Nome': 'NG', 'FVM': 'FVM_Tot', 'Qt.I': 'Quot_Tot'}).reset_index()
                
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum', 'Nome': lambda x: ", ".join(x)}).reset_index()
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum', 'Nome': lambda x: ", ".join(x)}).reset_index()
                
                tabella = pd.merge(df_l[['Squadra_LFM', 'Crediti']].drop_duplicates(), res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli.rename(columns={'Nome':'N_T'}), on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, att_stats, on='Squadra_LFM', how='left').fillna(0)
                tabella['Totale_Cr'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                
                st.markdown(f"### 🏆 {lega_nome}")
                for _, sq in tabella.sort_values(by='Squadra_LFM').iterrows():
                    cap = df_stadi[df_stadi['Squadra'].str.strip().str.upper() == sq['Squadra_LFM'].strip().upper()]['Stadio'].values
                    cap_txt = f"{int(cap[0])}k" if len(cap)>0 and cap[0] > 0 else "N.D."
                    color_ng = "#ff4b4b" if sq['NG'] < 25 or sq['NG'] > 35 else "#00ff00"
                    
                    # Preparazione testi svincolati/tagliati
                    txt_svinc = f"✈️ {sq['Nome']}" if sq['Nome'] != 0 else ""
                    txt_tagli = f"✂️ {sq['N_T']}" if sq['N_T'] != 0 else ""
                    
                    st.markdown(f"""<div style="background-color: {MAPPATURA_COLORI.get(lega_nome)}; padding: 15px; border-radius: 10px; margin-bottom: 12px; color: white; border: 1px solid rgba(255,255,255,0.1);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                            <b style="font-size: 18px;">{sq['Squadra_LFM']}</b> 
                            <span style="font-size:12px; background: rgba(0,0,0,0.2); padding: 2px 6px; border-radius: 4px;">🏟️ {cap_txt}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: baseline;">
                            <div style="font-size:22px; font-weight:bold;">{format_num(sq['Totale_Cr'])} <small style="font-size:12px;">cr residui</small></div>
                            <div style="font-size:14px; font-weight:bold; color: {color_ng};">({int(sq['NG'])} gioc.)</div>
                        </div>
                        <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.2); display: flex; justify-content: space-between; font-size:11px; opacity:0.9;">
                            <span>📊 FVM: <b>{format_num(sq['FVM_Tot'])}</b></span>
                            <span>💰 Quot: <b>{format_num(sq['Quot_Tot'])}</b></span>
                        </div>
                        <div style="margin-top: 10px; padding: 8px; background: rgba(0,0,0,0.15); border-radius: 6px; font-size: 13px; line-height: 1.4;">
                            <div style="color: #ffeb3b; font-weight: 500;">{txt_svinc}</div>
                            <div style="color: #ffffff; font-weight: 400; opacity: 0.85;">{txt_tagli}</div>
                        </div>
                    </div>""", unsafe_allow_html=True)

    # --- RESTANTI SEZIONI (Calendari, Coppe, Ranking, ecc.) ---
    # [Mantieni il codice precedente per Calendari, Coppe e Ranking]
