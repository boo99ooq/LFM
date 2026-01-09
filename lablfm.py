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
            
            # CALCOLO RIMBORSI * (Pieno: FVM + Qt.I/2)
            df['Rimborso_Star'] = df['FVM'] + (df['Qt.I'] / 2)
            # CALCOLO TAGLI VOLONTARI (50% del totale: (FVM + Qt.I)/2)
            df['Rimborso_Taglio'] = (df['FVM'] + df['Qt.I']) / 2
            
            df['Squadra_LFM'] = df['Squadra_LFM'].str.strip()
            return df
        except: continue
    return None

# --- 2. GESTIONE SESSIONE (Database persistenti) ---
# Svincolati * (Globali)
if 'refunded_ids' not in st.session_state:
    try:
        db_p = pd.read_csv('database_lfm.csv')
        st.session_state.refunded_ids = set(db_p['Id'].tolist())
    except: st.session_state.refunded_ids = set()

# Tagli Volontari (Selettivi: Id + Squadra)
if 'tagli_map' not in st.session_state:
    try:
        db_t = pd.read_csv('database_tagli.csv')
        db_t['Key'] = db_t['Id'].astype(str) + "_" + db_t['Squadra'].astype(str)
        st.session_state.tagli_map = set(db_t['Key'].tolist())
    except: st.session_state.tagli_map = set()

# Leghe e Crediti Residui
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

# --- 3. FIX NOMI LEGA ---
def fix_league_names(df_leghe):
    df = df_leghe.copy()
    df['Lega'] = df['Lega'].replace(['Lega A', 'nan', 'Da Assegnare'], 'Serie A')
    df.loc[df['Squadra'].str.contains("Fiorentina", case=False, na=False), 'Lega'] = "Serie A"
    return df

st.session_state.df_leghe_full = fix_league_names(st.session_state.df_leghe_full)

MAPPATURA_COLORI = {
    "Serie A": "#fce4ec", "Bundesliga": "#e8f5e9", "Premier League": "#e3f2fd", "Liga BBVA": "#fffde7"
}

# --- 4. COSTRUZIONE INTERFACCIA ---
df_static = load_static_data()
if df_static is not None:
    # Merge Dati Base
    df_base = pd.merge(df_static, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    
    # Checkbox Stato
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Admin")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🏃 Svincolati *", "✂️ Tagli Volontari", "📋 Visualizza Rose", "⚙️ Gestione Squadre"])

    # --- DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti e Rimborsi")
        ordine_leghe = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
        leghe_effettive = [l for l in ordine_leghe if l in df_base['Lega'].values]
        
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_effettive):
            with cols[i % 2]:
                st.markdown(f"## 🏆 {nome_lega}")
                df_l = df_base[df_base['Lega'] == nome_lega]
                
                # Raggruppamento Svincolati *
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                res_star.columns = ['Squadra_LFM', 'Val_Star', 'Nomi_Star']
                
                # Raggruppamento Tagli ✂️
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                res_tagli.columns = ['Squadra_LFM', 'Val_Taglio', 'Nomi_Taglio']
                
                df_crediti = df_l[['Squadra_LFM', 'Crediti']].drop_duplicates()
                tabella = pd.merge(df_crediti, res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli, on='Squadra_LFM', how='left').fillna(0)
                
                tabella['Totale'] = tabella['Crediti'] + tabella['Val_Star'] + tabella['Val_Taglio']
                tabella = tabella.sort_values(by='Squadra_LFM')
                bg_color = MAPPATURA_COLORI.get(nome_lega, "#f5f5f5")

                for _, sq in tabella.iterrows():
                    d_html = ""
                    if sq['Nomi_Star']: d_html += f"<div style='font-size:13px;color:#d32f2f;'><b>* Svincolati:</b> {sq['Nomi_Star']} (+{int(sq['Val_Star'])})</div>"
                    if sq['Nomi_Taglio']: d_html += f"<div style='font-size:13px;color:#7b1fa2;'><b>✂️ Tagli Vol.:</b> {sq['Nomi_Taglio']} (+{int(sq['Val_Taglio'])})</div>"
                    
                    st.markdown(f"""
                        <div style="background-color: {bg_color}; padding: 15px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #ddd; color: #333;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 20px; font-weight: bold;">{sq['Squadra_LFM']}</span>
                                <span style="font-size: 22px; font-weight: bold; color: #1e88e5;">{int(sq['Totale'])} <small>cr</small></span>
                            </div>
                            <hr style="margin: 8px 0;">
                            <div style="display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 8px;">
                                <span><b>Residuo:</b> {int(sq['Crediti'])}</span>
                                <span><b>Rimborsi Extra:</b> {int(sq['Val_Star'] + sq['Val_Taglio'])}</span>
                            </div>
                            <div style="background-color: rgba(255,255,255,0.4); padding: 8px; border-radius: 6px; border: 1px dashed #999;">
                                {d_html if d_html else "<i>Nessuna operazione attiva</i>"}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

    # --- SVINCOLATI * (Globali) ---
    elif menu == "🏃 Svincolati *":
        st.title("🏃 Rimborsi da * (Non più in Serie A)")
        st.info("Nota: Svincolare un giocatore qui lo rimuove da TUTTE le squadre (Rimborso Pieno).")
        cerca = st.text_input("Cerca giocatore:")
        if cerca:
            df_f = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
            edit = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'Rimborso_Star', 'Id']], 
                                  column_config={"Rimborsato_Star": "Svincola", "Id": None},
                                  hide_index=True, use_container_width=True)
            if st.button("Salva Svincoli *"):
                for _, r in edit.iterrows():
                    if r['Rimborsato_Star']: st.session_state.refunded_ids.add(r['Id'])
                    else: st.session_state.refunded_ids.discard(r['Id'])
                st.success("Database aggiornato!"); st.rerun()
        st.divider()
        st.subheader("📋 Elenco Giocatori Svincolati *")
        df_sv = df_base[df_base['Rimborsato_Star']].drop_duplicates('Id').sort_values(by='Nome')
        st.dataframe(df_sv[['Nome', 'R', 'Qt.I', 'FVM', 'Rimborso_Star']], use_container_width=True, hide_index=True)

    # --- TAGLI VOLONTARI (Selettivi) ---
    elif menu == "✂️ Tagli Volontari":
        st.title("✂️ Tagli Volontari (Rimborso 50%)")
        st.info("In questa pagina selezioni la squadra specifica che effettua il taglio.")
        cerca_t = st.text_input("Cerca nome giocatore (es. Martinez L.):")
        if cerca_t:
            df_t = df_base[df_base['Nome'].str.contains(cerca_t, case=False, na=False)]
            edit_t = st.data_editor(df_t[['Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'Rimborso_Taglio', 'Taglio_Key']], 
                                    column_config={"Taglio_Key": None, "Rimborsato_Taglio": "Taglia"},
                                    hide_index=True, use_container_width=True)
            if st.button("Applica Tagli Selettivi"):
                for _, r in edit_t.iterrows():
                    if r['Rimborsato_Taglio']: st.session_state.tagli_map.add(r['Taglio_Key'])
                    else: st.session_state.tagli_map.discard(r['Taglio_Key'])
                st.success("Tagli applicati alle squadre selezionate!"); st.rerun()
        st.divider()
        st.subheader("📋 Riepilogo Tagli Attivi")
        df_tv = df_base[df_base['Rimborsato_Taglio']].sort_values(by=['Squadra_LFM', 'Nome'])
        st.dataframe(df_tv[['Squadra_LFM', 'Nome', 'R', 'Rimborso_Taglio']], use_container_width=True, hide_index=True)

    # --- VISUALIZZA ROSE (Ordinamento P-D-C-A) ---
    elif menu == "📋 Visualizza Rose":
        st.title("📋 Consultazione Rose")
        lega_sel = st.selectbox("Seleziona Lega:", sorted(df_base['Lega'].unique()))
        squadra_sel = st.selectbox("Seleziona Squadra:", sorted(df_base[df_base['Lega'] == lega_sel]['Squadra_LFM'].unique()))
        df_r = df_base[df_base['Squadra_LFM'] == squadra_sel].copy()
        
        ruolo_order = {'P':0, 'D':1, 'C':2, 'A':3}
        df_r['Ruolo_Num'] = df_r['R'].map(ruolo_order).fillna(4)
        df_r['Stato'] = df_r.apply(lambda r: "❌ SVINC. *" if r['Rimborsato_Star'] else ("✂️ TAGLIO" if r['Rimborsato_Taglio'] else "🏃 IN ROSA"), axis=1)
        
        df_r = df_r.sort_values(by=['Rimborsato_Star', 'Rimborsato_Taglio', 'Ruolo_Num', 'Nome'])
        st.dataframe(df_r[['Stato', 'Nome', 'R', 'Qt.I', 'FVM']], 
                     column_config={"R": "Ruolo"}, use_container_width=True, hide_index=True)

    # --- GESTIONE SQUADRE (Salvataggio permanente) ---
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione e Backup")
        edited = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Salva Modifiche Leghe"):
            st.session_state.df_leghe_full = fix_league_names(edited)
            st.success("Leghe aggiornate!"); st.rerun()
        
        st.divider()
        st.subheader("📥 Scarica File per GitHub")
        st.write("Usa questi tasti per scaricare i file e caricarli manualmente sul tuo repository GitHub.")
        
        # Preparazione CSV per Tagli (Id, Squadra)
        tagli_list = []
        for key in st.session_state.tagli_map:
            pid, psq = key.split("_")
            tagli_list.append({'Id': pid, 'Squadra': psq, 'Rimborsato': True})
        
        c1, c2, c3 = st.columns(3)
        c1.download_button("Scarica database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids), 'Rimborsato': True}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("Scarica database_tagli.csv", pd.DataFrame(tagli_list).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("Scarica leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")

else: st.error("Errore: File CSV non trovati nella cartella principale.")
