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
            
            # OUTER JOIN: Include TUTTI i calciatori (anche quelli non posseduti)
            df = pd.merge(df_rose, df_quot, on='Id', how='outer')
            
            # Pulizia per i giocatori senza squadra
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
            squadre = sorted(df_static_init.dropna(subset=['Squadra_LFM'])['Squadra_LFM'].unique())
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

    # --- 🏠 DASHBOARD (Filtra solo rosterati) ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti e Rimborsi")
        df_dash = df_base.dropna(subset=['Squadra_LFM'])
        leghe_effettive = [l for l in ORDINE_LEGHE if l in df_dash['Lega'].values]
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_effettive):
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
                    if sq['Nome']: d_html += f"<div style='font-size:13px;color:#d32f2f;'><b>✈️ Svinc:</b> {sq['Nome']} (+{int(sq['Rimborso_Star'])})</div>"
                    if sq['N_T']: d_html += f"<div style='font-size:13px;color:#7b1fa2;'><b>✂️ Tagli:</b> {sq['N_T']} (+{int(sq['Rimborso_Taglio'])})</div>"
                    st.markdown(f"""<div style="background-color: {MAPPATURA_COLORI.get(nome_lega, '#f5f5f5')}; padding: 15px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #ddd; color: #333;">
                        <div style="display: flex; justify-content: space-between;"><b>{sq['Squadra_LFM']}</b><b style="color:#1e88e5;">{int(sq['Totale'])} cr</b></div>
                        <hr style="margin:8px 0;"><div style="background-color: rgba(255,255,255,0.4); padding: 8px; border-radius: 6px; border: 1px dashed #999;">{d_html if d_html else "<i>Nessuna operazione attiva</i>"}</div></div>""", unsafe_allow_html=True)

    # --- 🏃 SVINCOLATI * (Filtra solo rosterati) ---
    elif menu == "🏃 Svincolati *":
        st.title("✈️ Rimborsi da *")
        df_svinc_base = df_base.dropna(subset=['Squadra_LFM'])
        c1, c2 = st.columns([4, 1])
        cerca = c1.text_input("Cerca giocatore:", key="cerca_star")
        if c2.button("Reset 🔄", key="res_star"): st.rerun()
        if cerca:
            df_f = df_svinc_base[df_svinc_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
            edit = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'R', 'FVM', 'Qt.I', 'Rimborso_Star', 'Id']], column_config={"Rimborsato_Star": "Vola ✈️", "Id": None, "R": "Ruolo", "Qt.I": "Quot."}, hide_index=True, use_container_width=True)
            if st.button("Salva Svincoli *"):
                for _, r in edit.iterrows():
                    if r['Rimborsato_Star']: st.session_state.refunded_ids.add(r['Id'])
                    else: st.session_state.refunded_ids.discard(r['Id'])
                st.rerun()
        st.divider()
        st.dataframe(df_svinc_base[df_svinc_base['Rimborsato_Star']].drop_duplicates('Id').sort_values(by='Nome')[['Nome', 'R', 'Qt.I', 'FVM', 'Rimborso_Star']], use_container_width=True, hide_index=True)

    # --- ✂️ TAGLI VOLONTARI (Filtra solo rosterati) ---
    elif menu == "✂️ Tagli Volontari":
        st.title("✂️ Tagli Volontari")
        df_tagli_base = df_base.dropna(subset=['Squadra_LFM'])
        c1, c2 = st.columns([4, 1])
        cerca_t = c1.text_input("Cerca per squadra:", key="cerca_tagli")
        if c2.button("Reset 🔄", key="res_tagli"): st.rerun()
        if cerca_t:
            df_t = df_tagli_base[df_tagli_base['Nome'].str.contains(cerca_t, case=False, na=False)]
            edit_t = st.data_editor(df_t[['Rimborsato_Taglio', 'Nome', 'R', 'FVM', 'Qt.I', 'Squadra_LFM', 'Rimborso_Taglio', 'Taglio_Key']], column_config={"Taglio_Key": None, "Rimborsato_Taglio": "Taglia ✂️", "R": "Ruolo", "Qt.I": "Quot.", "Squadra_LFM": "Squadra", "Rimborso_Taglio": "Rimborso (50%)"}, hide_index=True, use_container_width=True)
            if st.button("Applica Tagli"):
                for _, r in edit_t.iterrows():
                    if r['Rimborsato_Taglio']: st.session_state.tagli_map.add(r['Taglio_Key'])
                    else: st.session_state.tagli_map.discard(r['Taglio_Key'])
                st.rerun()
        st.divider()
        st.dataframe(df_tagli_base[df_tagli_base['Rimborsato_Taglio']].sort_values(by=['Squadra_LFM', 'Nome'])[['Squadra_LFM', 'Nome', 'R', 'FVM', 'Qt.I', 'Rimborso_Taglio']], use_container_width=True, hide_index=True)

    # --- 📊 RANKING FVM (FIXED: MOSTRA TUTTI) ---
    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM Globale")
        
        c1, c2, c3 = st.columns(3)
        ruolo_filt = c1.multiselect("Filtra Ruolo:", ["P", "D", "C", "A"], default=["P", "D", "C", "A"])
        leghe_filt = c2.multiselect("Visualizza Colonne Leghe:", ORDINE_LEGHE, default=ORDINE_LEGHE)
        solo_liberi = c3.checkbox("Mostra solo LIBERI OVUNQUE", value=False)
        
        df_rank = df_base.copy()
        if ruolo_filt:
            df_rank = df_rank[df_rank['R'].isin(ruolo_filt)]

        def format_owner(row):
            if pd.isna(row['Squadra_LFM']): return "🟢 LIBERO"
            name = row['Squadra_LFM']
            if row['Rimborsato_Star']: return f"✈️ {name}" 
            if row['Rimborsato_Taglio']: return f"✂️ {name}" 
            return name

        df_rank['Display'] = df_rank.apply(format_owner, axis=1)
        
        # Matrice Pivot: Include TUTTI gli ID grazie all'outer join precedente
        pivot_rank = df_rank.pivot_table(
            index=['FVM', 'Nome', 'R', 'Id'], 
            columns='Lega', 
            values='Display', 
            aggfunc=lambda x: " | ".join(str(v) for v in x if str(v) != 'nan'),
            dropna=False
        ).reset_index()

        # Riempire i buchi con 🟢 LIBERO
        for lega in ORDINE_LEGHE:
            if lega in pivot_rank.columns:
                pivot_rank[lega] = pivot_rank[lega].fillna("🟢 LIBERO")
            else:
                pivot_rank[lega] = "🟢 LIBERO"

        if solo_liberi:
            mask = True
            for lega in ORDINE_LEGHE:
                if lega in pivot_rank.columns:
                    mask &= (pivot_rank[lega] == "🟢 LIBERO")
            pivot_rank = pivot_rank[mask]

        pivot_rank = pivot_rank.sort_values(by='FVM', ascending=False)
        colonne_vis = ['FVM', 'Nome', 'R'] + [l for l in leghe_filt if l in pivot_rank.columns]
        
        st.dataframe(
            pivot_rank[colonne_vis],
            column_config={
                "FVM": st.column_config.NumberColumn("FVM", format="%d"),
                "R": "Ruolo",
                **{l: st.column_config.TextColumn(f"🏆 {l}") for l in ORDINE_LEGHE}
            },
            use_container_width=True,
            hide_index=True
        )
        st.info("Legenda: 🟢 LIBERO = Disponibile | ✈️ = Svincolato (*) | ✂️ = Tagliato (50%)")

    # --- 📋 VISUALIZZA ROSE ---
    elif menu == "📋 Visualizza Rose":
        st.title("📋 Consultazione Rose")
        df_rose_base = df_base.dropna(subset=['Squadra_LFM'])
        lega_sel = st.selectbox("Lega:", sorted(df_rose_base['Lega'].unique()))
        squadra_sel = st.selectbox("Squadra:", sorted(df_rose_base[df_rose_base['Lega'] == lega_sel]['Squadra_LFM'].unique()))
        df_r = df_rose_base[df_rose_base['Squadra_LFM'] == squadra_sel].copy()
        ruolo_order = {'P':0, 'D':1, 'C':2, 'A':3}
        df_r['Ruolo_Num'] = df_r['R'].map(ruolo_order).fillna(4)
        df_r['Stato'] = df_r.apply(lambda r: "✈️ SVINC. *" if r['Rimborsato_Star'] else ("✂️ TAGLIO" if r['Rimborsato_Taglio'] else "🏃 ROSA"), axis=1)
        st.dataframe(df_r.sort_values(by=['Rimborsato_Star', 'Rimborsato_Taglio', 'Ruolo_Num', 'Nome'])[['Stato', 'Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    # --- ⚙️ GESTIONE SQUADRE ---
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione")
        c1, c2 = st.columns([4, 1])
        opzioni_lega = ["Tutte"] + sorted(list(st.session_state.df_leghe_full['Lega'].unique()))
        lega_filtro = c1.selectbox("Filtra per lega:", opzioni_lega, key="filtro_lega_gest")
        if c2.button("Reset 🔄", key="res_gest"): st.rerun()
        df_to_edit = st.session_state.df_leghe_full if lega_filtro == "Tutte" else st.session_state.df_leghe_full[st.session_state.df_leghe_full['Lega'] == lega_filtro]
        edited = st.data_editor(df_to_edit, use_container_width=True, hide_index=True)
        if st.button("Salva Modifiche"):
            temp_df = st.session_state.df_leghe_full.copy().set_index('Squadra')
            temp_df.update(edited.set_index('Squadra'))
            st.session_state.df_leghe_full = fix_league_names(temp_df.reset_index()); st.success("Dati aggiornati!"); st.rerun()
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.download_button("database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids), 'Rimborsato': True}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("database_tagli.csv", pd.DataFrame([{'Id': k.split('_')[0], 'Squadra': k.split('_')[1], 'Rimborsato': True} for k in st.session_state.tagli_map]).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")
else: st.error("Carica i file CSV!")
