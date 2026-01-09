import streamlit as st
import pandas as pd
import math
import os

st.set_page_config(page_title="LFM Manager - Pro Edition", layout="wide", page_icon="⚖️")

# --- 1. CARICAMENTO DATI BASE ---
@st.cache_data
def load_static_data():
    try:
        # Caricamento rose e quotazioni con codifica latin1 per sicurezza
        df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding='latin1')
        df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
        df_quot = pd.read_csv('quot.csv', encoding='latin1')
        df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
        df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
        df_rose = df_rose.dropna(subset=['Id'])
        df_owned = pd.merge(df_rose, df_quot, on='Id', how='left')
        df_owned['Nome'] = df_owned['Nome'].fillna("ID: " + df_owned['Id'].astype(int, errors='ignore').astype(str))
        df_owned['Qt.I'] = pd.to_numeric(df_owned['Qt.I'], errors='coerce').fillna(0)
        df_owned['FVM'] = pd.to_numeric(df_owned['FVM'], errors='coerce').fillna(0)
        df_owned['Squadra_LFM'] = df_owned['Squadra_LFM'].str.strip()
        
        # Calcolo Rimborsi
        df_owned['Rimborso_Star'] = df_owned['FVM'] + (df_owned['Qt.I'] / 2)
        df_owned['Rimborso_Taglio'] = (df_owned['FVM'] + df_owned['Qt.I']) / 2
        
        return df_owned, df_quot
    except: return None, None

def calculate_stadium_bonus(capienza):
    casa = capienza / 20
    # Arrotondamento per difetto allo 0.5 più vicino
    trasferta = math.floor((casa / 2) * 2) / 2
    return casa, trasferta

# --- 2. GESTIONE SESSIONE & FILE ---
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

# Caricamento Leghe e Stadi
try:
    df_leghe = pd.read_csv('leghe.csv', encoding='latin1')
    df_leghe['Squadra'] = df_leghe['Squadra'].str.strip()
except: df_leghe = pd.DataFrame(columns=['Squadra', 'Lega', 'Crediti'])

try:
    df_stadi = pd.read_csv('stadi.csv', encoding='latin1')
    df_stadi['Squadra'] = df_stadi['Squadra'].str.strip()
except: df_stadi = pd.DataFrame(columns=['Squadra', 'Lega', 'Stadio'])

# --- 3. COSTRUZIONE INTERFACCIA ---
df_base, df_all_quot = load_static_data()

if df_base is not None:
    df_base = pd.merge(df_base, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Manager Pro")
    menu = st.sidebar.radio("Vai a:", [
        "🏠 Dashboard", 
        "🗓️ Calendari Campionati", 
        "🏃 Gestione Mercato", 
        "📊 Ranking FVM", 
        "📋 Rose Complete", 
        "🟢 Giocatori Liberi", 
        "⚙️ Gestione & Backup"
    ])

    # --- 🏠 DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Leghe & Media Crediti")
        ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
        MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
        
        leghe_presenti = [l for l in ORDINE_LEGHE if l in df_base['Lega'].values]
        cols = st.columns(2)
        
        for i, nome_lega in enumerate(leghe_presenti):
            with cols[i % 2]:
                df_l = df_base[df_base['Lega'] == nome_lega]
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum'}).reset_index()
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum'}).reset_index()
                attivi = df_l[~(df_l['Rimborsato_Star']) & ~(df_l['Rimborsato_Taglio'])].groupby('Squadra_LFM').size().reset_index(name='NG')
                
                tabella = pd.merge(df_l[['Squadra_LFM', 'Crediti']].drop_duplicates(), res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, attivi, on='Squadra_LFM', how='left').fillna(0)
                tabella['Totale'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                
                st.markdown(f"### 🏆 {nome_lega} (Media: {int(tabella['Totale'].mean())} cr)")
                
                for _, sq in tabella.sort_values(by='Squadra_LFM').iterrows():
                    n_g = int(sq['NG'])
                    col_alert = "#81c784" if 25 <= n_g <= 35 else "#ef5350"
                    bg_color = MAPPATURA_COLORI.get(nome_lega, "#333")
                    st.markdown(f"""<div style="background-color: {bg_color}; padding: 12px; border-radius: 10px; margin-bottom: 8px; color: white; border: 1px solid rgba(255,255,255,0.1);">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <b>{sq['Squadra_LFM']}</b>
                            <span style="background:{col_alert}; padding:1px 8px; border-radius:8px; font-size:10px;">🏃 {n_g}/25-35</span>
                        </div>
                        <div style="font-size:18px; font-weight:bold;">{int(sq['Totale'])} <small style="font-size:10px;">cr</small></div>
                    </div>""", unsafe_allow_html=True)

    # --- 🗓️ CALENDARI CAMPIONATI ---
    elif menu == "🗓️ Calendari Campionati":
        st.title("🗓️ Centrale Calendari & Bonus Stadio")
        
        # Trova file calendari
        files_cal = [f for f in os.listdir('.') if f.startswith("Calendario_") and f.endswith(".csv")]
        
        if not files_cal:
            st.warning("Carica i file CSV dei calendari (es: Calendario_SERIE-A.csv)")
        else:
            # Creiamo un dizionario {Nome Pulito: Nome File Originale}
            mappa_nomi = {f.replace("Calendario_", "").replace(".csv", "").replace("-", " "): f for f in files_cal}
            nome_pulito_scelto = st.selectbox("Seleziona Campionato:", sorted(mappa_nomi.keys()))
            camp_scelto = mappa_nomi[nome_pulito_scelto]
            
            try:
                # Caricamento con latin1 per gestire simboli come ª
                df_cal = pd.read_csv(camp_scelto, header=None, encoding='latin1')
                giornate = sorted(list(set(
                    [str(x) for x in df_cal[0].dropna() if "Giornata" in str(x)] + 
                    [str(x) for x in df_cal[6].dropna() if "Giornata" in str(x)]
                )))
                
                sel_g = st.selectbox("Seleziona Giornata:", giornate)
                match_list = []
                for r in range(len(df_cal)):
                    for c in [0, 6]:
                        if str(df_cal.iloc[r, c]) == sel_g:
                            for i in range(1, 6):
                                if r+i < len(df_cal):
                                    h, a = str(df_cal.iloc[r+i, c]).strip(), str(df_cal.iloc[r+i, c+3]).strip()
                                    sh = str(df_cal.iloc[r+i, c+1]).replace('"', '').replace(',', '.').strip()
                                    sa = str(df_cal.iloc[r+i, c+2]).replace('"', '').replace(',', '.').strip()
                                    try:
                                        if float(sh) == 0 and float(sa) == 0:
                                            cap_h = df_stadi[df_stadi['Squadra']==h]['Stadio'].values[0] if h in df_stadi['Squadra'].values else 0
                                            cap_a = df_stadi[df_stadi['Squadra']==a]['Stadio'].values[0] if a in df_stadi['Squadra'].values else 0
                                            bh, _ = calculate_stadium_bonus(cap_h)
                                            _, ba = calculate_stadium_bonus(cap_a)
                                            match_list.append({"Partita": f"{h} vs {a}", "Bonus Casa": f"+{bh}", "Bonus Fuori": f"+{ba}"})
                                    except: continue
                if match_list: 
                    st.table(pd.DataFrame(match_list))
                else: 
                    st.info("Tutte le partite di questa giornata sono state giocate.")
            except Exception as e: st.error(f"Errore nella lettura del file: {e}")

    # --- 🏃 GESTIONE MERCATO ---
    elif menu == "🏃 Gestione Mercato":
        st.title("🏃 Operazioni Mercato")
        t1, t2 = st.tabs(["✈️ Svincoli * (100%)", "✂️ Tagli (50%)"])
        
        with t1:
            cerca = st.text_input("Cerca giocatore per svincolo (*):")
            if cerca:
                df_f = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
                ed = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'Squadra_LFM', 'FVM', 'Qt.I', 'Id']], hide_index=True)
                if st.button("Conferma Svincoli"):
                    for _, r in ed.iterrows():
                        if r['Rimborsato_Star']: st.session_state.refunded_ids.add(r['Id'])
                        else: st.session_state.refunded_ids.discard(r['Id'])
                    st.rerun()

        with t2:
            cerca_t = st.text_input("Cerca per Taglio Tecnico:")
            if cerca_t:
                df_t = df_base[df_base['Nome'].str.contains(cerca_t, case=False, na=False) | df_base['Squadra_LFM'].str.contains(cerca_t, case=False, na=False)]
                ed_t = st.data_editor(df_t[['Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'FVM', 'Taglio_Key']], hide_index=True)
                if st.button("Conferma Tagli"):
                    for _, r in ed_t.iterrows():
                        if r['Rimborsato_Taglio']: st.session_state.tagli_map.add(r['Taglio_Key'])
                        else: st.session_state.tagli_map.discard(r['Taglio_Key'])
                    st.rerun()

    # --- 📊 RANKING FVM ---
    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM")
        df_rank = df_base.copy()
        df_rank['Proprietario'] = df_rank.apply(lambda r: f"✈️ {r['Squadra_LFM']}" if r['Rimborsato_Star'] else (f"✂️ {r['Squadra_LFM']}" if r['Rimborsato_Taglio'] else r['Squadra_LFM']), axis=1)
        pivot = df_rank.pivot_table(index=['FVM', 'Nome', 'R'], columns='Lega', values='Proprietario', aggfunc=lambda x: " | ".join(x)).reset_index()
        st.dataframe(pivot.sort_values(by='FVM', ascending=False), use_container_width=True, hide_index=True)

    # --- 📋 ROSE COMPLETE ---
    elif menu == "📋 Rose Complete":
        st.title("📋 Consultazione Rose")
        l_sel = st.selectbox("Lega:", sorted(df_base['Lega'].unique()))
        s_sel = st.selectbox("Squadra:", sorted(df_base[df_base['Lega']==l_sel]['Squadra_LFM'].unique()))
        df_r = df_base[df_base['Squadra_LFM']==s_sel].copy()
        df_r['Stato'] = df_r.apply(lambda r: "✈️ SVINC" if r['Rimborsato_Star'] else ("✂️ TAGLIO" if r['Rimborsato_Taglio'] else "🏃 ROSA"), axis=1)
        st.dataframe(df_r.sort_values(by=['Stato','Nome'])[['Stato', 'Nome', 'R', 'Qt.I', 'FVM']], hide_index=True)

    # --- 🟢 GIOCATORI LIBERI ---
    elif menu == "🟢 Giocatori Liberi":
        st.title("🟢 Calciatori Liberi")
        ids_occupati = set(df_base['Id'])
        df_liberi = df_all_quot[~df_all_quot['Id'].isin(ids_occupati)]
        st.dataframe(df_liberi.sort_values(by='FVM', ascending=False)[['Nome', 'R', 'Qt.I', 'FVM']], hide_index=True)

    # --- ⚙️ GESTIONE & BACKUP ---
    elif menu == "⚙️ Gestione & Backup":
        st.title("⚙️ Pannello di Controllo")
        ed_l = st.data_editor(st.session_state.df_leghe_full, hide_index=True)
        if st.button("Salva Crediti Base"):
            st.session_state.df_leghe_full = ed_l; st.success("Dati salvati in sessione!"); st.rerun()
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.download_button("database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("database_tagli.csv", pd.DataFrame([{'Id': k.split('_')[0], 'Squadra': k.split('_')[1]} for k in st.session_state.tagli_map]).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")

else: st.error("Carica i file CSV necessari (rose, quotazioni, leghe, stadi)!")
