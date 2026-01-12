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

# --- CARICAMENTO DATI (VERSIONE CORRETTA PER I NUOVI FILE) ---
@st.cache_data(ttl=600)
def load_all_data():
    def read_safe(f, has_header=True):
        if not os.path.exists(f): return pd.DataFrame()
        try: return pd.read_csv(f, sep=',', encoding='utf-8', header=0 if has_header else None)
        except: return pd.read_csv(f, sep=',', encoding='latin1', header=0 if has_header else None)

    # Caricamento file con i tuoi nomi reali
    df_quot = read_safe('quot.csv')
    df_leghe = read_safe('leghe.csv')
    df_rosters = read_safe('fantamanager-2021-rosters.csv') # Con header: Squadra_LFM,Id,Prezzo
    df_stadi = read_safe('stadi.csv')
    df_base = read_safe('database_lfm.csv')

    if df_quot.empty or df_rosters.empty:
        return None, None, None, None, None

    # Pulizia colonne e standardizzazione ID
    for d in [df_quot, df_rosters, df_leghe, df_base]:
        if not d.empty:
            d.columns = [c.strip() for c in d.columns]
            if 'Id' in d.columns:
                d['Id'] = pd.to_numeric(d['Id'], errors='coerce').fillna(0).astype(int)

    # Ricostruzione rose: Uniamo Roster (Squadre) + Quotazioni (Giocatori)
    df_rose = pd.merge(df_rosters, df_quot, on='Id', how='inner')
    
    # Aggiungiamo la Lega da leghe.csv
    if not df_leghe.empty:
        df_leghe['Squadra'] = df_leghe['Squadra'].str.strip()
        df_rose = pd.merge(df_rose, df_leghe[['Squadra', 'Lega']], 
                           left_on='Squadra_LFM', right_on='Squadra', how='left')
    
    df_rose['Lega'] = df_rose['Lega'].fillna('Serie A')
    return df_rose, df_quot, df_leghe, df_stadi, df_base

# --- LOGICA APP ---
def main():
    data = load_all_data()
    if data[0] is None:
        st.error("⚠️ Errore critico: Assicurati che i file 'quot.csv' e 'fantamanager-2021-rosters.csv' siano presenti.")
        return

    df_all, df_all_quot, df_leghe_full, df_stadi, df_base = data

    # Inizializzazione Session State (Previene la pagina bianca)
    if 'df_leghe_full' not in st.session_state:
        st.session_state.df_leghe_full = df_leghe_full
    if 'refunded_ids' not in st.session_state:
        st.session_state.refunded_ids = set(df_base['Id']) if not df_base.empty else set()

    # Sidebar Navigazione
    st.sidebar.title("🏆 LFM Manager")
    menu = st.sidebar.radio("Navigazione", 
        ["📊 Dashboard", "📋 Rose Complete", "📈 Ranking FVM", "🏟️ Bonus Stadi", "🟢 Giocatori Liberi", "⚙️ Gestione Squadre"])

    # 1. DASHBOARD ORIGINALE
    if menu == "📊 Dashboard":
        st.title("⚽ LFM Global Dashboard")
        for lega in ORDINE_LEGHE:
            color = MAPPATURA_COLORI.get(lega, "#333")
            st.markdown(f'<div style="background-color:{color}; padding:10px; border-radius:10px; margin:20px 0 10px 0;"><h2 style="color:white; margin:0; text-align:center;">{lega.upper()}</h2></div>', unsafe_allow_html=True)
            df_l = df_all[df_all['Lega'] == lega]
            sqs = sorted(df_l['Squadra_LFM'].unique())
            if sqs:
                cols = st.columns(len(sqs))
                for i, s in enumerate(sqs):
                    with cols[i]:
                        fvm_tot = int(df_l[df_l['Squadra_LFM'] == s]['FVM'].sum())
                        st.metric(label=s, value=f"{fvm_tot} mln", delta=f"{len(df_l[df_l['Squadra_LFM'] == s])} G")

    # 2. ROSE ORIGINALI
    elif menu == "📋 Rose Complete":
        st.title("📋 Rose Complete")
        lega_sel = st.selectbox("Seleziona Lega", ORDINE_LEGHE)
        df_l = df_all[df_all['Lega'] == lega_sel]
        for s in sorted(df_l['Squadra_LFM'].unique(), key=natural_sort_key):
            with st.expander(f"🛡️ {s}"):
                rosa = df_l[df_l['Squadra_LFM'] == s].sort_values('R', key=lambda x: x.map(ORDINE_RUOLI))
                st.table(rosa[['R', 'Nome', 'Squadra', 'FVM']])

    # 3. RANKING ORIGINALE
    elif menu == "📈 Ranking FVM":
        st.title("📈 Valore Rose")
        rank = df_all.groupby('Squadra_LFM')['FVM'].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(rank.set_index('Squadra_LFM'))
        st.dataframe(rank, use_container_width=True, hide_index=True)

    # 4. BONUS STADI & CALENDARI (RIPRISTINATO ORIGINALE)
    elif menu == "🏟️ Bonus Stadi":
        st.title("🏟️ Bonus Stadio & Calendari")
        files_cal = [f for f in os.listdir('.') if 'Calendario' in f and f.endswith('.csv')]
        if files_cal:
            sel_cal = st.selectbox("Seleziona Calendario", files_cal)
            try:
                df_c = pd.read_csv(sel_cal, sep=',', encoding='latin1')
                giornate = [c for c in df_c.columns if 'G.' in c]
                g_sel = st.selectbox("Seleziona Giornata", giornate)
                
                # Logica visualizzazione giornata
                st.subheader(f"Dettaglio {g_sel}")
                st.dataframe(df_c[['CASA', 'FUORI', g_sel]], use_container_width=True, hide_index=True)
                
                # Qui puoi reinserire i calcoli automatici dello stadio
            except Exception as e:
                st.error(f"Errore: {e}")
        else:
            st.warning("Nessun calendario trovato.")

    # 5. GIOCATORI LIBERI
    elif menu == "🟢 Giocatori Liberi":
        st.title("🟢 Mercato Liberi")
        ids_occ = set(df_all['Id'])
        lib = df_all_quot[~df_all_quot['Id'].isin(ids_occ)].sort_values('FVM', ascending=False)
        st.dataframe(lib[['R', 'Nome', 'Squadra', 'FVM']].head(100), use_container_width=True)

    # 6. GESTIONE
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Gestione")
        st.session_state.df_leghe_full = st.data_editor(st.session_state.df_leghe_full, use_container_width=True)

if __name__ == "__main__":
    main()
