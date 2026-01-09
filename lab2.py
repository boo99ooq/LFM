import streamlit as st
import pandas as pd
import math
import os
import re

st.set_page_config(page_title="LFM Dashboard - Golden Edition", layout="wide", page_icon="⚖️")

# --- FUNZIONE PER ORDINAMENTO NATURALE ---
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

    st.sidebar.title("⚖️ LFM Golden Edition")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🗓️ Calendari Campionati", "🏃 Gestione Mercato", "📊 Ranking FVM", "📋 Rose Complete", "🟢 Giocatori Liberi", "⚙️ Gestione Squadre"])

    # --- 🗓️ CALENDARI (LOGICA UNIVERSALE CORRETTA) ---
    if menu == "🗓️ Calendari Campionati":
        st.title("🗓️ Centrale Calendari")
        files_cal = [f for f in os.listdir('.') if f.startswith("Calendario_") and f.endswith(".csv")]
        
        if not files_cal:
            st.warning("Nessun file calendario trovato.")
        else:
            mappa_nomi = {f.replace("Calendario_", "").replace(".csv", "").replace("-", " "): f for f in files_cal}
            camp_scelto = mappa_nomi[st.selectbox("Seleziona Competizione:", sorted(mappa_nomi.keys()))]
            
            try:
                df_cal = pd.read_csv(camp_scelto, header=None, encoding='latin1').fillna("")
                
                # 1. TROVA TUTTE LE INTESTAZIONI DI GIORNATA
                giornate_trovate = []
                for r in range(len(df_cal)):
                    for c in range(df_cal.shape[1]):
                        cella = str(df_cal.iloc[r, c]).strip()
                        if "giornata" in cella.lower() and "serie a" not in cella.lower():
                            giornate_trovate.append({"nome": cella, "r": r, "c": c})
                
                elenco_nomi = sorted(list(set([g["nome"] for g in giornate_trovate])), key=natural_sort_key)
                sel_g = st.selectbox("Seleziona Giornata:", elenco_nomi)
                
                match_list = []
                riposi = []
                
                # 2. PROCESSA OGNI BLOCCO DELLA GIORNATA SELEZIONATA
                posizioni = [g for g in giornate_trovate if g["nome"] == sel_g]
                
                for pos in posizioni:
                    r_start, c_start = pos["r"], pos["c"]
                    for i in range(1, 15):
                        if r_start + i < len(df_cal):
                            row = df_cal.iloc[r_start + i]
                            
                            # Se troviamo un'altra intestazione, il blocco è finito
                            testo_cella_base = str(row[c_start]).strip()
                            if "giornata" in testo_cella_base.lower(): break
                            
                            # LOGICA DINAMICA PER OFFSET (SQUADRA CASA)
                            # Se la cella base è corta (es. Gruppo "A"), la squadra è nella colonna dopo
                            if testo_cella_base != "" and len(testo_cella_base) <= 2:
                                idx_casa = c_start + 1
                            else:
                                idx_casa = c_start
                            
                            squadra_casa = str(row[idx_casa]).strip()
                            if not squadra_casa or squadra_casa == "nan": continue
                            
                            # Gestione Riposi
                            if "riposa" in squadra_casa.lower():
                                riposi.append(squadra_casa)
                                continue
                                
                            try:
                                squadra_fuori = str(row[idx_casa + 3]).strip()
                                # Pulizia punteggi (gestisce "0", "0,0", "" ecc)
                                sh_str = str(row[idx_casa + 1]).replace(',','.').replace('"','').strip()
                                sa_str = str(row[idx_casa + 2]).replace(',','.').replace('"','').strip()
                                
                                # Solo se la partita deve essere ancora giocata
                                if sh_str == "0" and sa_str == "0":
                                    cap_h = df_stadi[df_stadi['Squadra']==squadra_casa]['Stadio'].values[0] if squadra_casa in df_stadi['Squadra'].values else 0
                                    cap_a = df_stadi[df_stadi['Squadra']==squadra_fuori]['Stadio'].values[0] if squadra_fuori in df_stadi['Squadra'].values else 0
                                    
                                    bh, _ = calculate_stadium_bonus(cap_h)
                                    _, ba = calculate_stadium_bonus(cap_a)
                                    
                                    match_list.append({
                                        "Partita": f"{squadra_casa} vs {squadra_fuori}",
                                        "Bonus Casa": f"+{bh}",
                                        "Bonus Fuori": f"+{ba}"
                                    })
                            except: continue

                if match_list:
                    st.subheader(f"🏟️ Bonus Stadio - {sel_g}")
                    st.table(pd.DataFrame(match_list))
                else:
                    st.info("Nessuna partita da giocare (0-0) trovata per questa giornata.")
                
                if riposi:
                    st.subheader("☕ Squadre a riposo")
                    for rip in sorted(list(set(riposi))): st.write(f"- {rip}")

            except Exception as e: st.error(f"Errore tecnico: {e}")

    # --- 🏠 DASHBOARD ---
    elif menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti")
        ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
        MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
        leghe_effettive = [l for l in ORDINE_LEGHE if l in df_base['Lega'].values]
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_effettive):
            with cols[i % 2]:
                df_l = df_base[df_base['Lega'] == nome_lega]
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum'}).reset_index()
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum'}).reset_index()
                attivi = df_l[~(df_l['Rimborsato_Star']) & ~(df_l['Rimborsato_Taglio'])].groupby('Squadra_LFM').size().reset_index(name='NG')
                tabella = pd.merge(df_l[['Squadra_LFM', 'Crediti']].drop_duplicates(), res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, attivi, on='Squadra_LFM', how='left').fillna(0)
                tabella['Totale'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                st.markdown(f"### 🏆 {nome_lega}")
                bg_color = MAPPATURA_COLORI.get(nome_lega, "#333")
                for _, sq in tabella.sort_values(by='Squadra_LFM').iterrows():
                    n_g = int(sq['NG'])
                    col_alert = "#81c784" if 25 <= n_g <= 35 else "#ef5350"
                    st.markdown(f"""<div style="background-color: {bg_color}; padding: 12px; border-radius: 10px; margin-bottom: 8px; color: white;">
                        <b>{sq['Squadra_LFM']}</b> <span style="float:right; background:{col_alert}; padding:1px 8px; border-radius:8px; font-size:10px;">🏃 {n_g}</span>
                        <div style="font-size:18px; font-weight:bold;">{int(sq['Totale'])} cr</div>
                    </div>""", unsafe_allow_html=True)

    # --- RESTANTI SEZIONI ---
    elif menu == "🏃 Gestione Mercato":
        st.title("🏃 Operazioni Mercato")
        t1, t2 = st.tabs(["✈️ Svincoli * (100%)", "✂️ Tagli (50%)"])
        with t1:
            cerca = st.text_input("Cerca giocatore (*):")
            if cerca:
                df_f = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
                ed = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'Squadra_LFM', 'FVM', 'Id']], hide_index=True)
                if st.button("Conferma Svincoli"):
                    for _, r in ed.iterrows():
                        if r['Rimborsato_Star']: st.session_state.refunded_ids.add(r['Id'])
                        else: st.session_state.refunded_ids.discard(r['Id'])
                    st.rerun()
        with t2:
            cerca_t = st.text_input("Cerca per Taglio:")
            if cerca_t:
                df_t = df_base[df_base['Nome'].str.contains(cerca_t, case=False, na=False) | df_base['Squadra_LFM'].str.contains(cerca_t, case=False, na=False)]
                ed_t = st.data_editor(df_t[['Rimborsato_Taglio', 'Nome', 'Squadra_LFM', 'Taglio_Key']], hide_index=True)
                if st.button("Conferma Tagli"):
                    for _, r in ed_t.iterrows():
                        if r['Rimborsato_Taglio']: st.session_state.tagli_map.add(r['Taglio_Key'])
                        else: st.session_state.tagli_map.discard(r['Taglio_Key'])
                    st.rerun()

    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM")
        df_rank = df_base.copy()
        df_rank['Proprietario'] = df_rank.apply(lambda r: f"✈️ {r['Squadra_LFM']}" if r['Rimborsato_Star'] else (f"✂️ {r['Squadra_LFM']}" if r['Rimborsato_Taglio'] else r['Squadra_LFM']), axis=1)
        pivot = df_rank.pivot_table(index=['FVM', 'Nome', 'R'], columns='Lega', values='Proprietario', aggfunc=lambda x: " | ".join(x)).reset_index()
        st.dataframe(pivot.sort_values(by='FVM', ascending=False), use_container_width=True, hide_index=True)

    elif menu == "📋 Rose Complete":
        st.title("📋 Consultazione Rose")
        l_sel = st.selectbox("Lega:", sorted(df_base['Lega'].unique()))
        sq_sel = st.selectbox("Squadra:", sorted(df_base[df_base['Lega']==l_sel]['Squadra_LFM'].unique()))
        df_r = df_base[df_base['Squadra_LFM']==sq_sel].copy()
        df_r['Stato'] = df_r.apply(lambda r: "✈️ SVINC" if r['Rimborsato_Star'] else ("✂️ TAGLIO" if r['Rimborsato_Taglio'] else "🏃 ROSA"), axis=1)
        st.dataframe(df_r.sort_values(by=['Stato','Nome'])[['Stato', 'Nome', 'R', 'Qt.I', 'FVM']], hide_index=True)

    elif menu == "🟢 Giocatori Liberi":
        st.title("🟢 Giocatori Svincolati")
        ids_occ = set(df_base['Id'])
        st.dataframe(df_all_quot[~df_all_quot['Id'].isin(ids_occ)].sort_values(by='FVM', ascending=False)[['Nome', 'R', 'Qt.I', 'FVM']], hide_index=True)

    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Backup & Crediti")
        edited = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Salva Modifiche Crediti"):
            st.session_state.df_leghe_full = edited; st.success("Dati aggiornati!"); st.rerun()
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.download_button("database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("database_tagli.csv", pd.DataFrame([{'Id': k.split('_')[0], 'Squadra': k.split('_')[1]} for k in st.session_state.tagli_map]).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")

else: st.error("Carica i file CSV base!")
