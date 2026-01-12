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
    def read_safe(f, has_header=True):
        if not os.path.exists(f): return pd.DataFrame()
        try: return pd.read_csv(f, sep=',', encoding='utf-8', header=0 if has_header else None)
        except: return pd.read_csv(f, sep=',', encoding='latin1', header=0 if has_header else None)

    df_quot = read_safe('quot.csv')
    df_leghe = read_safe('leghe.csv')
    df_rosters = read_safe('fantamanager-2021-rosters.csv') # Con l'header aggiunto ora
    df_base = read_safe('database_lfm.csv')
    df_stadi = read_safe('stadi.csv')

    if df_quot.empty or df_rosters.empty:
        return None, None, None, None

    # Pulizia colonne e ID
    for d in [df_quot, df_rosters, df_leghe, df_base]:
        if not d.empty:
            d.columns = [c.strip() for c in d.columns]
            if 'Id' in d.columns:
                d['Id'] = pd.to_numeric(d['Id'], errors='coerce').fillna(0).astype(int)

    # MERGE: Roster + Quotazioni
    full_df = pd.merge(df_rosters, df_quot, on='Id', how='inner')
    
    # MERGE: + Leghe
    if not df_leghe.empty:
        df_leghe['Squadra'] = df_leghe['Squadra'].str.strip()
        full_df['Squadra_LFM'] = full_df['Squadra_LFM'].str.strip()
        full_df = pd.merge(full_df, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')

    full_df['Lega'] = full_df['Lega'].fillna('Serie A')
    return full_df, df_quot, df_leghe, df_stadi

# --- COMPONENTI INTERFACCIA ---

def render_dashboard(df_all):
    st.title("⚽ LFM Global Dashboard")
    for lega in ORDINE_LEGHE:
        color = MAPPATURA_COLORI.get(lega, "#333")
        # CORRETTO: unsafe_allow_html=True
        st.markdown(f"""
            <div style="background-color:{color}; padding:15px; border-radius:10px; margin-top:20px; margin-bottom:10px;">
                <h2 style="color:white; margin:0; text-align:center;">{lega.upper()}</h2>
            </div>
        """, unsafe_allow_html=True)
        
        df_lega = df_all[df_all['Lega'] == lega]
        squadre = sorted(df_lega['Squadra_LFM'].unique())
        
        if squadre:
            cols = st.columns(len(squadre))
            for i, sq in enumerate(squadre):
                with cols[i]:
                    df_sq = df_lega[df_lega['Squadra_LFM'] == sq]
                    fvm_tot = int(df_sq['FVM'].sum())
                    st.metric(label=sq, value=f"{fvm_tot} mln", delta=f"{len(df_sq)} G")
        else:
            st.info(f"Nessuna squadra assegnata a {lega}")

def render_ranking(df):
    st.title("📈 Ranking FVM e Valore Rose")
    col1, col2 = st.columns([2, 1])
    ranking = df.groupby('Squadra_LFM')['FVM'].sum().sort_values(ascending=False).reset_index()
    with col1:
        st.bar_chart(ranking.set_index('Squadra_LFM'))
    with col2:
        st.dataframe(ranking, use_container_width=True, hide_index=True)

# --- MAIN ---
def main():
    df_full, df_quot, df_leghe, df_stadi = load_all_lfm_data()

    if df_full is None:
        st.error("❌ Errore caricamento file. Verifica che 'quot.csv' e 'fantamanager-2021-rosters.csv' siano presenti.")
        return

    # SIDEBAR ORIGINALE
    st.sidebar.image("https://via.placeholder.com/150?text=LFM+LOGO", use_container_width=True) # Metti qui il tuo logo se vuoi
    menu = st.sidebar.radio("Seleziona Sezione", 
                            ["📊 Dashboard", "📋 Rose Complete", "📈 Ranking FVM", "🟢 Mercato", "🏟️ Bonus Stadi", "⚙️ Gestione"])

    if menu == "📊 Dashboard":
        render_dashboard(df_full)

    elif menu == "📋 Rose Complete":
        st.title("📋 Rose Complete")
        lega_sel = st.selectbox("Lega", ORDINE_LEGHE)
        df_l = df_full[df_full['Lega'] == lega_sel]
        squadre = sorted(df_l['Squadra_LFM'].unique())
        for s in squadre:
            with st.expander(f"🛡️ {s}"):
                rosa = df_l[df_l['Squadra_LFM'] == s].sort_values('R', key=lambda x: x.map(ORDINE_RUOLI))
                st.dataframe(rosa[['R', 'Nome', 'Squadra', 'FVM']], use_container_width=True, hide_index=True)

    elif menu == "📈 Ranking FVM":
        render_ranking(df_full)

    elif menu == "🟢 Mercato":
        st.title("🟢 Giocatori Svincolati (Top FVM)")
        ids_occupati = set(df_full['Id'])
        liberi = df_quot[~df_quot['Id'].isin(ids_occupati)].sort_values('FVM', ascending=False)
        st.dataframe(liberi[['R', 'Nome', 'Squadra', 'FVM']].head(100), use_container_width=True)

    elif menu == "🏟️ Bonus Stadi":
        st.title("🏟️ Calcolo Bonus Stadio")
        if not df_stadi.empty:
            st.dataframe(df_stadi, use_container_width=True)
        else:
            st.warning("File stadi.csv non trovato.")

    elif menu == "⚙️ Gestione":
        st.title("⚙️ Configurazione")
        st.write("Dati attuali Leghe e Crediti:")
        st.data_editor(df_leghe, use_container_width=True)

if __name__ == "__main__":
    main()
