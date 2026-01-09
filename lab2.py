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
            
            df_owned['Rimborso_Star'] = df_owned['FVM'] + (df_owned['Qt.I'] / 2)
            df_owned['Rimborso_Taglio'] = (df_owned['FVM'] + df_owned['Qt.I']) / 2
            
            return df_owned, df_quot
        except: continue
    return None, None

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

if 'df_leghe_full' not in st.session_state:
    try:
        df_temp = pd.read_csv('leghe.csv', encoding='latin1')
        df_temp['Squadra'] = df_temp['Squadra'].str.strip()
        df_temp['Lega'] = df_temp['Lega'].str.strip()
        df_temp['Crediti'] = pd.to_numeric(df_temp['Crediti'], errors='coerce').fillna(0)
        st.session_state.df_leghe_full = df_temp
    except:
        st.session_state.df_leghe_full = pd.DataFrame(columns=['Squadra', 'Lega', 'Crediti'])

try:
    df_stadi = pd.read_csv('stadi.csv', encoding='latin1')
    df_stadi['Squadra'] = df_stadi['Squadra'].str.strip()
except:
    df_stadi = pd.DataFrame(columns=['Squadra', 'Stadio'])

df_base, df_all_quot = load_static_data()

if df_base is not None:
    df_base = pd.merge(df_base, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🗓️ Calendari Campionati", "🏆 Coppe e Preliminari", "🏃 Gestione Mercato", "📊 Ranking FVM", "📋 Rose Complete", "🟢 Giocatori Liberi", "⚙️ Gestione Squadre"])

    # --- 🏠 DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti e News")
        ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
        MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
        
        leghe_effettive = [l for l in ORDINE_LEGHE if l in df_base['Lega'].values]
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_effettive):
            with cols[i % 2]:
                df_l = df_base[df_base['Lega'] == nome_lega]
                
                # Calcoli news per rimborsi
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum', 'Nome': lambda x: ", ".join(x)}).reset_index()
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum', 'Nome': lambda x: ", ".join(x)}).reset_index()
                attivi = df_l[~(df_l['Rimborsato_Star']) & ~(df_l['Rimborsato_Taglio'])].groupby('Squadra_LFM').size().reset_index(name='NG')
                
                tabella = pd.merge(df_l[['Squadra_LFM', 'Crediti']].drop_duplicates(), res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli.rename(columns={'Nome':'N_T'}), on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, attivi, on='Squadra_LFM', how='left').fillna(0)
                tabella['Totale'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                
                st.markdown(f"### 🏆 {nome_lega} (Media: {int(tabella['Totale'].mean())} cr)")
                bg_color = MAPPATURA_COLORI.get(nome_lega, "#333")
                for _, sq in tabella.sort_values(by='Squadra_LFM').iterrows():
                    n_g = int(sq['NG'])
                    col_alert = "#81c784" if 25 <= n_g <= 35 else "#ef5350"
                    st.markdown(f"""<div style="background-color: {bg_color}; padding: 12px; border-radius: 10px; margin-bottom: 8px; color: white;">
                        <div style="display: flex; justify-content: space-between;"><b>{sq['Squadra_LFM']}</b> <span style="background:{col_alert}; padding:1px 8px; border-radius:8px; font-size:10px;">🏃 {n_g}/25-35</span></div>
                        <div style="font-size:18px; font-weight:bold;">{int(sq['Totale'])} cr</div>
                        <div style="font-size:10px; opacity:0.8;">✈️ {sq['Nome'] if sq['Nome'] != 0 else '-'}</div>
                        <div style="font-size:10px; opacity:0.8;">✂️ {sq['N_T'] if sq['N_T'] != 0 else '-'}</div>
                    </div>""", unsafe_allow_html=True)

    # --- 🏃 GESTIONE MERCATO ---
    elif menu == "🏃 Gestione Mercato":
        st.title("🏃 Operazioni Mercato")
        t1, t2 = st.tabs(["✈️ Svincoli * (100%)", "✂️ Tagli (50%)"])
        with t1:
            cerca = st.text_input("Cerca giocatore per svincolo (*):")
            if cerca:
                df_f = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
                ed = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'Squadra_LFM', 'FVM', 'Id']], hide_index=True)
                if st.button("Conferma Svincoli"):
                    for _, r in ed.iterrows():
                        if r['Rimborsato_Star']: st.session_state.refunded_ids.add(r['Id'])
                        else: st.session_state.refunded_ids.discard(r['Id'])
                    st.rerun()
            st.divider()
            st.subheader("📋 Giocatori già svincolati (*)")
            st.dataframe(df_base[df_base['Rimborsato_Star']][['Nome', 'Squadra_LFM', 'Rimborso_Star']], use_container_width=True, hide_index=True)

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
            st.divider()
            st.subheader("📋 Giocatori già tagliati")
            st.dataframe(df_base[df_base['Rimborsato_Taglio']][['Nome', 'Squadra_LFM', 'Rimborso_Taglio']], use_container_width=True, hide_index=True)

    # --- 📊 RANKING FVM ---
    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM")
        c1, c2 = st.columns(2)
        ruolo_f = c1.multiselect("Filtra Ruolo:", sorted(df_base['R'].unique()), default=sorted(df_base['R'].unique()))
        lega_f = c2.multiselect("Filtra Lega:", ORDINE_LEGHE, default=ORDINE_LEGHE)
        
        df_rank = df_base[(df_base['R'].isin(ruolo_f)) & (df_base['Lega'].isin(lega_f))].copy()
        df_rank['Proprietario'] = df_rank.apply(lambda r: f"✈️ {r['Squadra_LFM']}" if r['Rimborsato_Star'] else (f"✂️ {r['Squadra_LFM']}" if r['Rimborsato_Taglio'] else r['Squadra_LFM']), axis=1)
        pivot = df_rank.pivot_table(index=['FVM', 'Nome', 'R'], columns='Lega', values='Proprietario', aggfunc=lambda x: " | ".join(x)).reset_index()
        st.dataframe(pivot.sort_values(by='FVM', ascending=False), use_container_width=True, hide_index=True)

    # --- 📋 ROSE COMPLETE ---
    elif menu == "📋 Rose Complete":
        st.title("📋 Consultazione Rose")
        l_sel = st.selectbox("Seleziona Lega:", sorted(df_base['Lega'].unique()))
        s_sel = st.selectbox("Seleziona Squadra:", sorted(df_base[df_base['Lega']==l_sel]['Squadra_LFM'].unique()))
        df_r = df_base[df_base['Squadra_LFM']==s_sel].copy()
        df_r['Stato'] = df_r.apply(lambda r: "✈️ SVINC" if r['Rimborsato_Star'] else ("✂️ TAGLIO" if r['Rimborsato_Taglio'] else "🏃 ROSA"), axis=1)
        st.dataframe(df_r.sort_values(by=['Stato','Nome'])[['Stato', 'Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    # --- 🟢 GIOCATORI LIBERI ---
    elif menu == "🟢 Giocatori Liberi":
        st.title("🟢 Calciatori Liberi (Svincolati Ovunque)")
        try:
            df_esclusi = pd.read_csv('esclusi.csv', header=None)
            ids_esclusi = set(pd.to_numeric(df_esclusi[0], errors='coerce').dropna())
        except: ids_esclusi = set()
        
        ids_occupati = set(df_base['Id'])
        df_liberi = df_all_quot[~df_all_quot['Id'].isin(ids_occupati) & ~df_all_quot['Id'].isin(ids_esclusi)]
        st.dataframe(df_liberi.sort_values(by='FVM', ascending=False)[['Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    # --- 🗓️ CALENDARI (Mantenuti invariati come da ultime versioni) ---
    elif menu == "🗓️ Calendari Campionati":
        # ... [Codice Calendari Standard] ...
        pass
    elif menu == "🏆 Coppe e Preliminari":
        # ... [Codice Coppe] ...
        pass

    # --- ⚙️ GESTIONE SQUADRE ---
    elif menu == "⚙️ Gestione Squadre":
        # ... [Codice Gestione Squadre] ...
        pass

else: st.error("Carica i file CSV base!")
