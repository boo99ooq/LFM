import streamlit as st
import pandas as pd
import math
import os
import re

st.set_page_config(page_title="LFM Manager - Pro Edition", layout="wide", page_icon="⚖️")

# --- FUNZIONE PER ORDINAMENTO NATURALE (1, 2, 10 invece di 1, 10, 2) ---
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
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🗓️ Calendari Campionati", "🏃 Gestione Mercato", "📊 Ranking FVM", "📋 Rose Complete", "🟢 Giocatori Liberi", "⚙️ Gestione & Backup"])

    # --- 🗓️ CALENDARI CAMPIONATI ---
    if menu == "🗓️ Calendari Campionati":
        st.title("🗓️ Centrale Calendari & Bonus Stadio")
        files_cal = [f for f in os.listdir('.') if f.startswith("Calendario_") and f.endswith(".csv")]
        
        if not files_cal:
            st.warning("Carica i file CSV dei calendari (es: Calendario_SERIE-A.csv)")
        else:
            mappa_nomi = {f.replace("Calendario_", "").replace(".csv", "").replace("-", " "): f for f in files_cal}
            nome_pulito_scelto = st.selectbox("Seleziona Campionato:", sorted(mappa_nomi.keys()))
            camp_scelto = mappa_nomi[nome_pulito_scelto]
            
            try:
                df_cal = pd.read_csv(camp_scelto, header=None, encoding='latin1')
                # Estraiamo le giornate
                giornate_raw = list(set(
                    [str(x) for x in df_cal[0].dropna() if "Giornata" in str(x)] + 
                    [str(x) for x in df_cal[6].dropna() if "Giornata" in str(x)]
                ))
                
                # ORDINAMENTO NATURALE DELLE GIORNATE
                giornate_ordinate = sorted(giornate_raw, key=natural_sort_key)
                
                sel_g = st.selectbox("Seleziona Giornata:", giornate_ordinate)
                
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
                if match_list: st.table(pd.DataFrame(match_list))
                else: st.info("Tutte le partite di questa giornata sono state giocate.")
            except Exception as e: st.error(f"Errore: {e}")

    # --- RESTANTI SEZIONI (Copiale dal codice precedente per Dashboard, Mercato, etc.) ---
    elif menu == "🏠 Dashboard":
        # [Logica Dashboard precedente...]
        pass
    # ... e così via per le altre voci del menu ...

else: st.error("Carica i file CSV necessari!")
