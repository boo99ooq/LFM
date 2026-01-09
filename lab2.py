import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Dashboard - Golden Edition", layout="wide", page_icon="⚖️")

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
            
            # INNER JOIN per le pagine standard (solo chi ha squadra)
            df_owned = pd.merge(df_rose, df_quot, on='Id', how='left')
            df_owned['Nome'] = df_owned['Nome'].fillna("ID: " + df_owned['Id'].astype(int, errors='ignore').astype(str))
            df_owned['Qt.I'] = pd.to_numeric(df_owned['Qt.I'], errors='coerce').fillna(0)
            df_owned['FVM'] = pd.to_numeric(df_owned['FVM'], errors='coerce').fillna(0)
            df_owned['Squadra_LFM'] = df_owned['Squadra_LFM'].str.strip()
            
            return df_owned, df_quot
        except: continue
    return None, None

# --- 2. GESTIONE SESSIONE ---
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
        df_temp['Lega'] = df_temp['Lega'].str.strip()
        df_temp['Crediti'] = pd.to_numeric(df_temp['Crediti'], errors='coerce').fillna(0)
        st.session_state.df_leghe_full = df_temp
    except:
        st.session_state.df_leghe_full = pd.DataFrame(columns=['Squadra', 'Lega', 'Crediti'])

def fix_league_names(df_leghe):
    df = df_leghe.copy()
    df['Lega'] = df['Lega'].replace(['Lega A', 'nan', 'Da Assegnare'], 'Serie A')
    df.loc[df['Squadra'].str.contains("Fiorentina", case=False, na=False), 'Lega'] = "Serie A"
    return df

st.session_state.df_leghe_full = fix_league_names(st.session_state.df_leghe_full)
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
MAPPATURA_COLORI = {"Serie A": "#fce4ec", "Bundesliga": "#e8f5e9", "Premier League": "#e3f2fd", "Liga BBVA": "#fffde7"}

# --- 3. COSTRUZIONE DATI ---
df_base, df_all_quot = load_static_data()

if df_base is not None:
    df_base = pd.merge(df_base, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Admin")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🏃 Svincolati *", "✂️ Tagli Volontari", "📊 Ranking FVM", "📋 Visualizza Rose", "🟢 Giocatori Liberi", "⚙️ Gestione Squadre"])

    # --- (DASHBOARD, SVINCOLATI, TAGLI, RANKING, ROSE rimangono identici all'ultima versione funzionante) ---
    # Per brevità non li riscrivo, ma nel tuo file devono esserci.

    # --- NUOVA PAGINA: GIOCATORI LIBERI ---
    if menu == "🟢 Giocatori Liberi":
        st.title("🟢 Calciatori non presenti in nessuna rosa")
        st.info("Questa lista mostra i giocatori disponibili sul mercato (non acquistati in nessuna delle 4 leghe).")
        
        # Identifichiamo gli ID di tutti i giocatori posseduti nelle rose
        ids_posseduti = set(df_base['Id'].unique())
        
        # Filtriamo il listone quotazioni per escludere chi ha già una squadra
        df_liberi = df_all_quot[~df_all_quot['Id'].isin(ids_posseduti)].copy()
        
        c1, c2 = st.columns(2)
        ruoli_lib = sorted(df_liberi['R'].dropna().unique())
        r_sel = c1.multiselect("Filtra per Ruolo:", ruoli_lib, default=ruoli_lib)
        cerca_lib = c2.text_input("Cerca per nome:")
        
        if r_sel:
            df_liberi = df_liberi[df_liberi['R'].isin(r_sel)]
        if cerca_lib:
            df_liberi = df_liberi[df_liberi['Nome'].str.contains(cerca_lib, case=False, na=False)]
            
        st.dataframe(df_liberi.sort_values(by='FVM', ascending=False)[['Nome', 'R', 'Qt.I', 'FVM']], 
                     column_config={"FVM": "FVM", "Qt.I": "Quot."},
                     use_container_width=True, hide_index=True)

    # --- (GESTIONE SQUADRE rimane identico) ---
