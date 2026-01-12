import streamlit as st
import pandas as pd
import math
import os
import re

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="LFM Dashboard - Golden Edition", layout="wide", page_icon="⚖️")

# --- COSTANTI ORIGINALI ---
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

# --- FUNZIONI UTILITY ---
def calculate_stadium_bonus(capienza):
    casa = capienza / 20
    trasferta = math.floor((casa / 2) * 2) / 2
    return casa, trasferta

@st.cache_data(ttl=600)
def load_all_lfm_data():
    def read_safe(f):
        if not os.path.exists(f): return pd.DataFrame()
        try: return pd.read_csv(f, sep=',', encoding='utf-8')
        except: return pd.read_csv(f, sep=',', encoding='latin1')

    # Caricamento file
    df_quot = read_safe('quot.csv')
    df_leghe = read_safe('leghe.csv')
    df_rosters = read_safe('fantamanager-2021-rosters.csv')
    df_base = read_safe('database_lfm.csv')
    df_stadi = read_safe('stadi.csv')

    if df_quot.empty or df_rosters.empty:
        return None, None, None, None

    # Pulizia nomi colonne e normalizzazione ID
    for d in [df_quot, df_rosters, df_leghe, df_base]:
        if not d.empty:
            d.columns = [c.strip() for c in d.columns]
            if 'Id' in d.columns:
                d['Id'] = pd.to_numeric(d['Id'], errors='coerce').fillna(0).astype(int)

    # --- COSTRUZIONE DATABASE INTEGRATO ---
    # Uniamo Roster (Squadre-Id) con Quotazioni (Info Giocatori)
    full_df = pd.merge(df_rosters, df_quot, on='Id', how='inner')
    
    # Uniamo con le Leghe (Lega e Crediti)
    if not df_leghe.empty:
        df_leghe['Squadra'] = df_leghe['Squadra'].str.strip()
        full_df['Squadra_LFM'] = full_df['Squadra_LFM'].str.strip()
        full_df = pd.merge(full_df, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')

    # Uniamo con database_lfm per i rimborsi
    if not df_base.empty:
        full_df = pd.merge(full_df, df_base[['Id', 'Rimborsato']], on='Id', how='left')
        full_df['Rimborsato'] = full_df['Rimborsato'].fillna(False)

    full_df['Lega'] = full_df['Lega'].fillna('Serie A')
    return full_df, df_quot, df_leghe, df_stadi

# --- LOGICA DASHBOARD (LE SCHEDE COLORATE) ---
def render_dashboard(df_all):
    st.title("⚽ LFM Global Dashboard")
    
    for lega in ORDINE_LEGHE:
        color = MAPPATURA_COLORI.get(lega, "#333")
        st.markdown(f"""
            <div style="background-color:{color}; padding:10px; border-radius:10px; margin-bottom:10px;">
                <h2 style="color:white; margin:0;">{lega.upper()}</h2>
            </div>
        """, unsafe_allow_value=True)
        
        df_lega = df_all[df_all['Lega'] == lega]
        squadre = sorted(df_lega['Squadra_LFM'].unique())
        
        cols = st.columns(len(squadre) if squadre else 1)
        for i, sq in enumerate(squadre):
            with cols[i]:
                df_sq = df_lega[df_lega['Squadra_LFM'] == sq]
                fvm_tot = int(df_sq['FVM'].sum())
                st.markdown(f"**{sq}**")
                st.markdown(f"💰 {fvm_tot} mln")
                st.caption(f"🏃 {len(df_sq)} gioc.")

# --- MAIN APP ---
def main():
    df_full, df_quot, df_leghe, df_stadi = load_all_lfm_data()

    if df_full is None:
        st.error("Caricamento fallito. Controlla i nomi dei file CSV.")
        return

    menu = st.sidebar.radio("Navigazione", ["📊 Dashboard", "📋 Rose Complete", "📈 Ranking FVM", "🟢 Mercato", "⚙️ Gestione"])

    if menu == "📊 Dashboard":
        render_dashboard(df_full)

    elif menu == "📋 Rose Complete":
        st.title("📋 Rose per Lega")
        lega_sel = st.selectbox("Seleziona Lega", ORDINE_LEGHE)
        df_l = df_full[df_full['Lega'] == lega_sel]
        squadre = sorted(df_l['Squadra_LFM'].unique())
        for s in squadre:
            with st.expander(f"🛡️ {s}"):
                rosa = df_l[df_l['Squadra_LFM'] == s].sort_values('R', key=lambda x: x.map(ORDINE_RUOLI))
                st.table(rosa[['R', 'Nome', 'Squadra', 'FVM']])

    elif menu == "📈 Ranking FVM":
        st.title("📈 Valore Rose")
        ranking = df_full.groupby('Squadra_LFM')['FVM'].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(ranking.set_index('Squadra_LFM'))
        st.dataframe(ranking, use_container_width=True)

    elif menu == "🟢 Mercato":
        st.title("🟢 Giocatori Svincolati")
        ids_occ = set(df_full['Id'])
        liberi = df_quot[~df_quot['Id'].isin(ids_occ)].sort_values('FVM', ascending=False)
        st.dataframe(liberi.head(100), use_container_width=True)

    elif menu == "⚙️ Gestione":
        st.title("⚙️ Gestione Squadre & Crediti")
        st.data_editor(df_leghe, use_container_width=True)

if __name__ == "__main__":
    main()
