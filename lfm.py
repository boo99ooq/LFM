import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM LAB", layout="wide", page_icon="🧪")

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
            df['Rimborso'] = df['FVM'] + (df['Qt.I'] / 2)
            df['Squadra_LFM'] = df['Squadra_LFM'].str.strip()
            return df
        except: continue
    return None

# --- 2. GESTIONE SESSIONE ---
if 'refunded_ids' not in st.session_state:
    try:
        db_p = pd.read_csv('database_lfm.csv')
        st.session_state.refunded_ids = set(db_p[db_p['Rimborsato'] == True]['Id'].tolist())
    except: st.session_state.refunded_ids = set()

if 'df_leghe_full' not in st.session_state:
    try:
        df_temp = pd.read_csv('leghe.csv', encoding='latin1')
        df_temp['Squadra'] = df_temp['Squadra'].astype(str).str.strip()
        df_temp['Lega'] = df_temp['Lega'].astype(str).str.strip()
        df_temp['Crediti'] = pd.to_numeric(df_temp['Crediti'], errors='coerce').fillna(0)
        st.session_state.df_leghe_full = df_temp
    except:
        df_static_init = load_static_data()
        if df_static_init is not None:
            squadre = sorted(df_static_init['Squadra_LFM'].unique())
            st.session_state.df_leghe_full = pd.DataFrame({'Squadra': squadre, 'Lega': 'Da Assegnare', 'Crediti': 0})

# --- 3. CORREZIONE FORZATA (IL FIX) ---
def fix_league_names(df_leghe):
    df = df_leghe.copy()
    # Tutto ciò che è "Lega A" o "Da Assegnare" o vuoto lo portiamo in "Serie A" per prova
    df['Lega'] = df['Lega'].replace(['Lega A', 'nan', '', 'None', 'Da Assegnare'], 'Serie A')
    # Forza la Fiorentina
    df.loc[df['Squadra'].str.contains("Fiorentina", case=False, na=False), 'Lega'] = "Serie A"
    return df

st.session_state.df_leghe_full = fix_league_names(st.session_state.df_leghe_full)

MAPPATURA_COLORI = {
    "Serie A": "#fce4ec", "Bundesliga": "#e8f5e9", "Premier League": "#e3f2fd", "Liga BBVA": "#fffde7"
}

# --- 4. COSTRUZIONE ---
df_static = load_static_data()
if df_static is not None:
    # Merge finale
    df_base = pd.merge(df_static, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato'] = df_base['Id'].isin(st.session_state.refunded_ids)

    st.sidebar.title("🧪 LFM LAB")
    menu = st.sidebar.radio("Navigazione:", ["🏠 Dashboard", "🏃 Giocatori Svincolati", "📋 Visualizza Rose", "⚙️ Gestione Squadre"])

    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti e Rimborsi")
        
        # Prendiamo TUTTE le leghe presenti nel file per non perdere nessuno
        leghe_nel_file = sorted(df_base['Lega'].unique().tolist())
        
        cols_container = st.columns(2)
        for i, nome_lega in enumerate(leghe_nel_file):
            with cols_container[i % 2]:
                st.markdown(f"## 🏆 {nome_lega}")
                df_l = df_base[df_base['Lega'] == nome_lega]
                
                # Calcoli
                df_rimb_active = df_l[df_l['Rimborsato'] == True]
                res_rimborsi = df_rimb_active.groupby('Squadra_LFM')['Rimborso'].sum().reset_index()
                res_nomi = df_rimb_active.groupby('Squadra_LFM')['Nome'].apply(lambda x: ", ".join(x)).reset_index()
                res_nomi.columns = ['Squadra_LFM', 'Dettaglio']
                
                df_crediti = df_l[['Squadra_LFM', 'Crediti']].drop_duplicates()
                tabella = pd.merge(df_crediti, res_rimborsi, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_nomi, on='Squadra_LFM', how='left').fillna("")
                tabella['Totale'] = tabella['Crediti'] + tabella['Rimborso']
                tabella = tabella.sort_values(by='Squadra_LFM')

                bg_color = MAPPATURA_COLORI.get(nome_lega, "#f5f5f5") # Grigio se non mappata

                for _, sq in tabella.iterrows():
                    st.markdown(f"""
                        <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #ccc; color: #333;">
                            <h3 style="margin: 0; color: #000; font-size: 24px;">{sq['Squadra_LFM']} — {int(sq['Totale'])} cr</h3>
                            <hr style="margin: 10px 0; border: 0; border-top: 1px solid #999;">
                            <div style="display: flex; justify-content: space-between; font-size: 18px;">
                                <span><b>Residuo:</b> {int(sq['Crediti'])}</span>
                                <span><b>Rimborsi:</b> {int(sq['Rimborso'])}</span>
                            </div>
                            <div style="margin-top: 10px; font-size: 15px; font-style: italic; color: #555;">
                                {f"📝 {sq['Dettaglio']}" if sq['Dettaglio'] else "Nessun rimborso attivo"}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    # --- LE ALTRE PAGINE RIMANGONO IDENTICHE MA USANO IL FIX ---
    elif menu == "🏃 Giocatori Svincolati":
        st.title("🏃 Gestione Giocatori Svincolati")
        cerca = st.text_input("Cerca nome giocatore:")
        if cerca:
            df_filtered = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
            res_editor = st.data_editor(df_filtered[['Rimborsato', 'Nome', 'R', 'Rimborso', 'Id']], hide_index=True)
            if st.button("Salva"):
                for _, row in res_editor.iterrows():
                    if row['Rimborsato']: st.session_state.refunded_ids.add(row['Id'])
                    else: st.session_state.refunded_ids.discard(row['Id'])
                st.rerun()

    elif menu == "📋 Visualizza Rose":
        st.title("📋 Consultazione Rose")
        lega_sel = st.selectbox("Lega:", sorted(df_base['Lega'].unique()))
        squadra_sel = st.selectbox("Squadra:", sorted(df_base[df_base['Lega'] == lega_sel]['Squadra_LFM'].unique()))
        df_rosa = df_base[df_base['Squadra_LFM'] == squadra_sel].copy()
        df_rosa['Stato'] = df_rosa['Rimborsato'].apply(lambda x: "✅ RIMB." if x else "🏃")
        st.dataframe(df_rosa[['Stato', 'Nome', 'R', 'Rimborso']], use_container_width=True, hide_index=True)

    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione")
        st.write("Qui puoi correggere manualmente la Lega per ogni squadra se vedi ancora errori.")
        edited = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Applica"):
            st.session_state.df_leghe_full = edited
            st.rerun()

else: st.error("Carica i file CSV!")
