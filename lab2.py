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

# --- 2. GESTIONE SESSIONE & STADI ---
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
        st.title("🗓️ Calendari Campionati Standard")
        files = [f for f in os.listdir('.') if f.startswith("Calendario_") and "CHAMPIONS" not in f.upper() and f.endswith(".csv")]
        if not files: st.warning("Nessun file campionato trovato.")
        else:
            camp = st.selectbox("Campionato:", files)
            df = pd.read_csv(camp, header=None, encoding='latin1').fillna("")
            # Trova giornate su colonna 0 e 6 (standard)
            g_pos = []
            for c in [0, 6]:
                for r in range(len(df)):
                    if "Giornata" in str(df.iloc[r, c]) and "serie a" not in str(df.iloc[r, c]).lower():
                        g_pos.append((str(df.iloc[r, c]).strip(), r, c))
            
            sel_g = st.selectbox("Giornata:", sorted(list(set([x[0] for x in g_pos])), key=natural_sort_key))
            matches = []
            for g_nome, r, c in [x for x in g_pos if x[0] == sel_g]:
                for i in range(1, 8):
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
            st.table(pd.DataFrame(matches))

    # --- 🏆 MOTORE B: COPPE (FORMATO GRUPPI + RIPOSI) ---
    elif menu == "🏆 Coppe e Preliminari":
        st.title("🏆 Coppe e Preliminari")
        files = [f for f in os.listdir('.') if "CHAMPIONS" in f.upper() and f.endswith(".csv")]
        if not files: st.warning("Carica i file Calendario_CHAMPIONS...")
        else:
            camp = st.selectbox("Competizione:", files)
            df = pd.read_csv(camp, header=None, encoding='latin1').fillna("")
            # Nelle coppe le giornate sono in colonna 0 e 7
            g_pos = []
            for c in [0, 7]:
                for r in range(len(df)):
                    if "Giornata" in str(df.iloc[r, c]) and "serie a" not in str(df.iloc[r, c]).lower():
                        g_pos.append((str(df.iloc[r, c]).strip(), r, c))
            
            sel_g = st.selectbox("Giornata:", sorted(list(set([x[0] for x in g_pos])), key=natural_sort_key))
            matches, riposi = [], []
            for g_nome, r, c in [x for x in g_pos if x[0] == sel_g]:
                for i in range(1, 12):
                    if r+i < len(df):
                        row = df.iloc[r+i]
                        if "Giornata" in str(row[c]): break
                        if "Riposa" in str(row[c+1]): riposi.append(str(row[c+1]).strip()); continue
                        h, a = str(row[c+1]).strip(), str(row[c+4]).strip() # Offset +1 per colonna Gruppo
                        if h == "" or h == "nan": continue
                        sh, sa = str(row[c+2]).replace(',','.'), str(row[c+3]).replace(',','.')
                        try:
                            if float(sh) == 0 and float(sa) == 0:
                                cap_h = df_stadi[df_stadi['Squadra']==h]['Stadio'].values[0] if h in df_stadi['Squadra'].values else 0
                                cap_a = df_stadi[df_stadi['Squadra']==a]['Stadio'].values[0] if a in df_stadi['Squadra'].values else 0
                                bh, _ = calculate_stadium_bonus(cap_h); _, ba = calculate_stadium_bonus(cap_a)
                                matches.append({"Partita": f"{h} vs {a}", "Casa": f"+{bh}", "Fuori": f"+{ba}"})
                        except: pass
            st.table(pd.DataFrame(matches))
            if riposi: 
                st.write("☕ **Squadre a Riposo:**")
                for rip in riposi: st.write(f"- {rip}")

    # --- 🏠 DASHBOARD E RESTANTI PAGINE ---
    elif menu == "🏠 Dashboard":
        st.title("🏠 Dashboard Crediti")
        # [Logica Dashboard Golden Edition...]
        st.write("Benvenuto nel sistema Golden.")

    # [Inserire qui le sezioni Gestione Mercato, Ranking, Rose, Svincolati e Gestione Squadre dal file lab3.py]
    # ...

else: st.error("Carica i file base (rose, quotazioni, stadi)!")
