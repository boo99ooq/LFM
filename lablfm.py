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

# --- 4. COSTRUZIONE INTERFACCIA ---
df_static = load_static_data()
if df_static is not None:
    df_base = pd.merge(df_static, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Admin")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🏃 Svincolati *", "✂️ Tagli Volontari", "📊 Ranking FVM", "📋 Visualizza Rose", "⚙️ Gestione Squadre"])

    # --- DASHBOARD (Sintetizzata) ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti e Rimborsi")
        cols = st.columns(2)
        for i, nome_lega in enumerate([l for l in ORDINE_LEGHE if l in df_base['Lega'].values]):
            with cols[i % 2]:
                st.markdown(f"## 🏆 {nome_lega}")
                df_l = df_base[df_base['Lega'] == nome_lega]
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                tabella = pd.merge(df_l[['Squadra_LFM', 'Crediti']].drop_duplicates(), res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli.rename(columns={'Nome':'N_T'}), on='Squadra_LFM', how='left').fillna(0)
                tabella['Totale'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                for _, sq in tabella.sort_values(by='Squadra_LFM').iterrows():
                    st.markdown(f"""<div style="background-color: {MAPPATURA_COLORI.get(nome_lega, '#f5f5f5')}; padding: 15px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #ddd; color: #333;">
                        <div style="display: flex; justify-content: space-between;"><b>{sq['Squadra_LFM']}</b><b style="color:#1e88e5;">{int(sq['Totale'])} cr</b></div>
                        <hr style="margin:8px 0;"><div style="font-size:13px;">* {sq['Nome'] if sq['Nome'] else "nessuno"} | ✂️ {sq['N_T'] if sq['N_T'] else "nessuno"}</div></div>""", unsafe_allow_html=True)

    # --- SVINCOLATI * e TAGLI VOLONTARI (Codice invariato) ---
    elif menu == "🏃 Svincolati *":
        st.title("🏃 Rimborsi da *")
        cerca = st.text_input("Cerca giocatore:")
        if cerca:
            df_f = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
            edit = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'R', 'FVM', 'Qt.I', 'Rimborso_Star', 'Id']], hide_index=True, use_container_width=True)
            if st.button("Salva"):
                st.session_state.refunded_ids = set(edit[edit['Rimborsato_Star']]['Id']); st.rerun()

    elif menu == "✂️ Tagli Volontari":
        st.title("✂️ Tagli Volontari")
        cerca_t = st.text_input("Cerca per squadra:")
        if cerca_t:
            df_t = df_base[df_base['Nome'].str.contains(cerca_t, case=False, na=False)]
            edit_t = st.data_editor(df_t[['Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'Rimborso_Taglio', 'Taglio_Key']], hide_index=True, use_container_width=True)
            if st.button("Salva"):
                st.session_state.tagli_map = set(edit_t[edit_t['Rimborsato_Taglio']]['Taglio_Key']); st.rerun()

    # --- NUOVA PAGINA: RANKING FVM (MATRICE PER LEGA) ---
    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM per Lega")
        
        # Filtri Ranking
        c1, c2 = st.columns(2)
        ruolo_filt = c1.multiselect("Filtra Ruolo:", ["P", "D", "C", "A"], default=["P", "D", "C", "A"])
        leghe_filt = c2.multiselect("Visualizza Colonne Leghe:", ORDINE_LEGHE, default=ORDINE_LEGHE)
        
        # Preparazione dati pivot
        df_rank = df_base.copy()
        if ruolo_filt:
            df_rank = df_rank[df_rank['R'].isin(ruolo_filt)]
            
        # Creiamo il pivot: Indice (Giocatore, Ruolo, FVM) e Colonne (Leghe)
        # Usiamo aggfunc per unire i nomi delle squadre se ce ne sono più di una per lega
        pivot_rank = df_rank.pivot_table(
            index=['FVM', 'Nome', 'R'], 
            columns='Lega', 
            values='Squadra_LFM', 
            aggfunc=lambda x: ", ".join(x)
        ).reset_index()

        # Riordiniamo per FVM decrescente
        pivot_rank = pivot_rank.sort_values(by='FVM', ascending=False)

        # Selezioniamo solo le colonne richieste + dati base
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

    # --- VISUALIZZA ROSE (Codice invariato) ---
    elif menu == "📋 Visualizza Rose":
        st.title("📋 Consultazione Rose")
        sq_sel = st.selectbox("Squadra:", sorted(df_base['Squadra_LFM'].unique()))
        df_r = df_base[df_base['Squadra_LFM'] == sq_sel].copy()
        st.dataframe(df_r[['Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    # --- GESTIONE SQUADRE (Codice invariato) ---
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione")
        edited = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Salva"):
            st.session_state.df_leghe_full = fix_league_names(edited); st.rerun()
        c1, c2, c3 = st.columns(3)
        c1.download_button("database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("database_tagli.csv", pd.DataFrame({'Id': [k.split('_')[0] for k in st.session_state.tagli_map], 'Squadra':[k.split('_')[1] for k in st.session_state.tagli_map]}).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")

else: st.error("Carica i file CSV!")
