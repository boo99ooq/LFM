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
            df_owned = pd.merge(df_rose, df_quot, on='Id', how='left')
            df_owned['Nome'] = df_owned['Nome'].fillna("ID: " + df_owned['Id'].astype(int, errors='ignore').astype(str))
            df_owned['Qt.I'] = pd.to_numeric(df_owned['Qt.I'], errors='coerce').fillna(0)
            df_owned['FVM'] = pd.to_numeric(df_owned['FVM'], errors='coerce').fillna(0)
            df_owned['Squadra_LFM'] = df_owned['Squadra_LFM'].str.strip()
            
            df_owned['Rimborso_Star'] = df_owned['FVM'] + (df_owned['Qt.I'] / 2)
            df_owned['Rimborso_Taglio'] = (df_owned['FVM'] + df_owned['Qt.I']) / 2
            
            return df_owned, df_quot
        except: continue
    return None, None

# --- 2. MAPPATURA COLORI BRANDING ---
MAPPATURA_COLORI = {
    "Serie A": "#00529b", 
    "Bundesliga": "#d3010c", 
    "Premier League": "#3d195b", 
    "Liga BBVA": "#ee8707"
}

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
        st.session_state.df_leghe_full = pd.DataFrame(columns=['Squadra', 'Lega', 'Crediti'])

def fix_league_names(df_leghe):
    df = df_leghe.copy()
    df['Lega'] = df['Lega'].replace(['Lega A', 'nan', 'Da Assegnare'], 'Serie A')
    df.loc[df['Squadra'].str.contains("Fiorentina", case=False, na=False), 'Lega'] = "Serie A"
    return df

st.session_state.df_leghe_full = fix_league_names(st.session_state.df_leghe_full)
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]

# --- 3. COSTRUZIONE DATI ---
df_base, df_all_quot = load_static_data()

if df_base is not None:
    df_base = pd.merge(df_base, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Admin")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🏃 Svincolati *", "✂️ Tagli Volontari", "📊 Ranking FVM", "📋 Visualizza Rose", "🟢 Giocatori Liberi", "⚙️ Gestione Squadre"])

    # --- 🏠 DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti e News")
        
        st.info("📢 **Bacheca News & Alert**")
        st.markdown("* ⚠️ **Alert Rose:** Il contatore diventa rosso se la rosa ha meno di 25 o più di 35 giocatori.")
        
        st.subheader("🔄 Ultimi Movimenti")
        news_star = df_base[df_base['Rimborsato_Star']].copy()
        news_star['Tipo'] = "✈️ SVINC *"
        news_tagli = df_base[df_base['Rimborsato_Taglio']].copy()
        news_tagli['Tipo'] = "✂️ TAGLIO"
        movimenti = pd.concat([news_star, news_tagli])
        
        if not movimenti.empty:
            for _, mov in movimenti.head(5).iterrows():
                st.write(f"**{mov['Tipo']}**: {mov['Nome']} ({mov['Squadra_LFM']})")
        else:
            st.write("*Nessun movimento recente.*")
        
        st.divider()

        leghe_effettive = [l for l in ORDINE_LEGHE if l in df_base['Lega'].values]
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_effettive):
            with cols[i % 2]:
                st.markdown(f"## 🏆 {nome_lega}")
                df_l = df_base[df_base['Lega'] == nome_lega]
                
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                
                # Conteggio attivi
                attivi = df_l[~(df_l['Rimborsato_Star']) & ~(df_l['Rimborsato_Taglio'])].groupby('Squadra_LFM').size().reset_index(name='Num_Giocatori')
                
                tabella = pd.merge(df_l[['Squadra_LFM', 'Crediti']].drop_duplicates(), res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli.rename(columns={'Nome':'N_T'}), on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, attivi, on='Squadra_LFM', how='left').fillna(0)
                tabella['Totale'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                
                bg_color = MAPPATURA_COLORI.get(nome_lega, "#f5f5f5")
                
                for _, sq in tabella.sort_values(by='Squadra_LFM').iterrows():
                    d_html = ""
                    if sq['Nome']: d_html += f"<div style='font-size:12px;color:#ffcdd2;'><b>✈️ Svinc:</b> {sq['Nome']} (+{int(sq['Rimborso_Star'])})</div>"
                    if sq['N_T']: d_html += f"<div style='font-size:12px;color:#e1bee7;'><b>✂️ Tagli:</b> {sq['N_T']} (+{int(sq['Rimborso_Taglio'])})</div>"
                    
                    # LOGICA ALERT: Rosso se fuori dal range [25, 35]
                    n_g = int(sq['Num_Giocatori'])
                    if 25 <= n_g <= 35:
                        colore_count = "#81c784" # Verde
                        icona = "🏃"
                    else:
                        colore_count = "#ef5350" # Rosso
                        icona = "⚠️" if n_g > 35 else "🏃"
                    
                    st.markdown(f"""<div style="background-color: {bg_color}; padding: 15px; border-radius: 12px; margin-bottom: 12px; border: 1px solid rgba(255,255,255,0.2); color: white;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <b style="font-size:16px; color: white;">{sq['Squadra_LFM']}</b>
                            <span style="background:{colore_count}; color:white; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:bold;">
                                {icona} {n_g}/25-35
                            </span>
                        </div>
                        <div style="font-size:20px; font-weight:bold; color: #ffffff; margin-top:5px;">{int(sq['Totale'])} <small style="font-size:12px; opacity:0.8;">cr</small></div>
                        <hr style="margin:8px 0; opacity:0.3;">
                        <div style="background-color: rgba(0,0,0,0.2); padding: 8px; border-radius: 6px;">
                            {d_html if d_html else "<i style='color:rgba(255,255,255,0.5); font-size:12px;'>Nessuna operazione attiva</i>"}
                        </div>
                    </div>""", unsafe_allow_html=True)

    # --- LE ALTRE PAGINE RIMANGONO UGUALI ---
    elif menu == "🏃 Svincolati *":
        st.title("✈️ Rimborsi da *")
        c1, c2 = st.columns([4, 1])
        cerca = c1.text_input("Cerca giocatore:", key="cerca_star")
        if c2.button("Reset 🔄"): st.rerun()
        if cerca:
            df_f = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
            edit = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'R', 'FVM', 'Qt.I', 'Rimborso_Star', 'Id']], column_config={"Rimborsato_Star": "Vola ✈️", "Id": None}, hide_index=True, use_container_width=True)
            if st.button("Salva Svincoli *"):
                for _, r in edit.iterrows():
                    if r['Rimborsato_Star']: st.session_state.refunded_ids.add(r['Id'])
                    else: st.session_state.refunded_ids.discard(r['Id'])
                st.rerun()
        st.divider()
        st.dataframe(df_base[df_base['Rimborsato_Star']].drop_duplicates('Id').sort_values(by='Nome')[['Nome', 'R', 'Qt.I', 'FVM', 'Rimborso_Star']], use_container_width=True, hide_index=True)

    elif menu == "✂️ Tagli Volontari":
        st.title("✂️ Tagli Volontari")
        c1, c2 = st.columns([4, 1])
        cerca_t = c1.text_input("Cerca giocatore o squadra:", key="cerca_tagli")
        if c2.button("Reset 🔄"): st.rerun()
        if cerca_t:
            df_t = df_base[df_base['Nome'].str.contains(cerca_t, case=False, na=False) | df_base['Squadra_LFM'].str.contains(cerca_t, case=False, na=False)]
            edit_t = st.data_editor(df_t[['Rimborsato_Taglio', 'Nome', 'R', 'FVM', 'Qt.I', 'Squadra_LFM', 'Rimborso_Taglio', 'Taglio_Key']], column_config={"Taglio_Key": None, "Rimborsato_Taglio": "Taglia ✂️"}, hide_index=True, use_container_width=True)
            if st.button("Applica Tagli"):
                for _, r in edit_t.iterrows():
                    if r['Rimborsato_Taglio']: st.session_state.tagli_map.add(r['Taglio_Key'])
                    else: st.session_state.tagli_map.discard(r['Taglio_Key'])
                st.rerun()
        st.divider()
        st.dataframe(df_base[df_base['Rimborsato_Taglio']].sort_values(by=['Squadra_LFM', 'Nome'])[['Squadra_LFM', 'Nome', 'R', 'FVM', 'Qt.I', 'Rimborso_Taglio']], use_container_width=True, hide_index=True)

    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM")
        c1, c2 = st.columns(2)
        ruoli_dispo = sorted(df_base['R'].dropna().unique())
        ruolo_filt = c1.multiselect("Ruolo:", ruoli_dispo, default=ruoli_dispo)
        leghe_filt = c2.multiselect("Leghe:", ORDINE_LEGHE, default=ORDINE_LEGHE)
        df_rank = df_base.copy()
        if ruolo_filt: df_rank = df_rank[df_rank['R'].isin(ruolo_filt)]
        def format_owner(row):
            name = row['Squadra_LFM']
            if row['Rimborsato_Star']: return f"✈️ {name}" 
            if row['Rimborsato_Taglio']: return f"✂️ {name}" 
            return name
        df_rank['Squadra_Display'] = df_rank.apply(format_owner, axis=1)
        pivot_rank = df_rank.pivot_table(index=['FVM', 'Nome', 'R'], columns='Lega', values='Squadra_Display', aggfunc=lambda x: " | ".join(x)).reset_index()
        for lega in ORDINE_LEGHE:
            if lega in pivot_rank.columns: pivot_rank[lega] = pivot_rank[lega].fillna("🟢 LIBERO")
            else: pivot_rank[lega] = "🟢 LIBERO"
        st.dataframe(pivot_rank.sort_values(by='FVM', ascending=False)[['FVM', 'Nome', 'R'] + [l for l in leghe_filt if l in pivot_rank.columns]], use_container_width=True, hide_index=True)

    elif menu == "🟢 Giocatori Liberi":
        st.title("🟢 Calciatori Liberi")
        try:
            df_esclusi = pd.read_csv('esclusi.csv', sep='\t', header=None)
            blacklisted_ids = set(pd.to_numeric(df_esclusi.iloc[:, 0], errors='coerce').dropna().unique())
        except: blacklisted_ids = set()
        ids_posseduti = set(df_base['Id'].unique())
        df_liberi = df_all_quot[(~df_all_quot['Id'].isin(ids_posseduti)) & (~df_all_quot['Id'].isin(blacklisted_ids))].copy()
        r_sel = st.multiselect("Filtra Ruolo:", sorted(df_liberi['R'].dropna().unique()), default=sorted(df_liberi['R'].dropna().unique()))
        if r_sel: df_liberi = df_liberi[df_liberi['R'].isin(r_sel)]
        st.dataframe(df_liberi.sort_values(by='FVM', ascending=False)[['Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    elif menu == "📋 Visualizza Rose":
        st.title("📋 Consultazione Rose")
        lega_sel = st.selectbox("Lega:", sorted(df_base['Lega'].unique()))
        squadra_sel = st.selectbox("Squadra:", sorted(df_base[df_base['Lega'] == lega_sel]['Squadra_LFM'].unique()))
        df_r = df_base[df_base['Squadra_LFM'] == squadra_sel].copy()
        df_r['Stato'] = df_r.apply(lambda r: "✈️ SVINC" if r['Rimborsato_Star'] else ("✂️ TAGLIO" if r['Rimborsato_Taglio'] else "🏃 ROSA"), axis=1)
        st.dataframe(df_r.sort_values(by=['Rimborsato_Star', 'Rimborsato_Taglio', 'Nome'])[['Stato', 'Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione")
        edited = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Salva Modifiche"):
            st.session_state.df_leghe_full = fix_league_names(edited); st.success("Dati aggiornati!"); st.rerun()
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.download_button("database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("database_tagli.csv", pd.DataFrame([{'Id': k.split('_')[0], 'Squadra': k.split('_')[1]} for k in st.session_state.tagli_map]).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")
else: st.error("Carica i file CSV!")
