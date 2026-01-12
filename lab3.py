import streamlit as st
import pandas as pd
import os
import re

# --- CONFIGURAZIONE E COSTANTI ---
st.set_page_config(page_title="LFM Dashboard - Pro Edition", layout="wide", page_icon="⚽")

ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
COLORI_LEGHE = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}

# --- 1. MOTORE DI CARICAMENTO DATI (CACHE) ---
@st.cache_data(ttl=3600)
def load_all_data():
    """Carica, pulisce e unisce tutti i database in un unico punto."""
    try:
        # Caricamento file base con gestione encoding
        def read_csv_safe(file):
            if not os.path.exists(file): return pd.DataFrame()
            try: return pd.read_csv(file, sep=',', encoding='utf-8')
            except: return pd.read_csv(file, sep=',', encoding='latin1')

        df_base = read_csv_safe('database_lfm.csv')
        df_quot = read_csv_safe('Quotazioni_FVM.csv')
        df_stadi = read_csv_safe('stadi.csv')
        
        if df_base.empty or df_quot.empty:
            return None, None, None

        # Pulizia e Merge
        df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
        df_base['Id'] = pd.to_numeric(df_base['Id'], errors='coerce')
        
        # Unione dati: Rose + Quotazioni
        full_df = pd.merge(df_base, df_quot, on='Id', how='left', suffixes=('', '_q'))
        
        # Pulizia Nomi Leghe
        full_df['Lega'] = full_df['Lega'].fillna('Serie A').replace(['nan', 'Lega A'], 'Serie A')
        
        return full_df, df_quot, df_stadi
    except Exception as e:
        st.error(f"Errore critico nel caricamento dati: {e}")
        return None, None, None

# --- 2. LOGICA CALCOLO STADI (Migliorata) ---
def get_stadium_bonus(df_cal, df_stadi, squadra_nome):
    """Trova il bonus stadio cercando dinamicamente nel calendario."""
    try:
        # Esempio di logica più robusta: cerca la squadra nella colonna 'Casa'
        # Invece di iloc fissi, usiamo filtri sui nomi
        info_stadio = df_stadi[df_stadi['Squadra'].str.upper() == squadra_nome.upper()]
        if not info_stadio.empty:
            capienza = info_stadio.iloc[0]['Capienza']
            casa = capienza / 20
            return casa, (casa / 2)
        return 0, 0
    except:
        return 0, 0

# --- 3. COMPONENTI INTERFACCIA ---

def render_dashboard(df):
    st.header("📊 Overview Leghe")
    cols = st.columns(4)
    for i, lega in enumerate(ORDINE_LEGHE):
        with cols[i]:
            count = len(df[df['Lega'] == lega])
            st.metric(label=lega, value=count)
            # Qui puoi aggiungere un grafico sparkline o mini-classifica

def render_mercato(df_all_quot, df_base):
    st.header("🟢 Giocatori Liberi (Top FVM)")
    # Identifica ID già presi
    presi = set(df_base['Id'].dropna())
    liberi = df_all_quot[~df_all_quot['Id'].isin(presi)].sort_values('FVM', ascending=False)
    
    st.dataframe(
        liberi[['Nome', 'R', 'Squadra', 'FVM', 'Qt.A']].head(50),
        use_container_width=True,
        hide_index=True
    )

def render_rose(df):
    st.header("📋 Rose Complete")
    lega_sel = st.selectbox("Seleziona Lega", ORDINE_LEGHE)
    df_l = df[df['Lega'] == lega_sel]
    
    # Raggruppamento per Squadra LFM
    squadre = sorted(df_l['Squadra_LFM'].unique())
    for sq in squadre:
        with st.expander(f"🛡️ {sq}"):
            rosa_sq = df_l[df_l['Squadra_LFM'] == sq].sort_values('R', key=lambda x: x.map({'P':0,'D':1,'C':2,'A':3}))
            st.table(rosa_sq[['R', 'Nome', 'Squadra', 'FVM']])

# --- 4. MAIN APP ---

def main():
    # Sidebar Navigation
    with st.sidebar:
        st.title("🏆 LFM Manager")
        menu = st.radio("Menu", ["Dashboard", "Rose", "Mercato", "Configurazione"])
        st.divider()
        if st.button("🔄 Forza Refresh Dati"):
            st.cache_data.clear()
            st.rerun()

    # Caricamento Dati
    df_full, df_quot, df_stadi = load_all_data()

    if df_full is None:
        st.warning("⚠️ Database non trovati. Controlla i file CSV.")
        return

    # Routing Pagine
    if menu == "Dashboard":
        render_dashboard(df_full)
    elif menu == "Rose":
        render_rose(df_full)
    elif menu == "Mercato":
        render_mercato(df_quot, df_full)
    elif menu == "Configurazione":
        st.info("Sezione per caricamento nuovi file e backup.")
        # Inserire qui il data_editor per i crediti

if __name__ == "__main__":
    main()
