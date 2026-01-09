import streamlit as st
import pandas as pd
import math
import os
import re

st.set_page_config(page_title="LFM Dashboard - Golden Edition", layout="wide", page_icon="⚖️")

# --- FUNZIONE ORDINAMENTO NATURALE ---
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

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
            return df_owned, df_quot
        except: continue
    return None, None

def calculate_stadium_bonus(capienza):
    casa = capienza / 20
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

try:
    df_stadi = pd.read_csv('stadi.csv', encoding='latin1')
    df_stadi['Squadra'] = df_stadi['Squadra'].str.strip()
except:
    df_stadi = pd.DataFrame(columns=['Squadra', 'Stadio'])

df_base, df_all_quot = load_static_data()

if df_base is not None:
    # Merge con leghe per Dashboard
    if 'df_leghe_full' not in st.session_state:
        try:
            df_temp = pd.read_csv('leghe.csv', encoding='latin1')
            df_temp['Squadra'] = df_temp['Squadra'].str.strip()
            st.session_state.df_leghe_full = df_temp
        except: st.session_state.df_leghe_full = pd.DataFrame(columns=['Squadra', 'Lega', 'Crediti'])
    
    df_base = pd.merge(df_base, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Golden Edition")
    menu = st.sidebar.radio("Vai a:", [
        "🏠 Dashboard", 
        "🗓️ Calendari Campionati", 
        "🏆 Coppe e Preliminari", 
        "🏃 Gestione Mercato", 
        "📊 Ranking FVM", 
        "📋 Rose Complete", 
        "🟢 Giocatori Liberi", 
        "⚙️ Gestione Squadre"
    ])

    # --- 🗓️ MOTORE A: CAMPIONATI (STANDARD) ---
    if menu == "🗓️ Calendari Campionati":
        st.title("🗓️ Calendari Campionati (Standard)")
        files = [f for f in os.listdir('.') if f.startswith("Calendario_") and "CHAMPIONS" not in f.upper() and f.endswith(".csv")]
        if not files: st.warning("Carica i file Calendario_...")
        else:
            camp = st.selectbox("Campionato:", files)
            df = pd.read_csv(camp, header=None, encoding='latin1').fillna("")
            g_pos = []
            for c in [0, 6]:
                for r in range(len(df)):
                    val = str(df.iloc[r, c])
                    if "Giornata" in val and "serie a" not in val.lower():
                        g_pos.append((val.strip(), r, c))
            
            sel_g = st.selectbox("Giornata:", sorted(list(set([x[0] for x in g_pos])), key=natural_sort_key))
            matches = []
            for g_nome, r, c in [x for x in g_pos if x[0] == sel_g]:
                for i in range(1, 10):
                    if r+i < len(df):
                        row = df.iloc[r+i]
                        if "Giornata" in str(row[c]): break
                        h, a = str(row[c]).strip(), str(row[c+3]).strip()
                        if h == "" or h == "nan": continue
                        sh, sa = str(row[c+1]).replace(',','.'), str(row[c+2]).replace(',','.')
                        try:
                            if float(sh) == 0 and float(sa) == 0:
                                cap_h = df_stadi[df_stadi['Squadra']==h]['Stadio'].values[0] if h in df_stadi['Squadra'].values else 0
                                cap_a = df_stadi[df_stadi['Squadra']==a]['Stadio'].values[0] if a in df_stadi['Squadra'].values else 0
                                bh, _ = calculate_stadium_bonus(cap_h); _, ba = calculate_stadium_bonus(cap_a)
                                matches.append({"Partita": f"{h} vs {a}", "Casa": f"+{bh}", "Fuori": f"+{ba}"})
                        except: pass
            if matches: st.table(pd.DataFrame(matches))
            else: st.info("Nessuna partita da giocare (0-0).")

    # --- 🏆 MOTORE B: COPPE (FORMATO GRUPPI + 4 RIPOSI) ---
    elif menu == "🏆 Coppe e Preliminari":
        st.title("🏆 Coppe e Preliminari")
        files = [f for f in os.listdir('.') if "CHAMPIONS" in f.upper() and f.endswith(".csv")]
        if not files: st.warning("Carica il file Calendario_PRELIMINARI-CHAMPIONS...")
        else:
            camp = st.selectbox("Competizione:", files)
            df = pd.read_csv(camp, header=None, encoding='latin1').fillna("")
            g_pos = []
            # Nelle coppe le colonne giornate sono 0 e 7
            for c in [0, 7]:
                for r in range(len(df)):
                    val = str(df.iloc[r, c])
                    if "Giornata" in val and "serie a" not in val.lower():
                        g_pos.append((val.strip(), r, c))
            
            sel_g = st.selectbox("Giornata:", sorted(list(set([x[0] for x in g_pos])), key=natural_sort_key))
            matches, riposi = [], []
            for g_nome, r, c in [x for x in g_pos if x[0] == sel_g]:
                # Estendiamo a 15 righe per prendere tutti i gruppi e i riposi
                for i in range(1, 16):
                    if r+i < len(df):
                        row = df.iloc[r+i]
                        if "Giornata" in str(row[c]): break
                        # Controllo riposo (può essere in colonna c o c+1)
                        if "Riposa" in str(row[c]) or "Riposa" in str(row[c+1]):
                            txt = str(row[c]).strip() if "Riposa" in str(row[c]) else str(row[c+1]).strip()
                            riposi.append(txt)
                            continue
                        
                        h, a = str(row[c+1]).strip(), str(row[c+4]).strip()
                        if h == "" or h == "nan" or "Riposa" in h: continue
                        sh, sa = str(row[c+2]).replace(',','.'), str(row[c+3]).replace(',','.')
                        try:
                            if float(sh) == 0 and float(sa) == 0:
                                cap_h = df_stadi[df_stadi['Squadra']==h]['Stadio'].values[0] if h in df_stadi['Squadra'].values else 0
                                cap_a = df_stadi[df_stadi['Squadra']==a]['Stadio'].values[0] if a in df_stadi['Squadra'].values else 0
                                bh, _ = calculate_stadium_bonus(cap_h); _, ba = calculate_stadium_bonus(cap_a)
                                matches.append({"Partita": f"{h} vs {a}", "Casa": f"+{bh}", "Fuori": f"+{ba}"})
                        except: pass
            
            if matches: st.table(pd.DataFrame(matches))
            else: st.info("Partite giocate.")
            if riposi:
                st.subheader("☕ Squadre a Riposo")
                # Usiamo set() per evitare duplicati se la riga viene letta due volte
                for rip in sorted(list(set(riposi))): st.write(f"- {rip}")

    # --- 🏠 DASHBOARD ---
    elif menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Leghe")
        ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
        MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
        cols = st.columns(2)
        leghe_attive = [l for l in ORDINE_LEGHE if l in df_base['Lega'].values]
        for i, l in enumerate(leghe_attive):
            with cols[i % 2]:
                df_l = df_base[df_base['Lega'] == l]
                tab = df_l.groupby('Squadra_LFM').size().reset_index(name='NG')
                st.markdown(f"### 🏆 {l}")
                for _, sq in tab.iterrows():
                    bg = MAPPATURA_COLORI.get(l, "#333")
                    st.markdown(f"<div style='background:{bg}; padding:10px; border-radius:8px; color:white; margin-bottom:5px;'>{sq['Squadra_LFM']} ({sq['NG']}/25-35)</div>", unsafe_allow_html=True)

    # --- RESTANTI SEZIONI ---
    elif menu == "🏃 Gestione Mercato":
        st.title("🏃 Mercato")
        t1, t2 = st.tabs(["✈️ Svincoli *", "✂️ Tagli"])
        with t1:
            c = st.text_input("Cerca per svincolo (*):")
            if c:
                df_f = df_base[df_base['Nome'].str.contains(c, case=False, na=False)]
                ed = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'Squadra_LFM', 'Id']], hide_index=True)
                if st.button("Salva Svincoli"):
                    for _, r in ed.iterrows():
                        if r['Rimborsato_Star']: st.session_state.refunded_ids.add(r['Id'])
                        else: st.session_state.refunded_ids.discard(r['Id'])
                    st.rerun()
        with t2:
            c2 = st.text_input("Cerca per taglio:")
            if c2:
                df_t = df_base[df_base['Nome'].str.contains(c2, case=False, na=False)]
                ed2 = st.data_editor(df_t[['Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'Taglio_Key']], hide_index=True)
                if st.button("Salva Tagli"):
                    for _, r in ed2.iterrows():
                        if r['Rimborsato_Taglio']: st.session_state.tagli_map.add(r['Taglio_Key'])
                        else: st.session_state.tagli_map.discard(r['Taglio_Key'])
                    st.rerun()

    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking")
        st.dataframe(df_base.sort_values('FVM', ascending=False)[['Nome', 'R', 'FVM', 'Squadra_LFM']], hide_index=True)

    elif menu == "📋 Rose Complete":
        st.title("📋 Rose")
        sq = st.selectbox("Squadra:", sorted(df_base['Squadra_LFM'].unique()))
        st.dataframe(df_base[df_base['Squadra_LFM']==sq][['Nome', 'R', 'Qt.I', 'FVM']], hide_index=True)

    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Backup")
        c1, c2, c3 = st.columns(3)
        c1.download_button("database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("database_tagli.csv", pd.DataFrame([{'Id': k.split('_')[0], 'Squadra': k.split('_')[1]} for k in st.session_state.tagli_map]).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")

else: st.error("Carica i file base!")
