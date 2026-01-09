import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM LAB - Gestione Avanzata", layout="wide", page_icon="🧪")

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
            
            # CALCOLO RIMBORSI * (Pieno: FVM + Qt.I/2)
            df['Rimborso_Star'] = df['FVM'] + (df['Qt.I'] / 2)
            # CALCOLO TAGLI VOLONTARI (50% di tutto: (FVM + Qt.I)/2)
            df['Rimborso_Taglio'] = (df['FVM'] + df['Qt.I']) / 2
            
            df['Squadra_LFM'] = df['Squadra_LFM'].str.strip()
            return df
        except: continue
    return None

# --- 2. GESTIONE SESSIONE (Caricamento da file) ---
if 'refunded_ids' not in st.session_state:
    try:
        db_p = pd.read_csv('database_lfm.csv')
        st.session_state.refunded_ids = set(db_p['Id'].tolist())
    except: st.session_state.refunded_ids = set()

if 'tagli_ids' not in st.session_state:
    try:
        db_t = pd.read_csv('database_tagli.csv')
        st.session_state.tagli_ids = set(db_t['Id'].tolist())
    except: st.session_state.tagli_ids = set()

if 'df_leghe_full' not in st.session_state:
    try:
        df_temp = pd.read_csv('leghe.csv', encoding='latin1')
        df_temp['Squadra'] = df_temp['Squadra'].str.strip()
        df_temp['Lega'] = df_temp['Lega'].str.strip()
        df_temp['Crediti'] = pd.to_numeric(df_temp['Crediti'], errors='coerce').fillna(0)
        st.session_state.df_leghe_full = df_temp
    except:
        st.session_state.df_leghe_full = pd.DataFrame(columns=['Squadra', 'Lega', 'Crediti'])

# --- 3. UNIFICAZIONE NOMI LEGA ---
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
    # Merge Dati
    df_base = pd.merge(df_static, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Rimborsato_Taglio'] = df_base['Id'].isin(st.session_state.tagli_ids)

    st.sidebar.title("🧪 LFM LAB")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🏃 Svincolati *", "✂️ Tagli Volontari", "📋 Visualizza Rose", "⚙️ Gestione Squadre"])

    # --- DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti e Operazioni")
        ordine_leghe = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
        leghe_effettive = [l for l in ordine_leghe if l in df_base['Lega'].values]
        
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_effettive):
            with cols[i % 2]:
                st.markdown(f"## 🏆 {nome_lega}")
                df_l = df_base[df_base['Lega'] == nome_lega]
                
                # Calcoli aggregati
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                res_star.columns = ['Squadra_LFM', 'Valore_Star', 'Nomi_Star']
                
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                res_tagli.columns = ['Squadra_LFM', 'Valore_Taglio', 'Nomi_Taglio']
                
                df_crediti = df_l[['Squadra_LFM', 'Crediti']].drop_duplicates()
                tabella = pd.merge(df_crediti, res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli, on='Squadra_LFM', how='left').fillna(0)
                
                tabella['Totale'] = tabella['Crediti'] + tabella['Valore_Star'] + tabella['Valore_Taglio']
                tabella = tabella.sort_values(by='Squadra_LFM')
                bg_color = MAPPATURA_COLORI.get(nome_lega, "#f5f5f5")

                for _, sq in tabella.iterrows():
                    d_html = ""
                    if sq['Nomi_Star']: d_html += f"<div style='font-size:13px;color:#d32f2f;'><b>* Svincolati:</b> {sq['Nomi_Star']} (+{int(sq['Valore_Star'])})</div>"
                    if sq['Nomi_Taglio']: d_html += f"<div style='font-size:13px;color:#7b1fa2;'><b>✂️ Tagli Vol.:</b> {sq['Nomi_Taglio']} (+{int(sq['Valore_Taglio'])})</div>"
                    
                    st.markdown(f"""
                        <div style="background-color: {bg_color}; padding: 15px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #ddd; color: #333;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 22px; font-weight: bold;">{sq['Squadra_LFM']}</span>
                                <span style="font-size: 22px; font-weight: bold; color: #1e88e5;">{int(sq['Totale'])} <small>cr</small></span>
                            </div>
                            <hr style="margin: 8px 0;">
                            <div style="display: flex; justify-content: space-between; font-size: 15px; margin-bottom: 8px;">
                                <span><b>Residuo:</b> {int(sq['Crediti'])}</span>
                                <span><b>Extra:</b> {int(sq['Valore_Star'] + sq['Valore_Taglio'])}</span>
                            </div>
                            <div style="background-color: rgba(255,255,255,0.4); padding: 8px; border-radius: 6px; border: 1px dashed #999;">
                                {d_html if d_html else "<i>Nessuna operazione</i>"}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    # --- SVINCOLATI * ---
    elif menu == "🏃 Svincolati *":
        st.title("🏃 Svincolati d'ufficio (Rimborso Pieno)")
        cerca = st.text_input("Cerca giocatore:")
        if cerca:
            df_f = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
            edit = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'Squadra_LFM', 'Rimborso_Star', 'Id']], hide_index=True, use_container_width=True)
            if st.button("Salva Svincoli *"):
                for _, r in edit.iterrows():
                    if r['Rimborsato_Star']: st.session_state.refunded_ids.add(r['Id'])
                    else: st.session_state.refunded_ids.discard(r['Id'])
                st.success("Salvato!"); st.rerun()
        st.divider()
        st.subheader("📋 Elenco Svincolati *")
        df_sv = df_base[df_base['Rimborsato_Star']].drop_duplicates('Id').sort_values(by='Nome')
        st.dataframe(df_sv[['Nome', 'R', 'Qt.I', 'FVM', 'Rimborso_Star']], use_container_width=True, hide_index=True)

    # --- TAGLI VOLONTARI ---
    elif menu == "✂️ Tagli Volontari":
        st.title("✂️ Tagli Volontari (Rimborso 50%)")
        cerca_t = st.text_input("Cerca giocatore da tagliare:")
        if cerca_t:
            df_t = df_base[df_base['Nome'].str.contains(cerca_t, case=False, na=False)].drop_duplicates('Id')
            edit_t = st.data_editor(df_t[['Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'Rimborso_Taglio', 'Id']], hide_index=True, use_container_width=True)
            if st.button("Salva Tagli"):
                for _, r in edit_t.iterrows():
                    if r['Rimborsato_Taglio']: st.session_state.tagli_ids.add(r['Id'])
                    else: st.session_state.tagli_ids.discard(r['Id'])
                st.success("Salvato!"); st.rerun()
        st.divider()
        st.subheader("📋 Elenco Tagli Volontari")
        df_tv = df_base[df_base['Rimborsato_Taglio']].drop_duplicates('Id').sort_values(by='Nome')
        st.dataframe(df_tv[['Nome', 'R', 'Qt.I', 'FVM', 'Rimborso_Taglio']], use_container_width=True, hide_index=True)

    # --- VISUALIZZA ROSE ---
    elif menu == "📋 Visualizza Rose":
        st.title("📋 Rose Complete")
        squadra_sel = st.selectbox("Seleziona Squadra:", sorted(df_base['Squadra_LFM'].unique()))
        df_r = df_base[df_base['Squadra_LFM'] == squadra_sel].copy()
        
        ruolo_order = {'P':0, 'D':1, 'C':2, 'A':3}
        df_r['Ruolo_Num'] = df_r['R'].map(ruolo_order).fillna(4)
        df_r['Stato'] = df_r.apply(lambda r: "❌ SVINC. *" if r['Rimborsato_Star'] else ("✂️ TAGLIO" if r['Rimborsato_Taglio'] else "🏃 ROSA"), axis=1)
        
        df_r = df_r.sort_values(by=['Rimborsato_Star', 'Rimborsato_Taglio', 'Ruolo_Num', 'Nome'])
        st.dataframe(df_r[['Stato', 'Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    # --- GESTIONE SQUADRE ---
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Setup e Download")
        edited = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Applica Modifiche"):
            st.session_state.df_leghe_full = fix_league_names(edited); st.rerun()
        
        st.divider()
        st.download_button("📥 Scarica database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        st.download_button("📥 Scarica database_tagli.csv", pd.DataFrame({'Id': list(st.session_state.tagli_ids)}).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        st.download_button("📥 Scarica leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")

else: st.error("Dati non caricati.")
