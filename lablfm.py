import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM LAB - Gestione Tagli", layout="wide", page_icon="🧪")

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
            
            # CALCOLO RIMBORSI * (Pieno: FVM + Qt.I/2) -> Come da logica precedente
            df['Rimborso_Star'] = df['FVM'] + (df['Qt.I'] / 2)
            
            # CALCOLO TAGLI VOLONTARI (50% di tutto: (FVM + Qt.I)/2)
            df['Rimborso_Taglio'] = (df['FVM'] + df['Qt.I']) / 2
            
            df['Squadra_LFM'] = df['Squadra_LFM'].str.strip()
            return df
        except: continue
    return None

# --- 2. GESTIONE SESSIONE (Sdoppiata) ---
# Rimborsi * (Svincolati d'ufficio)
if 'refunded_ids' not in st.session_state:
    st.session_state.refunded_ids = set()
# Tagli Volontari
if 'tagli_ids' not in st.session_state:
    st.session_state.tagli_ids = set()

# Caricamento leghe.csv
if 'df_leghe_full' not in st.session_state:
    try:
        df_temp = pd.read_csv('leghe.csv', encoding='latin1')
        df_temp['Squadra'] = df_temp['Squadra'].str.strip()
        df_temp['Lega'] = df_temp['Lega'].str.strip()
        df_temp['Crediti'] = pd.to_numeric(df_temp['Crediti'], errors='coerce').fillna(0)
        st.session_state.df_leghe_full = df_temp
    except:
        st.session_state.df_leghe_full = pd.DataFrame(columns=['Squadra', 'Lega', 'Crediti'])

# --- 3. UNIFICAZIONE NOMI ---
def fix_league_names(df_leghe):
    df = df_leghe.copy()
    df['Lega'] = df['Lega'].replace("Lega A", "Serie A")
    df.loc[df['Squadra'].str.contains("Fiorentina", case=False, na=False), 'Lega'] = "Serie A"
    return df

st.session_state.df_leghe_full = fix_league_names(st.session_state.df_leghe_full)

MAPPATURA_COLORI = {
    "Serie A": "#fce4ec", "Bundesliga": "#e8f5e9", "Premier League": "#e3f2fd", "Liga BBVA": "#fffde7"
}

# --- 4. COSTRUZIONE INTERFACCIA ---
df_static = load_static_data()
if df_static is not None:
    df_base = pd.merge(df_static, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    
    # Checkbox stato
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Rimborsato_Taglio'] = df_base['Id'].isin(st.session_state.tagli_ids)

    st.sidebar.title("🧪 LFM LAB")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🏃 Svincolati *", "✂️ Tagli Volontari", "📋 Visualizza Rose", "⚙️ Gestione Squadre"])

    # --- DASHBOARD AGGIORNATA ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti, Rimborsi * e Tagli")
        ordine_leghe = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
        leghe_effettive = [l for l in ordine_leghe if l in df_base['Lega'].values]
        
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_effettive):
            with cols[i % 2]:
                st.markdown(f"## 🏆 {nome_lega}")
                df_l = df_base[df_base['Lega'] == nome_lega]
                
                # Calcolo Rimborsi *
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM')['Rimborso_Star'].sum().reset_index()
                # Calcolo Tagli
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM')['Rimborso_Taglio'].sum().reset_index()
                
                df_crediti = df_l[['Squadra_LFM', 'Crediti']].drop_duplicates()
                
                tabella = pd.merge(df_crediti, res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli, on='Squadra_LFM', how='left').fillna(0)
                
                tabella['Totale'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                tabella = tabella.sort_values(by='Squadra_LFM')
                
                bg_color = MAPPATURA_COLORI.get(nome_lega, "#f5f5f5")
                for _, sq in tabella.iterrows():
                    st.markdown(f"""
                        <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #ccc; color: #333;">
                            <h3 style="margin: 0; color: #000; font-size: 24px;">{sq['Squadra_LFM']} — {int(sq['Totale'])} cr</h3>
                            <hr style="margin: 10px 0; border: 0; border-top: 1px solid #999;">
                            <div style="display: flex; justify-content: space-between; font-size: 16px;">
                                <span><b>Residuo:</b> {int(sq['Crediti'])}</span>
                                <span><b>Rimborsi *:</b> {int(sq['Rimborso_Star'])}</span>
                                <span><b>Tagli ✂️:</b> {int(sq['Rimborso_Taglio'])}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    # --- PAGINA SVINCOLATI * (LOGICA PIENA) ---
    elif menu == "🏃 Svincolati *":
        st.title("🏃 Giocatori non più in Serie A (*)")
        cerca = st.text_input("Cerca giocatore da svincolare (Rimborso Pieno):")
        if cerca:
            df_f = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
            edit = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'Squadra_LFM', 'Rimborso_Star', 'Id']], hide_index=True)
            if st.button("Salva Svincoli *"):
                for _, r in edit.iterrows():
                    if r['Rimborsato_Star']: st.session_state.refunded_ids.add(r['Id'])
                    else: st.session_state.refunded_ids.discard(r['Id'])
                st.rerun()

    # --- PAGINA TAGLI VOLONTARI (LOGICA 50%) ---
    elif menu == "✂️ Tagli Volontari":
        st.title("✂️ Tagli Volontari (Rimborso 50%)")
        cerca_t = st.text_input("Cerca giocatore da tagliare (Recupero 50% FVM e Qt.I):")
        if cerca_t:
            df_t = df_base[df_base['Nome'].str.contains(cerca_t, case=False, na=False)].drop_duplicates('Id')
            edit_t = st.data_editor(df_t[['Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'Rimborso_Taglio', 'Id']], hide_index=True)
            if st.button("Salva Tagli"):
                for _, r in edit_t.iterrows():
                    if r['Rimborsato_Taglio']: st.session_state.tagli_ids.add(r['Id'])
                    else: st.session_state.tagli_ids.discard(r['Id'])
                st.rerun()

    # --- VISUALIZZA ROSE AGGIORNATA ---
    elif menu == "📋 Visualizza Rose":
        st.title("📋 Rose e Stato Giocatori")
        squadra_sel = st.selectbox("Seleziona Squadra:", sorted(df_base['Squadra_LFM'].unique()))
        df_r = df_base[df_base['Squadra_LFM'] == squadra_sel].copy()
        
        def check_stato(row):
            if row['Rimborsato_Star']: return "❌ SVINCOLATO *"
            if row['Rimborsato_Taglio']: return "✂️ TAGLIO VOL."
            return "🏃 IN ROSA"
        
        df_r['Stato'] = df_r.apply(check_stato, axis=1)
        st.dataframe(df_r[['Stato', 'Nome', 'R', 'FVM', 'Qt.I']], use_container_width=True, hide_index=True)

    # --- GESTIONE SQUADRE ---
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Setup")
        st.download_button("📥 Scarica database_tagli.csv", pd.DataFrame({'Id': list(st.session_state.tagli_ids), 'Taglio': True}).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
