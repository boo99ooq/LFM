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

# --- CARICAMENTO DATI (CORRETTO PER I TUOI FILE) ---
@st.cache_data(ttl=600)
def load_all_data():
    def read_safe(f):
        if not os.path.exists(f): return pd.DataFrame()
        try: return pd.read_csv(f, sep=',', encoding='utf-8')
        except: return pd.read_csv(f, sep=',', encoding='latin1')

    # Caricamento dei tuoi file reali
    df_base = read_safe('database_lfm.csv') # File rimborsi
    df_quot = read_safe('quot.csv')         # Quotazioni
    df_leghe = read_safe('leghe.csv')       # Leghe/Crediti
    df_stadi = read_safe('stadi.csv')       # Stadi
    df_rosters = read_safe('fantamanager-2021-rosters.csv') # Associazioni Squadre-Id

    # Pulizia colonne e ID
    for d in [df_base, df_quot, df_leghe, df_rosters]:
        if not d.empty:
            d.columns = [c.strip() for c in d.columns]
            if 'Id' in d.columns:
                d['Id'] = pd.to_numeric(d['Id'], errors='coerce').fillna(0).astype(int)

    # RICOSTRUZIONE DATABASE (Logica originale ripristinata)
    if not df_rosters.empty and not df_quot.empty:
        # Uniamo i roster con le info dei giocatori
        df_all = pd.merge(df_rosters, df_quot, on='Id', how='inner')
        
        # Uniamo con le leghe per avere il campo 'Lega'
        if not df_leghe.empty:
            df_leghe['Squadra'] = df_leghe['Squadra'].str.strip()
            df_all = pd.merge(df_all, df_leghe[['Squadra', 'Lega']], 
                              left_on='Squadra_LFM', right_on='Squadra', how='left')
        
        df_all['Lega'] = df_all['Lega'].fillna('Serie A')
        return df_all, df_quot, df_leghe, df_stadi, df_base
    
    return None, None, None, None, None

# --- LOGICA APP ---
def main():
    df_all, df_all_quot, df_leghe_full, df_stadi, df_base = load_all_data()

    if df_all is None:
        st.error("⚠️ Errore nel caricamento dei dati. Controlla i file CSV.")
        return

    # Inizializzazione Session State (Fondamentale nel tuo codice originale)
    if 'df_leghe_full' not in st.session_state:
        st.session_state.df_leghe_full = df_leghe_full

    # SIDEBAR ORIGINALE
    st.sidebar.title("🏆 LFM Manager")
    menu = st.sidebar.radio("Navigazione", 
        ["📊 Dashboard", "📋 Rose Complete", "📈 Ranking FVM", "🏟️ Bonus Stadi", "🟢 Giocatori Liberi", "⚙️ Gestione Squadre"])

    # 1. DASHBOARD ORIGINALE (Con i colori e le colonne)
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
                        st.metric(label=sq, value=f"{fvm_tot} mln", delta=f"{len(df_sq)} Gioc.")
            else: st.info(f"Nessun dato per {lega}")

    # 2. ROSE COMPLETE (Visualizzazione Tabella Originale)
    elif menu == "📋 Rose Complete":
        st.title("📋 Rose Complete")
        lega_sel = st.selectbox("Seleziona Lega", ORDINE_LEGHE)
        df_l = df_all[df_all['Lega'] == lega_sel]
        for s in sorted(df_l['Squadra_LFM'].unique()):
            with st.expander(f"🛡️ {s}"):
                rosa = df_l[df_l['Squadra_LFM'] == s].sort_values('R', key=lambda x: x.map(ORDINE_RUOLI))
                st.table(rosa[['R', 'Nome', 'Squadra', 'FVM']])

    # 3. RANKING FVM (Grafico Originale)
    elif menu == "📈 Ranking FVM":
        st.title("📈 Valore Rose (Ranking FVM)")
        ranking = df_all.groupby('Squadra_LFM')['FVM'].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(ranking.set_index('Squadra_LFM'))
        st.dataframe(ranking, use_container_width=True, hide_index=True)

    # 4. BONUS STADI (Logica originale dei calendari)
    elif menu == "🏟️ Bonus Stadi":
        st.title("🏟️ Bonus Stadio & Calendari")
        if df_stadi.empty: st.warning("File stadi.csv non trovato.")
        else: st.dataframe(df_stadi, use_container_width=True, hide_index=True)

    # 5. GIOCATORI LIBERI
    elif menu == "🟢 Giocatori Liberi":
        st.title("🟢 Calciatori Liberi")
        ids_occ = set(df_all['Id'])
        df_lib = df_all_quot[~df_all_quot['Id'].isin(ids_occ)].sort_values('FVM', ascending=False)
        st.dataframe(df_lib[['R', 'Nome', 'Squadra', 'FVM']].head(100), use_container_width=True, hide_index=True)

    # 6. GESTIONE SQUADRE (Il data editor originale)
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione & Crediti")
        st.session_state.df_leghe_full = st.data_editor(st.session_state.df_leghe_full, use_container_width=True)

if __name__ == "__main__":
    main()
