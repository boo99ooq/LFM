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
            df = pd.merge(df_rose, df_quot, on='Id', how='left')
            df['Nome'] = df['Nome'].fillna("ID: " + df['Id'].astype(int, errors='ignore').astype(str))
            df['Qt.I'] = pd.to_numeric(df['Qt.I'], errors='coerce').fillna(0)
            df['FVM'] = pd.to_numeric(df['FVM'], errors='coerce').fillna(0)
            df['Rimborso_Star'] = df['FVM'] + (df['Qt.I'] / 2)
            df['Rimborso_Taglio'] = (df['FVM'] + df['Qt.I']) / 2
            df['Squadra_LFM'] = df['Squadra_LFM'].str.strip()
            return df
        except: continue
    return None

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
        df_static_init = load_static_data()
        if df_static_init is not None:
            squadre = sorted(df_static_init['Squadra_LFM'].unique())
            st.session_state.df_leghe_full = pd.DataFrame({'Squadra': squadre, 'Lega': 'Da Assegnare', 'Crediti': 0})

def fix_league_names(df_leghe):
    df = df_leghe.copy()
    df['Lega'] = df['Lega'].replace(['Lega A', 'nan', 'Da Assegnare'], 'Serie A')
    df.loc[df['Squadra'].str.contains("Fiorentina", case=False, na=False), 'Lega'] = "Serie A"
    return df

st.session_state.df_leghe_full = fix_league_names(st.session_state.df_leghe_full)
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
MAPPATURA_COLORI = {"Serie A": "#fce4ec", "Bundesliga": "#e8f5e9", "Premier League": "#e3f2fd", "Liga BBVA": "#fffde7"}

# --- 3. COSTRUZIONE DATI ---
df_static = load_static_data()
if df_static is not None:
    df_base = pd.merge(df_static, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Admin")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🏃 Svincolati *", "✂️ Tagli Volontari", "📊 Ranking FVM", "📋 Visualizza Rose", "⚙️ Gestione Squadre"])

    # (Le altre sezioni Dashboard, Svincolati, Tagli rimangono come prima...)
    
    # --- RANKING FVM AGGIORNATO ---
    if menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM per Lega")
        c1, c2 = st.columns(2)
        ruolo_filt = c1.multiselect("Filtra Ruolo:", ["P", "D", "C", "A"], default=["P", "D", "C", "A"])
        leghe_filt = c2.multiselect("Visualizza Colonne Leghe:", ORDINE_LEGHE, default=ORDINE_LEGHE)
        
        df_rank = df_base.copy()
        if ruolo_filt:
            df_rank = df_rank[df_rank['R'].isin(ruolo_filt)]

        # LOGICA DI FORMATTAZIONE PER LA MATRICE
        def format_owner(row):
            name = row['Squadra_LFM']
            if row['Rimborsato_Star']:
                return f"~~*{name}*~~" # Sbarrato e asterisco per svincolo globale
            if row['Rimborsato_Taglio']:
                return f"✂️ {name}" # Icona forbici per taglio volontario
            return name

        df_rank['Squadra_Display'] = df_rank.apply(format_owner, axis=1)

        pivot_rank = df_rank.pivot_table(
            index=['FVM', 'Nome', 'R'], 
            columns='Lega', 
            values='Squadra_Display', 
            aggfunc=lambda x: " | ".join(x)
        ).reset_index()

        pivot_rank = pivot_rank.sort_values(by='FVM', ascending=False)
        colonne_finali = ['FVM', 'Nome', 'R'] + [l for l in leghe_filt if l in pivot_rank.columns]
        
        st.dataframe(
            pivot_rank[colonne_finali],
            column_config={
                "FVM": st.column_config.NumberColumn("FVM", format="%d"),
                "R": "Ruolo",
                **{l: st.column_config.TextColumn(f"🏆 {l}") for l in ORDINE_LEGHE}
            },
            use_container_width=True,
            hide_index=True
        )
        st.info("Legenda: ~~*Squadra*~~ = Svincolato d'ufficio (*) | ✂️ Squadra = Taglio Volontario")

    # (Includi il resto del codice per Dashboard, Svincolati, Rose e Gestione Squadre come nell'ultima versione...)
