import streamlit as st
import pandas as pd
import os
import re

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="LFM Dashboard - Pro Edition", layout="wide", page_icon="⚽")

# Costanti per ordinamento
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

# --- FUNZIONI DI CARICAMENTO DATI ---
@st.cache_data(ttl=600)
def load_lfm_data():
    def read_safe(f):
        if not os.path.exists(f): 
            return pd.DataFrame()
        try:
            df = pd.read_csv(f, sep=',', encoding='utf-8')
        except:
            df = pd.read_csv(f, sep=',', encoding='latin1')
        
        # Pulizia nomi colonne da spazi bianchi invisibili
        df.columns = [c.strip() for c in df.columns]
        return df

    # Caricamento file principali
    df_quot = read_safe('quot.csv')
    df_leghe = read_safe('leghe.csv')
    df_rosters = read_safe('fantamanager-2021-rosters.csv')
    df_base = read_safe('database_lfm.csv')

    # Verifica minima per far girare l'app
    if df_quot.empty or df_rosters.empty:
        return None, None, None

    # --- NORMALIZZAZIONE ID ---
    # Convertiamo tutti gli ID in numeri interi per un merge perfetto
    for d in [df_quot, df_rosters, df_base]:
        if not d.empty and 'Id' in d.columns:
            d['Id'] = pd.to_numeric(d['Id'], errors='coerce').fillna(0).astype(int)

    # --- UNIONE DEI DATI (IL CUORE) ---
    # 1. Partiamo dai Roster (Squadra LFM <-> Id Giocatore)
    # 2. Uniamo con le Quotazioni (Nome, Ruolo, FVM)
    full_df = pd.merge(df_rosters, df_quot, on='Id', how='inner')

    # 3. Uniamo con le Leghe per sapere la competizione di ogni squadra
    if not df_leghe.empty:
        # Pulizia nomi squadre per evitare errori di battitura
        df_leghe['Squadra'] = df_leghe['Squadra'].str.strip()
        full_df['Squadra_LFM'] = full_df['Squadra_LFM'].str.strip()
        
        full_df = pd.merge(
            full_df, 
            df_leghe[['Squadra', 'Lega']], 
            left_on='Squadra_LFM', 
            right_on='Squadra', 
            how='left'
        )

    # 4. Integrazione dati rimborsi (se presenti)
    if not df_base.empty and 'Rimborsato' in df_base.columns:
        full_df = pd.merge(full_df, df_base[['Id', 'Rimborsato']], on='Id', how='left')
        full_df['Rimborsato'] = full_df['Rimborsato'].fillna(False)

    # Riempimento valori di sicurezza
    full_df['Lega'] = full_df['Lega'].fillna('Da Assegnare')
    
    return full_df, df_quot, df_leghe

# --- INTERFACCIA UTENTE ---
def main():
    df, df_quot, df_leghe = load_lfm_data()

    if df is None:
        st.error("❌ Errore critico: File 'quot.csv' o 'fantamanager-2021-rosters.csv' mancanti.")
        st.info("Assicurati che i file CSV siano nella stessa cartella dello script su GitHub.")
        return

    # Sidebar
    st.sidebar.title("🏆 LFM Manager")
    menu = st.sidebar.radio("Menu Navigazione", ["🏠 Dashboard", "📋 Rose Leghe", "📈 Ranking FVM", "🟢 Mercato"])

    if menu == "🏠 Dashboard":
        st.title("⚽ LFM Global Dashboard")
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("Giocatori in Rosa", len(df))
        c2.metric("Squadre Totali", df['Squadra_LFM'].nunique())
        c3.metric("FVM Totale Lega", f"{int(df['FVM'].sum())} mln")

    elif menu == "📋 Rose Leghe":
        st.title("📋 Rose per Competizione")
        leghe_disponibili = sorted(df['Lega'].unique())
        lega_sel = st.selectbox("Seleziona la Lega:", leghe_disponibili)
        
        df_l = df[df['Lega'] == lega_sel]
        squadre = sorted(df_l['Squadra_LFM'].unique())
        
        for s in squadre:
            with st.expander(f"🛡️ {s.upper()}"):
                rosa = df_l[df_l['Squadra_LFM'] == s].sort_values(
                    'R', key=lambda x: x.map(ORDINE_RUOLI)
                )
                # Visualizzazione tabella pulita
                st.table(rosa[['R', 'Nome', 'Squadra', 'FVM']])

    elif menu == "📈 Ranking FVM":
        st.title("📈 Valore Rose (Ranking FVM)")
        ranking = df.groupby('Squadra_LFM')['FVM'].sum().sort_values(ascending=False).reset_index()
        st.bar_chart(ranking.set_index('Squadra_LFM'))
        st.dataframe(ranking, use_container_width=True, hide_index=True)

    elif menu == "🟢 Mercato":
        st.title("🟢 Giocatori Svincolati")
        ids_occupati = set(df['Id'])
        liberi = df_quot[~df_quot['Id'].isin(ids_occupati)].sort_values('FVM', ascending=False)
        st.write("Top 100 giocatori liberi per valore FVM:")
        st.dataframe(liberi.head(100), use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
