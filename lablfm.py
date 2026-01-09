import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Dashboard - Golden Edition", layout="wide", page_icon="⚖️")

# --- 1. CARICAMENTO E PULIZIA DATI ---
@st.cache_data
def load_sanitized_data():
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            # Caricamento file
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            
            # 1. Normalizzazione ID (Stringhe senza .0)
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce').fillna(0).astype(int).astype(str)
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce').fillna(0).astype(int).astype(str)
            
            # 2. Unione Totale (Outer)
            df = pd.merge(df_quot, df_rose, on='Id', how='outer')
            
            # 3. Sanitizzazione immediata di ogni colonna per evitare crash
            df['Nome'] = df['Nome'].fillna("Sconosciuto").astype(str)
            df['R'] = df['R'].fillna("?").astype(str)
            df['Squadra_LFM'] = df['Squadra_LFM'].str.strip().fillna("LIBERO").astype(str)
            df['FVM'] = pd.to_numeric(df['FVM'], errors='coerce').fillna(0).astype(int)
            df['Qt.I'] = pd.to_numeric(df['Qt.I'], errors='coerce').fillna(0).astype(int)
            
            # 4. Calcolo rimborsi su dati puliti
            df['Rimborso_Star'] = df['FVM'] + (df['Qt.I'] / 2)
            df['Rimborso_Taglio'] = (df['FVM'] + df['Qt.I']) / 2
            
            return df[df['Id'] != "0"] # Esclude righe corrotte
        except Exception as e:
            continue
    return None

# --- 2. GESTIONE STATO ---
if 'refunded_ids' not in st.session_state:
    try:
        db_p = pd.read_csv('database_lfm.csv')
        st.session_state.refunded_ids = set(db_p['Id'].astype(str).tolist())
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

# --- 3. LOGICA DASHBOARD ---
df_base = load_sanitized_data()

if df_base is not None:
    # Merge con le leghe per avere le colonne Lega e Crediti
    df_full = pd.merge(df_base, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    
    # Check rimborsi
    df_full['R_Star'] = df_full['Id'].isin(st.session_state.refunded_ids)
    df_full['T_Key'] = df_full['Id'] + "_" + df_full['Squadra_LFM']
    df_full['R_Taglio'] = df_full['T_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Admin")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🏃 Svincolati *", "✂️ Tagli Volontari", "📊 Ranking FVM", "📋 Visualizza Rose", "⚙️ Gestione Squadre"])

    ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
    COLORI = {"Serie A": "#fce4ec", "Bundesliga": "#e8f5e9", "Premier League": "#e3f2fd", "Liga BBVA": "#fffde7"}

    # --- RANKING FVM (Punto critico risolto) ---
    if menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM Globale")
        c1, c2, c3 = st.columns(3)
        ruolo = c1.multiselect("Ruolo:", ["P", "D", "C", "A"], default=["P", "D", "C", "A"])
        leghe_v = c2.multiselect("Leghe:", ORDINE_LEGHE, default=ORDINE_LEGHE)
        solo_lib = c3.checkbox("Solo LIBERI OVUNQUE")

        df_rank = df_full.copy()
        if ruolo: df_rank = df_rank[df_rank['R'].isin(ruolo)]

        def format_rank_name(row):
            if row['Squadra_LFM'] == "LIBERO": return "🟢 LIBERO"
            pre = "✈️ " if row['R_Star'] else ("✂️ " if row['R_Taglio'] else "")
            return f"{pre}{row['Squadra_LFM']}"

        df_rank['Display'] = df_rank.apply(format_rank_name, axis=1)
        
        # Pivot table sicura
        pivot = df_rank.pivot_table(index=['FVM', 'Nome', 'R'], columns='Lega', values='Display', 
                                    aggfunc=lambda x: " | ".join(str(v) for v in x if v), dropna=False).reset_index()

        for l in ORDINE_LEGHE:
            if l in pivot.columns: pivot[l] = pivot[l].fillna("🟢 LIBERO")
            else: pivot[l] = "🟢 LIBERO"

        if solo_lib:
            mask = True
            for l in ORDINE_LEGHE: mask &= (pivot[l] == "🟢 LIBERO")
            pivot = pivot[mask]

        st.dataframe(pivot.sort_values('FVM', ascending=False)[['FVM', 'Nome', 'R'] + [l for l in leghe_v if l in pivot.columns]], use_container_width=True, hide_index=True)

    # --- ALTRE PAGINE (Semplificate per evitare errori) ---
    elif menu == "🏠 Dashboard":
        st.title("🏠 Dashboard")
        df_d = df_full[df_full['Squadra_LFM'] != "LIBERO"].dropna(subset=['Lega'])
        for l in [leg for leg in ORDINE_LEGHE if leg in df_d['Lega'].unique()]:
            st.subheader(f"🏆 {l}")
            st.write(df_d[df_d['Lega'] == l][['Squadra_LFM', 'Crediti']].drop_duplicates())

    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Gestione")
        edit = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Salva"):
            st.session_state.df_leghe_full = edit
            st.rerun()
        st.download_button("Scarica database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")

else:
    st.error("Impossibile caricare i file. Controlla che quot.csv e fantamanager-2021-rosters.csv siano corretti.")
