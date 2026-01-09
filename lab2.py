import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM LAB 2 - Debug Mode", layout="wide")

# --- 1. FUNZIONE CARICAMENTO (Corretta per errori di codifica) ---
@st.cache_data
def get_data():
    # Proviamo le codifiche più comuni per i file creati con Excel in Italia
    for encoding in ['latin1', 'cp1252', 'utf-8', 'utf-16']:
        try:
            # Caricamento Rosters
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=encoding)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo']
            
            # Caricamento Quotazioni
            df_quot = pd.read_csv('quot.csv', encoding=encoding)
            
            # Pulizia ID
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce').fillna(0).astype(int)
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce').fillna(0).astype(int)
            
            return df_rose[df_rose['Id'] > 0], df_quot[df_quot['Id'] > 0]
        except (UnicodeDecodeError, Exception):
            continue
    
    st.error("Impossibile leggere i file CSV. Assicurati che non siano aperti in Excel e che siano salvati correttamente.")
    return None, None
# --- 2. LOGICA PRINCIPALE ---
df_rose, df_quot = get_data()

if df_rose is not None and df_quot is not None:
    # Preparazione base rosterata (INNER JOIN) per le pagine standard
    df_base = pd.merge(df_rose, df_quot, on='Id', how='inner')
    df_base['Squadra_LFM'] = df_base['Squadra_LFM'].str.strip()
    
    # Inizializzazione Sessione
    if 'refunded_ids' not in st.session_state: st.session_state.refunded_ids = set()
    if 'tagli_map' not in st.session_state: st.session_state.tagli_map = set()

    # Sidebar
    st.sidebar.title("🧪 LAB 2")
    menu = st.sidebar.radio("Menu:", ["🏠 Dashboard", "📊 Ranking FVM", "⚙️ Debug"])

    if menu == "🏠 Dashboard":
        st.title("🏠 Monitoraggio Rose")
        st.write("Dati caricati correttamente. Seleziona Ranking FVM per i test pesanti.")
        st.dataframe(df_base.head(10))

    elif menu == "📊 Ranking FVM":
        st.title("📊 Scouting Globale (Test)")
        
        # Filtri
        ruoli = st.multiselect("Filtra Ruolo:", ["P", "D", "C", "A"], default=["A"])
        solo_liberi = st.checkbox("Mostra solo giocatori LIBERI")

        # Qui facciamo l'operazione pesante (OUTER JOIN) solo su richiesta
        with st.spinner("Elaborazione matrice..."):
            # Creiamo la lista con tutti i calciatori e aggiungiamo i possessori
            df_rank = pd.merge(df_quot, df_rose, on='Id', how='left')
            
            # Formattazione Icone
            def set_status(row):
                if pd.isna(row['Squadra_LFM']): return "🟢 LIBERO"
                if row['Id'] in st.session_state.refunded_ids: return f"✈️ {row['Squadra_LFM']}"
                return row['Squadra_LFM']

            df_rank['Stato'] = df_rank.apply(set_status, axis=1)
            
            # Filtro Ruolo
            if ruoli: df_rank = df_rank[df_rank['R'].isin(ruoli)]
            
            # Se vuoi vedere i possessori divisi per colonna, qui usiamo una vista semplificata
            if solo_liberi:
                df_rank = df_rank[pd.isna(df_rank['Squadra_LFM'])]
            
            # Mostriamo i Top per FVM
            res = df_rank.sort_values('FVM', ascending=False)[['FVM', 'Nome', 'R', 'Stato']]
            st.dataframe(res, use_container_width=True, hide_index=True)

    elif menu == "⚙️ Debug":
        st.title("⚙️ Analisi File")
        st.write(f"Righe in Rosters: {len(df_rose)}")
        st.write(f"Righe in Quotazioni: {len(df_quot)}")
        if st.button("Pulisci Cache"):
            st.cache_data.clear()
            st.rerun()

else:
    st.warning("Assicurati di avere 'quot.csv' e 'fantamanager-2021-rosters.csv' nella stessa cartella di lab2.py")
