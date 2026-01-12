import streamlit as st
import pandas as pd
import math
import os
import re

# --- CONFIGURAZIONE ORIGINALE ---
st.set_page_config(page_title="LFM Dashboard - Golden Edition", layout="wide", page_icon="⚖️")

ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

# --- FUNZIONI UTILITY ORIGINALI ---
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def calculate_stadium_bonus(capienza):
    casa = capienza / 20
    trasferta = math.floor((casa / 2) * 2) / 2
    return casa, trasferta

# --- CARICAMENTO DATI (CON PROTEZIONE ENCODING) ---
@st.cache_data(ttl=600)
def load_all_data():
    def read_safe(f):
        if not os.path.exists(f): return pd.DataFrame()
        try: return pd.read_csv(f, sep=',', encoding='utf-8')
        except: return pd.read_csv(f, sep=',', encoding='latin1')

    df_quot = read_safe('quot.csv')
    df_leghe = read_safe('leghe.csv')
    df_rosters = read_safe('fantamanager-2021-rosters.csv')
    df_stadi = read_safe('stadi.csv')
    df_base = read_safe('database_lfm.csv')

    if df_quot.empty or df_rosters.empty: return None, None, None, None, None

    # Pulizia colonne e ID
    for d in [df_quot, df_rosters, df_leghe]:
        if not d.empty:
            d.columns = [c.strip() for c in d.columns]
            if 'Id' in d.columns:
                d['Id'] = pd.to_numeric(d['Id'], errors='coerce').fillna(0).astype(int)

    # Merge Rose
    df_rose = pd.merge(df_rosters, df_quot, on='Id', how='inner')
    if not df_leghe.empty:
        df_rose = pd.merge(df_rose, df_leghe[['Squadra', 'Lega']], left_on='Squadra_LFM', right_on='Squadra', how='left')
    
    df_rose['Lega'] = df_rose['Lega'].fillna('Serie A')
    return df_rose, df_quot, df_leghe, df_stadi, df_base

# --- MAIN ---
def main():
    df_all, df_all_quot, df_leghe_full, df_stadi, df_base = load_all_data()
    if df_all is None:
        st.error("Dati non trovati. Controlla i file CSV.")
        return

    st.sidebar.title("🏆 LFM Manager")
    menu = st.sidebar.radio("Navigazione", ["📊 Dashboard", "📋 Rose Complete", "📈 Ranking FVM", "🏟️ Bonus Stadi", "🟢 Giocatori Liberi"])

    if menu == "📊 Dashboard":
        # ... (Logica dashboard colorata che avevi già)
        st.title("⚽ Dashboard")
        for lega in ORDINE_LEGHE:
            color = MAPPATURA_COLORI.get(lega, "#333")
            st.markdown(f'<div style="background-color:{color}; padding:10px; border-radius:10px; margin-top:20px;"><h2 style="color:white; text-align:center;">{lega.upper()}</h2></div>', unsafe_allow_html=True)
            df_l = df_all[df_all['Lega'] == lega]
            sqs = sorted(df_l['Squadra_LFM'].unique())
            cols = st.columns(len(sqs)) if sqs else [st.container()]
            for i, s in enumerate(sqs):
                with cols[i]:
                    val = int(df_l[df_l['Squadra_LFM'] == s]['FVM'].sum())
                    st.metric(s, f"{val} mln")

    elif menu == "🏟️ Bonus Stadi":
        st.title("🏟️ Bonus Stadio & Calendari")
        
        # Logica Calendari (RIPRISTINATA)
        files_cal = [f for f in os.listdir('.') if 'Calendario' in f and f.endswith('.csv')]
        if files_cal:
            sel_cal = st.selectbox("Seleziona il Calendario della competizione:", files_cal)
            try:
                df_c = pd.read_csv(sel_cal, sep=',', encoding='latin1') # Uso latin1 per evitare errori
                giornate = [c for c in df_c.columns if 'G.' in c]
                g_sel = st.selectbox("Seleziona la Giornata:", giornate)
                
                st.subheader(f"Dettaglio {g_sel}")
                st.dataframe(df_c[['CASA', 'FUORI', g_sel]], use_container_width=True)
                
                # Qui l'app originale cercava i bonus...
            except Exception as e:
                st.error(f"Errore nella lettura del calendario: {e}")
        else:
            st.warning("Nessun file 'Calendario_*.csv' trovato.")

    # ... (Altre sezioni Ranking, Rose, Mercato)
