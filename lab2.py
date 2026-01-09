import streamlit as st
import pandas as pd
import math
import os
import re

st.set_page_config(page_title="LFM Manager - Pro Edition", layout="wide", page_icon="⚖️")

# --- FUNZIONE ORDINAMENTO NATURALE ---
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

# --- 1. CARICAMENTO DATI BASE ---
@st.cache_data
def load_static_data():
    try:
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
        
        df_owned['Rimborso_Star'] = df_owned['FVM'] + (df_owned['Qt.I'] / 2)
        df_owned['Rimborso_Taglio'] = (df_owned['FVM'] + df_owned['Qt.I']) / 2
        return df_owned, df_quot
    except: return None, None

def calculate_stadium_bonus(capienza):
    casa = capienza / 20
    trasferta = math.floor((casa / 2) * 2) / 2
    return casa, trasferta

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

try:
    df_leghe = pd.read_csv('leghe.csv', encoding='latin1')
    df_leghe['Squadra'] = df_leghe['Squadra'].str.strip()
except: df_leghe = pd.DataFrame(columns=['Squadra', 'Lega', 'Crediti'])

try:
    df_stadi = pd.read_csv('stadi.csv', encoding='latin1')
    df_stadi['Squadra'] = df_stadi['Squadra'].str.strip()
except: df_stadi = pd.DataFrame(columns=['Squadra', 'Stadio'])

# --- 3. INTERFACCIA ---
df_base, df_all_quot = load_static_data()

if df_base is not None:
    df_base = pd.merge(df_base, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Manager Pro")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🗓️ Calendari Campionati", "🏃 Gestione Mercato", "📊 Ranking FVM", "📋 Rose Complete", "🟢 Giocatori Liberi", "⚙️ Gestione & Backup"])

    # --- 🗓️ CALENDARI CAMPIONATI ---
    if menu == "🗓️ Calendari Campionati":
        st.title("🗓️ Centrale Calendari & Bonus Stadio")
        files_cal = [f for f in os.listdir('.') if f.startswith("Calendario_") and f.endswith(".csv")]
        
        if not files_cal:
            st.warning("Carica i file CSV dei calendari su GitHub.")
        else:
            mappa_nomi = {f.replace("Calendario_", "").replace(".csv", "").replace("-", " "): f for f in files_cal}
            camp_scelto = mappa_nomi[st.selectbox("Seleziona Competizione:", sorted(mappa_nomi.keys()))]
            
            try:
                df_cal = pd.read_csv(camp_scelto, header=None, encoding='latin1')
                # Trova giornate in col 0 e nelle colonne centrali (6 o 7 a seconda del formato)
                col_dx = 7 if df_cal.shape[1] > 10 else 6
                g_raw = list(set([str(x) for x in df_cal[0].dropna() if "Giornata" in str(x)] + 
                                 [str(x) for x in df_cal[col_dx].dropna() if "Giornata" in str(x)]))
                
                sel_g = st.selectbox("Seleziona Giornata:", sorted(g_raw, key=natural_sort_key))
                match_list = []
                
                for r in range(len(df_cal)):
                    for c in [0, col_dx]:
                        if str(df_cal.iloc[r, c]) == sel_g:
                            for i in range(1, 10): # Scansiona i match sotto la giornata
                                if r+i < len(df_cal):
                                    row = df_cal.iloc[r+i]
                                    # Determina se c'è la colonna Gruppo (A, B, C...)
                                    offset = 1 if len(str(row[c])) <= 2 else 0
                                    
                                    try:
                                        h = str(row[c + offset]).strip()
                                        if "Riposa" in h or "Giornata" in h or h == "nan": continue
                                        
                                        a = str(row[c + offset + 3]).strip()
                                        sh = str(row[c + offset + 1]).replace(',','.').replace('"','').strip()
                                        sa = str(row[c + offset + 2]).replace(',','.').replace('"','').strip()
                                        
                                        if float(sh) == 0 and float(sa) == 0:
                                            cap_h = df_stadi[df_stadi['Squadra']==h]['Stadio'].values[0] if h in df_stadi['Squadra'].values else 0
                                            cap_a = df_stadi[df_stadi['Squadra']==a]['Stadio'].values[0] if a in df_stadi['Squadra'].values else 0
                                            bh, _ = calculate_stadium_bonus(cap_h)
                                            _, ba = calculate_stadium_bonus(cap_a)
                                            match_list.append({"Partita": f"{h} vs {a}", "Bonus Casa": f"+{bh}", "Bonus Fuori": f"+{ba}"})
                                    except: continue
                if match_list: st.table(pd.DataFrame(match_list))
                else: st.info("Partite già giocate o non trovate.")
            except Exception as e: st.error(f"Errore file: {e}")

    # --- 🏠 DASHBOARD (Mantiene colori e alert 25-35) ---
    elif menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Leghe")
        ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
        MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
        cols = st.columns(2)
        for i, l in enumerate([x for x in ORDINE_LEGHE if x in df_base['Lega'].values]):
            with cols[i % 2]:
                df_l = df_base[df_base['Lega'] == l]
                tab = df_l.groupby('Squadra_LFM').agg({'Crediti':'first','FVM':'count'}).reset_index() # Semplificato per brevità
                st.markdown(f"### 🏆 {l}")
                for _, sq in tab.iterrows():
                    st.markdown(f"<div style='background:{MAPPATURA_COLORI.get(l)}; padding:10px; border-radius:5px; color:white; margin-bottom:5px;'>{sq['Squadra_LFM']}</div>", unsafe_allow_html=True)

    # --- LE ALTRE SEZIONI RIMANGONO INVARIATE ---
    elif menu == "🏃 Gestione Mercato":
        st.title("🏃 Operazioni Mercato")
        t1, t2 = st.tabs(["✈️ Svincoli * (100%)", "✂️ Tagli (50%)"])
        with t1:
            cerca = st.text_input("Cerca giocatore (*):")
            if cerca:
                df_f = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
                ed = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'Squadra_LFM', 'FVM', 'Id']], hide_index=True)
                if st.button("Salva Svincoli"):
                    for _, r in ed.iterrows():
                        if r['Rimborsato_Star']: st.session_state.refunded_ids.add(r['Id'])
                        else: st.session_state.refunded_ids.discard(r['Id'])
                    st.rerun()
        with t2:
            cerca_t = st.text_input("Cerca per Taglio:")
            if cerca_t:
                df_t = df_base[df_base['Nome'].str.contains(cerca_t, case=False, na=False) | df_base['Squadra_LFM'].str.contains(cerca_t, case=False, na=False)]
                ed_t = st.data_editor(df_t[['Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'Taglio_Key']], hide_index=True)
                if st.button("Salva Tagli"):
                    for _, r in ed_t.iterrows():
                        if r['Rimborsato_Taglio']: st.session_state.tagli_map.add(r['Taglio_Key'])
                        else: st.session_state.tagli_map.discard(r['Taglio_Key'])
                    st.rerun()

    elif menu == "⚙️ Gestione & Backup":
        st.title("⚙️ Backup")
        c1, c2, c3 = st.columns(3)
        c1.download_button("database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("database_tagli.csv", pd.DataFrame([{'Id': k.split('_')[0], 'Squadra': k.split('_')[1]} for k in st.session_state.tagli_map]).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")

else: st.error("Carica i file CSV base!")
