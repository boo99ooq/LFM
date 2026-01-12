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

def format_num(num):
    if num == int(num): return str(int(num))
    return str(round(num, 1))

# --- CARICAMENTO DATI (LOGICA ORIGINALE ADATTATA) ---
@st.cache_data(ttl=600)
def load_all_data():
    def read_safe(f):
        if not os.path.exists(f): return pd.DataFrame()
        try: return pd.read_csv(f, sep=',', encoding='utf-8')
        except: return pd.read_csv(f, sep=',', encoding='latin1')

    # File caricati
    df_base = read_safe('database_lfm.csv')
    df_all_quot = read_safe('quot.csv')
    df_leghe_full = read_safe('leghe.csv')
    df_stadi = read_safe('stadi.csv')
    df_rosters = read_safe('fantamanager-2021-rosters.csv')

    # Pulizia ID e Colonne
    for d in [df_base, df_all_quot, df_leghe_full, df_rosters]:
        if not d.empty:
            d.columns = [c.strip() for c in d.columns]
            if 'Id' in d.columns:
                d['Id'] = pd.to_numeric(d['Id'], errors='coerce').fillna(0).astype(int)

    # Costruzione database rose (Merge fondamentale)
    if not df_rosters.empty and not df_all_quot.empty:
        df_rose = pd.merge(df_rosters, df_all_quot, on='Id', how='inner')
        if not df_leghe_full.empty:
            df_leghe_full['Squadra'] = df_leghe_full['Squadra'].str.strip()
            df_rose = pd.merge(df_rose, df_leghe_full[['Squadra', 'Lega']], 
                               left_on='Squadra_LFM', right_on='Squadra', how='left')
        df_rose['Lega'] = df_rose['Lega'].fillna('Serie A')
        return df_rose, df_all_quot, df_leghe_full, df_stadi, df_base
    
    return None, None, None, None, None

# --- LOGICA APP ---
def main():
    df_all, df_all_quot, df_leghe_full, df_stadi, df_base = load_all_data()

    if df_all is None:
        st.error("⚠️ Errore caricamento. Verifica i file CSV (quot.csv, fantamanager-2021-rosters.csv).")
        return

    # Inizializzazione Session State Originale
    if 'df_leghe_full' not in st.session_state:
        st.session_state.df_leghe_full = df_leghe_full
    if 'refunded_ids' not in st.session_state:
        st.session_state.refunded_ids = set(df_base['Id']) if not df_base.empty else set()

    # Navigazione Sidebar Originale
    st.sidebar.title("🏆 LFM Manager")
    menu = st.sidebar.radio("Navigazione", 
        ["📊 Dashboard", "📋 Rose Complete", "📈 Ranking FVM", "🏟️ Bonus Stadi", "🟢 Giocatori Liberi", "⚙️ Gestione Squadre"])

    # 1. DASHBOARD (LOGICA ORIGINALE DELLE COLONNE)
    if menu == "📊 Dashboard":
        st.title("⚽ LFM Global Dashboard")
        for lega in ORDINE_LEGHE:
            color = MAPPATURA_COLORI.get(lega, "#333")
            st.markdown(f'<div style="background-color:{color}; padding:10px; border-radius:10px; margin:20px 0 10px 0;"><h2 style="color:white; margin:0; text-align:center;">{lega.upper()}</h2></div>', unsafe_allow_html=True)
            
            df_lega = df_all[df_all['Lega'] == lega]
            squadre = sorted(df_lega['Squadra_LFM'].unique())
            
            if squadre:
                cols = st.columns(len(squadre))
                for i, sq in enumerate(squadre):
                    with cols[i]:
                        df_sq = df_lega[df_lega['Squadra_LFM'] == sq]
                        fvm_tot = int(df_sq['FVM'].sum())
                        st.metric(label=sq, value=f"{fvm_tot} mln", delta=f"{len(df_sq)} G")
            else: st.info(f"Nessuna squadra in {lega}")

    # 2. ROSE (TABELLE ORIGINALI)
    elif menu == "📋 Rose Complete":
        st.title("📋 Rose Complete")
        lega_sel = st.selectbox("Seleziona Lega", ORDINE_LEGHE)
        df_l = df_all[df_all['Lega'] == lega_sel]
        for s in sorted(df_l['Squadra_LFM'].unique(), key=natural_sort_key):
            with st.expander(f"🛡️ {s}"):
                rosa = df_l[df_l['Squadra_LFM'] == s].sort_values('R', key=lambda x: x.map(ORDINE_RUOLI))
                st.table(rosa[['R', 'Nome', 'Squadra', 'FVM']])

    # 3. RANKING (GRAFICO ORIGINALE)
    elif menu == "📈 Ranking FVM":
        st.title("📈 Valore Rose")
        rank = df_all.groupby('Squadra_LFM')['FVM'].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(rank.set_index('Squadra_LFM'))
        st.dataframe(rank, use_container_width=True, hide_index=True)

    # 4. BONUS STADI E CALENDARI (VERSIONE CORRETTA)
    elif menu == "🏟️ Bonus Stadi":
        st.title("🏟️ Bonus Stadio & Calendari")
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.subheader("🏟️ Database Stadi")
            if not df_stadi.empty:
                st.dataframe(df_stadi, use_container_width=True, hide_index=True)
            else:
                st.warning("File stadi.csv non trovato.")
        
        with c2:
            st.subheader("🗓️ Analisi Calendari")
            # Cerchiamo i file dei calendari
            file_cal = [f for f in os.listdir('.') if 'Calendario' in f and f.endswith('.csv')]
            
            if not file_cal:
                st.info("Nessun file 'Calendario_*.csv' trovato nella cartella.")
            else:
                sel_cal = st.selectbox("Seleziona Calendario", file_cal)
                
                if sel_cal:
                    try:
                        # TENTATIVO 1: UTF-8
                        df_c = pd.read_csv(sel_cal, sep=',')
                    except UnicodeDecodeError:
                        # TENTATIVO 2: Latin-1 (Risolve l'errore che hai ricevuto)
                        df_c = pd.read_csv(sel_cal, sep=',', encoding='latin1')
                    except Exception as e:
                        st.error(f"Errore nella lettura del calendario: {e}")
                        df_c = pd.DataFrame()

                    if not df_c.empty:
                        st.dataframe(df_c, use_container_width=True, hide_index=True)
    # 5. GIOCATORI LIBERI (LOGICA ORIGINALE)
    elif menu == "🟢 Giocatori Liberi":
        st.title("🟢 Mercato Svincolati")
        ids_occ = set(df_all['Id'])
        liberi = df_all_quot[~df_all_quot['Id'].isin(ids_occ)].sort_values('FVM', ascending=False)
        st.dataframe(liberi[['R', 'Nome', 'Squadra', 'FVM']].head(100), use_container_width=True)

    # 6. GESTIONE (DOWNLOAD E EDIT ORIGINALE)
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione")
        st.session_state.df_leghe_full = st.data_editor(st.session_state.df_leghe_full, use_container_width=True)
        st.divider()
        st.download_button("Scarica Database Aggiornato", df_all.to_csv(index=False), "database_completo.csv")

if __name__ == "__main__":
    main()
