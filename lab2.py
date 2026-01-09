import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM LAB - Versione Definitiva", layout="wide", page_icon="🧪")

# --- 1. CARICAMENTO DATI (SICURO) ---
@st.cache_data
def load_data():
    # Testiamo diverse codifiche per evitare l'errore 'utf-8' codec can't decode
    for enc in ['latin1', 'cp1252', 'utf-8', 'iso-8859-1']:
        try:
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            
            # Normalizzazione ID (Stringhe pulite senza .0)
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce').fillna(0).astype(int).astype(str)
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce').fillna(0).astype(int).astype(str)
            
            # Rimozione ID nulli
            df_rose = df_rose[df_rose['Id'] != "0"]
            df_quot = df_quot[df_quot['Id'] != "0"]
            
            # OUTER JOIN per includere TUTTI (Roster + Liberi)
            df = pd.merge(df_quot, df_rose, on='Id', how='outer')
            
            # Sanitizzazione Valori
            df['Nome'] = df['Nome'].fillna("Sconosciuto")
            df['R'] = df['R'].fillna("?")
            df['FVM'] = pd.to_numeric(df['FVM'], errors='coerce').fillna(0).astype(int)
            df['Qt.I'] = pd.to_numeric(df['Qt.I'], errors='coerce').fillna(0).astype(int)
            df['Squadra_LFM'] = df['Squadra_LFM'].str.strip().fillna("LIBERO")
            
            # Calcoli Rimborsi
            df['Rimborso_Star'] = df['FVM'] + (df['Qt.I'] / 2)
            df['Rimborso_Taglio'] = (df['FVM'] + df['Qt.I']) / 2
            
            return df
        except:
            continue
    return None

# --- 2. GESTIONE STATO E DATABASE ---
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

def fix_league_names(df):
    df['Lega'] = df['Lega'].replace(['Lega A', 'nan', 'Da Assegnare', 'None'], 'Serie A').fillna('Serie A')
    return df

st.session_state.df_leghe_full = fix_league_names(st.session_state.df_leghe_full)
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
COLORI = {"Serie A": "#fce4ec", "Bundesliga": "#e8f5e9", "Premier League": "#e3f2fd", "Liga BBVA": "#fffde7"}

# --- 3. COSTRUZIONE INTERFACCIA ---
df_base = load_data()

if df_base is not None:
    # Unione con le leghe per Dashboard e Rose
    df_full = pd.merge(df_base, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_full['In_Star'] = df_full['Id'].isin(st.session_state.refunded_ids)
    df_full['T_Key'] = df_full['Id'] + "_" + df_full['Squadra_LFM']
    df_full['In_Taglio'] = df_full['T_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Dashboard")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🏃 Svincolati *", "✂️ Tagli Volontari", "📊 Ranking FVM", "📋 Visualizza Rose", "⚙️ Gestione Squadre"])

    # --- 🏠 DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti")
        df_d = df_full[df_full['Squadra_LFM'] != "LIBERO"].copy()
        cols = st.columns(2)
        leghe_attive = [l for l in ORDINE_LEGHE if l in df_d['Lega'].unique()]
        for i, l in enumerate(leghe_attive):
            with cols[i % 2]:
                st.markdown(f"### 🏆 {l}")
                df_l = df_d[df_d['Lega'] == l]
                tab = df_l[['Squadra_LFM', 'Crediti']].drop_duplicates().sort_values('Squadra_LFM')
                for _, r in tab.iterrows():
                    st.markdown(f"""<div style="background-color:{COLORI.get(l,'#f0f0f0')}; padding:10px; border-radius:10px; border:1px solid #ccc; margin-bottom:5px; color:#333;">
                    <b>{r['Squadra_LFM']}</b>: {int(r['Crediti'])} cr</div>""", unsafe_allow_html=True)

    # --- 🏃 SVINCOLATI * ---
    elif menu == "🏃 Svincolati *":
        st.title("✈️ Svincolati d'ufficio (*)")
        cerca = st.text_input("Cerca giocatore:", key="s1")
        if cerca:
            # Solo chi ha una squadra può essere svincolato d'ufficio
            df_f = df_full[(df_full['Squadra_LFM'] != "LIBERO") & (df_full['Nome'].str.contains(cerca, case=False, na=False))].drop_duplicates('Id')
            edit = st.data_editor(df_f[['In_Star', 'Nome', 'R', 'FVM', 'Rimborso_Star', 'Id']], column_config={"In_Star":"Svincola", "Id":None}, hide_index=True)
            if st.button("Salva Modifiche"):
                for _, r in edit.iterrows():
                    if r['In_Star']: st.session_state.refunded_ids.add(r['Id'])
                    else: st.session_state.refunded_ids.discard(r['Id'])
                st.rerun()

    # --- ✂️ TAGLI VOLONTARI ---
    elif menu == "✂️ Tagli Volontari":
        st.title("✂️ Tagli Volontari (50%)")
        cerca_t = st.text_input("Cerca per squadra o nome:", key="t1")
        if cerca_t:
            df_t = df_full[(df_full['Squadra_LFM'] != "LIBERO") & (df_full['Nome'].str.contains(cerca_t, case=False, na=False))]
            edit_t = st.data_editor(df_t[['In_Taglio', 'Nome', 'Squadra_LFM', 'Rimborso_Taglio', 'T_Key']], column_config={"T_Key":None, "In_Taglio":"Taglia"}, hide_index=True)
            if st.button("Conferma Tagli"):
                for _, r in edit_t.iterrows():
                    if r['In_Taglio']: st.session_state.tagli_map.add(r['T_Key'])
                    else: st.session_state.tagli_map.discard(r['T_Key'])
                st.rerun()

    # --- 📊 RANKING FVM (A MATRICE) ---
    elif menu == "📊 Ranking FVM":
        st.title("📊 Scouting e Ranking FVM")
        c1, c2, c3 = st.columns(3)
        r_f = c1.multiselect("Ruolo:", ["P", "D", "C", "A"], default=["A"])
        l_f = c2.multiselect("Leghe:", ORDINE_LEGHE, default=ORDINE_LEGHE)
        solo_lib = c3.checkbox("Mostra solo liberi ovunque")

        df_r = df_full.copy()
        if r_f: df_r = df_r[df_r['R'].isin(r_f)]

        def get_disp(row):
            if row['Squadra_LFM'] == "LIBERO": return "🟢 LIBERO"
            pre = "✈️ " if row['In_Star'] else ("✂️ " if row['In_Taglio'] else "")
            return f"{pre}{row['Squadra_LFM']}"

        df_r['Display'] = df_r.apply(get_disp, axis=1)
        pivot = df_r.pivot_table(index=['FVM', 'Nome', 'R'], columns='Lega', values='Display', 
                                aggfunc=lambda x: " | ".join(str(v) for v in x if v), dropna=False).reset_index()

        for l in ORDINE_LEGHE:
            if l in pivot.columns: pivot[l] = pivot[l].fillna("🟢 LIBERO")
            else: pivot[l] = "🟢 LIBERO"

        if solo_lib:
            mask = True
            for l in ORDINE_LEGHE: mask &= (pivot[l] == "🟢 LIBERO")
            pivot = pivot[mask]

        st.dataframe(pivot.sort_values('FVM', ascending=False)[['FVM', 'Nome', 'R'] + [col for col in l_f if col in pivot.columns]], use_container_width=True, hide_index=True)

    # --- 📋 VISUALIZZA ROSE ---
    elif menu == "📋 Visualizza Rose":
        st.title("📋 Consultazione Rose")
        df_ro = df_full[df_full['Squadra_LFM'] != "LIBERO"]
        s_sel = st.selectbox("Squadra:", sorted(df_ro['Squadra_LFM'].unique()))
        df_res = df_ro[df_ro['Squadra_LFM'] == s_sel].copy()
        df_res['Stato'] = df_res.apply(lambda r: "✈️" if r['In_Star'] else ("✂️" if r['In_Taglio'] else "🏃"), axis=1)
        st.dataframe(df_res[['Stato', 'Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    # --- ⚙️ GESTIONE SQUADRE ---
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione")
        c1, c2 = st.columns([4,1])
        lega_f = c1.selectbox("Filtra Lega:", ["Tutte"] + ORDINE_LEGHE)
        if c2.button("Reset 🔄"): st.rerun()
        
        df_edit = st.session_state.df_leghe_full if lega_f == "Tutte" else st.session_state.df_leghe_full[st.session_state.df_leghe_full['Lega'] == lega_f]
        res_e = st.data_editor(df_edit, use_container_width=True, hide_index=True)
        if st.button("Salva Crediti"):
            st.session_state.df_leghe_full.update(res_e)
            st.success("Dati salvati in sessione!"); st.rerun()
        
        st.divider()
        st.subheader("📥 Download Backup")
        c1, c2, c3 = st.columns(3)
        c1.download_button("database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("database_tagli.csv", pd.DataFrame([{'Id': k.split('_')[0], 'Squadra': k.split('_')[1]} for k in st.session_state.tagli_map if "_" in k]).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")

else:
    st.error("Errore critico: File CSV non trovati o corrotti.")
