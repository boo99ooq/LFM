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
            
            # Conversione ID in stringhe pulite per evitare .0
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce').fillna(0).astype(int).astype(str)
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce').fillna(0).astype(int).astype(str)
            
            # Rimozione righe senza ID valido
            df_rose = df_rose[df_rose['Id'] != "0"]
            df_quot = df_quot[df_quot['Id'] != "0"]
            
            # OUTER JOIN per includere TUTTI (anche i liberi)
            df = pd.merge(df_rose, df_quot, on='Id', how='outer')
            
            df['Nome'] = df['Nome'].fillna("Sconosciuto")
            df['Qt.I'] = pd.to_numeric(df['Qt.I'], errors='coerce').fillna(0)
            df['FVM'] = pd.to_numeric(df['FVM'], errors='coerce').fillna(0)
            df['Rimborso_Star'] = df['FVM'] + (df['Qt.I'] / 2)
            df['Rimborso_Taglio'] = (df['FVM'] + df['Qt.I']) / 2
            df['Squadra_LFM'] = df['Squadra_LFM'].str.strip().fillna("LIBERO")
            return df
        except: continue
    return None

# --- 2. GESTIONE SESSIONE ---
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

def fix_league_names(df_leghe):
    df = df_leghe.copy()
    df['Lega'] = df['Lega'].replace(['Lega A', 'nan', 'Da Assegnare', 'None'], 'Serie A')
    df.loc[df['Squadra'].str.contains("Fiorentina", case=False, na=False), 'Lega'] = "Serie A"
    return df

st.session_state.df_leghe_full = fix_league_names(st.session_state.df_leghe_full)
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
MAPPATURA_COLORI = {"Serie A": "#fce4ec", "Bundesliga": "#e8f5e9", "Premier League": "#e3f2fd", "Liga BBVA": "#fffde7"}

# --- 3. COSTRUZIONE BASE DATI ---
df_static = load_static_data()
if df_static is not None:
    # Merge con le leghe
    df_base = pd.merge(df_static, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    
    # Flags rimborsi
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'] + "_" + df_base['Squadra_LFM']
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Admin")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🏃 Svincolati *", "✂️ Tagli Volontari", "📊 Ranking FVM", "📋 Visualizza Rose", "⚙️ Gestione Squadre"])

    # --- 🏠 DASHBOARD (Solo Squadre Reali) ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti e Rimborsi")
        df_dash = df_base[df_base['Squadra_LFM'] != "LIBERO"].copy()
        leghe_eff = [l for l in ORDINE_LEGHE if l in df_dash['Lega'].unique()]
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_eff):
            with cols[i % 2]:
                st.markdown(f"## 🏆 {nome_lega}")
                df_l = df_dash[df_dash['Lega'] == nome_lega]
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                tabella = pd.merge(df_l[['Squadra_LFM', 'Crediti']].drop_duplicates(), res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli.rename(columns={'Nome':'N_T'}), on='Squadra_LFM', how='left').fillna(0)
                tabella['Totale'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                for _, sq in tabella.sort_values(by='Squadra_LFM').iterrows():
                    d_html = ""
                    if sq['Nome']: d_html += f"<div style='font-size:13px;color:#d32f2f;'><b>✈️ Svinc:</b> {sq['Nome']}</div>"
                    if sq['N_T']: d_html += f"<div style='font-size:13px;color:#7b1fa2;'><b>✂️ Tagli:</b> {sq['N_T']}</div>"
                    st.markdown(f"""<div style="background-color: {MAPPATURA_COLORI.get(nome_lega, '#f5f5f5')}; padding: 15px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #ddd; color: #333;">
                        <div style="display: flex; justify-content: space-between;"><b>{sq['Squadra_LFM']}</b><b style="color:#1e88e5;">{int(sq['Totale'])} cr</b></div>
                        <hr style="margin:8px 0;">{d_html if d_html else "<i>Nessuna operazione</i>"}</div>""", unsafe_allow_html=True)

    # --- 📊 RANKING FVM (Include Liberi) ---
    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM Globale")
        c1, c2, c3 = st.columns(3)
        ruolo_filt = c1.multiselect("Ruolo:", ["P", "D", "C", "A"], default=["P", "D", "C", "A"])
        leghe_filt = c2.multiselect("Leghe:", ORDINE_LEGHE, default=ORDINE_LEGHE)
        solo_liberi = c3.checkbox("Solo LIBERI OVUNQUE", value=False)
        
        df_rank = df_base.copy()
        if ruolo_filt: df_rank = df_rank[df_rank['R'].isin(ruolo_filt)]

        def format_owner(row):
            if row['Squadra_LFM'] == "LIBERO": return "🟢 LIBERO"
            if row['Rimborsato_Star']: return f"✈️ {row['Squadra_LFM']}" 
            if row['Rimborsato_Taglio']: return f"✂️ {row['Squadra_LFM']}" 
            return row['Squadra_LFM']

        df_rank['Display'] = df_rank.apply(format_owner, axis=1)
        pivot = df_rank.pivot_table(index=['FVM', 'Nome', 'R'], columns='Lega', values='Display', aggfunc=lambda x: " | ".join(str(v) for v in x if str(v) != 'nan'), dropna=False).reset_index()

        for l in ORDINE_LEGHE:
            if l in pivot.columns: pivot[l] = pivot[l].fillna("🟢 LIBERO")
            else: pivot[l] = "🟢 LIBERO"

        if solo_liberi:
            mask = True
            for l in ORDINE_LEGHE: mask &= (pivot[l] == "🟢 LIBERO")
            pivot = pivot[mask]

        st.dataframe(pivot.sort_values(by='FVM', ascending=False)[['FVM', 'Nome', 'R'] + [l for l in leghe_filt if l in pivot.columns]], use_container_width=True, hide_index=True)

    # --- GESTIONE SQUADRE ---
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione")
        edited = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Salva"):
            st.session_state.df_leghe_full = fix_league_names(edited); st.rerun()
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.download_button("database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("database_tagli.csv", pd.DataFrame([{'Id': k.split('_')[0], 'Squadra': k.split('_')[1]} for k in st.session_state.tagli_map if "_" in k]).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")

    # (Le altre pagine: Svincolati *, Rose rimangono come prima ma con dropna sui LIBERI)
    elif menu == "🏃 Svincolati *":
        st.title("✈️ Rimborsi da *")
        df_sv = df_base[df_base['Squadra_LFM'] != "LIBERO"].copy()
        cerca = st.text_input("Cerca:")
        if cerca:
            df_f = df_sv[df_sv['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
            st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'R', 'Rimborso_Star', 'Id']], hide_index=True)
            if st.button("Salva"): st.rerun()

    elif menu == "📋 Visualizza Rose":
        st.title("📋 Rose")
        df_ro = df_base[df_base['Squadra_LFM'] != "LIBERO"].copy()
        s_sel = st.selectbox("Squadra:", sorted(df_ro['Squadra_LFM'].unique()))
        st.dataframe(df_ro[df_ro['Squadra_LFM'] == s_sel][['Nome', 'R', 'FVM']], hide_index=True)

else: st.error("Errore caricamento file!")
