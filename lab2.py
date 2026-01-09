import streamlit as st
import pandas as pd
import math
import os

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
            
            # Calcolo Rimborsi
            df_owned['Rimborso_Star'] = df_owned['FVM'] + (df_owned['Qt.I'] / 2)
            df_owned['Rimborso_Taglio'] = (df_owned['FVM'] + df_owned['Qt.I']) / 2
            
            return df_owned, df_all_quot
        except: continue
    return None, None

# --- 2. LOGICA STADI E COLORI ---
def calculate_stadium_bonus(capienza):
    casa = capienza / 20
    # Arrotondamento per difetto allo 0.5 più vicino per la trasferta
    trasferta = math.floor((casa / 2) * 2) / 2
    return casa, trasferta

MAPPATURA_COLORI = {
    "Serie A": "#00529b",        # Blu/Azzurro ufficiale
    "Bundesliga": "#d3010c",     # Rosso Bundesliga
    "Premier League": "#3d195b", # Viola Premier
    "Liga BBVA": "#ee8707"       # Arancio Liga
}
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]

# --- 3. GESTIONE SESSIONE ---
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

# --- 4. COSTRUZIONE DATI ---
# Caricamento quotazioni e rose
df_base, df_all_quot = load_static_data()

# Caricamento stadi
try:
    df_stadi = pd.read_csv('stadi.csv')
    df_stadi['Squadra'] = df_stadi['Squadra'].str.strip()
except:
    df_stadi = pd.DataFrame(columns=['Squadra', 'Lega', 'Stadio'])

if df_base is not None:
    df_base = pd.merge(df_base, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Admin")
    menu = st.sidebar.radio("Vai a:", [
        "🏠 Dashboard", 
        "📅 Calendario Premier", 
        "🏟️ Calcolo Rapido Stadio", 
        "🏃 Svincolati *", 
        "✂️ Tagli Volontari", 
        "📊 Ranking FVM", 
        "📋 Visualizza Rose", 
        "🟢 Giocatori Liberi", 
        "⚙️ Gestione Squadre"
    ])

    # --- 🏠 DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti e Statistiche")
        
        st.info("📢 **Bacheca News**")
        st.markdown("* 🏃 **Alert Rose:** Il contatore diventa rosso se fuori dal range 25-35 giocatori.")
        
        leghe_effettive = [l for l in ORDINE_LEGHE if l in df_base['Lega'].values]
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_effettive):
            with cols[i % 2]:
                df_l = df_base[df_base['Lega'] == nome_lega]
                
                # Calcoli aggregati
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum','Nome': lambda x: ", ".join(x)}).reset_index()
                attivi = df_l[~(df_l['Rimborsato_Star']) & ~(df_l['Rimborsato_Taglio'])].groupby('Squadra_LFM').size().reset_index(name='Num_Giocatori')
                
                tabella = pd.merge(df_l[['Squadra_LFM', 'Crediti']].drop_duplicates(), res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli.rename(columns={'Nome':'N_T'}), on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, attivi, on='Squadra_LFM', how='left').fillna(0)
                tabella['Totale'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                
                st.markdown(f"## 🏆 {nome_lega} (Media: {int(tabella['Totale'].mean())} cr)")
                bg_color = MAPPATURA_COLORI.get(nome_lega, "#f5f5f5")
                
                for _, sq in tabella.sort_values(by='Squadra_LFM').iterrows():
                    n_g = int(sq['Num_Giocatori'])
                    # Alert range 25-35
                    if 25 <= n_g <= 35:
                        colore_count = "#81c784" # Verde
                        icona = "🏃"
                    else:
                        colore_count = "#ef5350" # Rosso
                        icona = "⚠️" if n_g > 35 else "🏃"
                    
                    st.markdown(f"""<div style="background-color: {bg_color}; padding: 15px; border-radius: 12px; margin-bottom: 12px; color: white; border: 1px solid rgba(255,255,255,0.2);">
                        <div style="display: flex; justify-content: space-between;">
                            <b style="font-size:16px;">{sq['Squadra_LFM']}</b> 
                            <span style="background:{colore_count}; padding:2px 8px; border-radius:10px; font-size:11px;">{icona} {n_g}/25-35</span>
                        </div>
                        <div style="font-size:20px; font-weight:bold;">{int(sq['Totale'])} cr</div>
                    </div>""", unsafe_allow_html=True)

    # --- 📅 CALENDARIO PREMIER ---
    elif menu == "📅 Calendario Premier":
        st.title("📅 Calendario & Bonus Automatici")
        files_presenti = os.listdir('.')
        if 'Calendario_PREMIER-LEAGUE.csv' not in files_presenti:
            st.error("❌ File 'Calendario_PREMIER-LEAGUE.csv' non trovato nella cartella principale.")
        else:
            try:
                df_cal = pd.read_csv('Calendario_PREMIER-LEAGUE.csv', header=None, encoding='utf-8')
                giornate = sorted(list(set(
                    [str(v) for v in df_cal[0].dropna() if "Giornata" in str(v)] + 
                    [str(v) for v in df_cal[6].dropna() if "Giornata" in str(v)]
                )))
                
                sel_g = st.selectbox("Seleziona Giornata:", giornate)
                partite_news = []
                for r in range(len(df_cal)):
                    for c in [0, 6]:
                        if str(df_cal.iloc[r, c]) == sel_g:
                            for i in range(1, 6):
                                if r+i < len(df_cal):
                                    h = str(df_cal.iloc[r+i, c]).strip()
                                    a = str(df_cal.iloc[r+i, c+3]).strip()
                                    s_h = str(df_cal.iloc[r+i, c+1]).replace(',', '.').strip()
                                    s_a = str(df_cal.iloc[r+i, c+2]).replace(',', '.').strip()
                                    try:
                                        if float(s_h) == 0 and float(s_a) == 0:
                                            cap_h = df_stadi[df_stadi['Squadra']==h]['Stadio'].values[0] if h in df_stadi['Squadra'].values else 0
                                            cap_a = df_stadi[df_stadi['Squadra']==a]['Stadio'].values[0] if a in df_stadi['Squadra'].values else 0
                                            b_h, _ = calculate_stadium_bonus(cap_h)
                                            _, b_a = calculate_stadium_bonus(cap_a)
                                            partite_news.append({"Match": f"{h} vs {a}", "Bonus Casa": f"+{b_h}", "Bonus Fuori": f"+{b_a}"})
                                    except: continue
                
                if partite_news:
                    st.table(pd.DataFrame(partite_news))
                else:
                    st.info("Tutte le partite di questa giornata sono state giocate.")
            except Exception as e:
                st.error(f"Errore nella lettura del calendario: {e}")

    # --- 🏟️ CALCOLO RAPIDO STADIO ---
    elif menu == "🏟️ Calcolo Rapido Stadio":
        st.title("🏟️ Calcolo Bonus Manuale")
        c1, c2 = st.columns(2)
        sq_c = c1.selectbox("Casa:", sorted(df_base['Squadra_LFM'].unique()))
        sq_f = c2.selectbox("Fuori:", sorted(df_base['Squadra_LFM'].unique()))
        cap_c = df_stadi[df_stadi['Squadra']==sq_c]['Stadio'].values[0] if sq_c in df_stadi['Squadra'].values else 0
        cap_f = df_stadi[df_stadi['Squadra']==sq_f]['Stadio'].values[0] if sq_f in df_stadi['Squadra'].values else 0
        b_c, _ = calculate_stadium_bonus(cap_c)
        _, b_f = calculate_stadium_bonus(cap_f)
        st.metric(f"Bonus {sq_c}", f"+{b_c}")
        st.metric(f"Bonus {sq_f}", f"+{b_f}")

    # --- 🏃 SVINCOLATI * ---
    elif menu == "🏃 Svincolati *":
        st.title("✈️ Rimborsi da * (100%)")
        cerca = st.text_input("Cerca giocatore:")
        if cerca:
            df_f = df_base[df_base['Nome'].str.contains(cerca, case=False, na=False)].drop_duplicates('Id')
            edit = st.data_editor(df_f[['Rimborsato_Star', 'Nome', 'R', 'FVM', 'Qt.I', 'Rimborso_Star', 'Id']], column_config={"Rimborsato_Star": "Vola ✈️", "Id": None}, hide_index=True, use_container_width=True)
            if st.button("Salva Svincoli"):
                for _, r in edit.iterrows():
                    if r['Rimborsato_Star']: st.session_state.refunded_ids.add(r['Id'])
                    else: st.session_state.refunded_ids.discard(r['Id'])
                st.rerun()
        st.divider()
        st.subheader("📋 Elenco Svincolati")
        st.dataframe(df_base[df_base['Rimborsato_Star']].drop_duplicates('Id')[['Nome', 'R', 'Qt.I', 'FVM', 'Rimborso_Star']], use_container_width=True, hide_index=True)

    # --- ✂️ TAGLI VOLONTARI ---
    elif menu == "✂️ Tagli Volontari":
        st.title("✂️ Tagli Tecnici (50%)")
        cerca_t = st.text_input("Cerca per squadra o nome:")
        if cerca_t:
            df_t = df_base[df_base['Nome'].str.contains(cerca_t, case=False, na=False) | df_base['Squadra_LFM'].str.contains(cerca_t, case=False, na=False)]
            edit_t = st.data_editor(df_t[['Rimborsato_Taglio', 'Nome', 'R', 'FVM', 'Qt.I', 'Squadra_LFM', 'Rimborso_Taglio', 'Taglio_Key']], column_config={"Taglio_Key": None, "Rimborsato_Taglio": "Taglia ✂️"}, hide_index=True, use_container_width=True)
            if st.button("Applica Tagli"):
                for _, r in edit_t.iterrows():
                    if r['Rimborsato_Taglio']: st.session_state.tagli_map.add(r['Taglio_Key'])
                    else: st.session_state.tagli_map.discard(r['Taglio_Key'])
                st.rerun()
        st.divider()
        st.subheader("📋 Elenco Tagli")
        st.dataframe(df_base[df_base['Rimborsato_Taglio']][['Squadra_LFM', 'Nome', 'R', 'Rimborso_Taglio']], use_container_width=True, hide_index=True)

    # --- 📊 RANKING FVM ---
    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM")
        def format_owner(row):
            if row['Rimborsato_Star']: return f"✈️ {row['Squadra_LFM']}"
            if row['Rimborsato_Taglio']: return f"✂️ {row['Squadra_LFM']}"
            return row['Squadra_LFM']
        df_rank = df_base.copy()
        df_rank['Squadra_Display'] = df_rank.apply(format_owner, axis=1)
        pivot = df_rank.pivot_table(index=['FVM', 'Nome', 'R'], columns='Lega', values='Squadra_Display', aggfunc=lambda x: " | ".join(x)).reset_index()
        for l in ORDINE_LEGHE: 
            if l in pivot.columns: pivot[l] = pivot[l].fillna("🟢 LIBERO")
        st.dataframe(pivot.sort_values(by='FVM', ascending=False), use_container_width=True, hide_index=True)

    # --- 📋 VISUALIZZA ROSE ---
    elif menu == "📋 Visualizza Rose":
        st.title("📋 Rose Complete")
        lega_sel = st.selectbox("Lega:", sorted(df_base['Lega'].unique()))
        sq_sel = st.selectbox("Squadra:", sorted(df_base[df_base['Lega']==lega_sel]['Squadra_LFM'].unique()))
        df_r = df_base[df_base['Squadra_LFM']==sq_sel].copy()
        df_r['Stato'] = df_r.apply(lambda r: "✈️ SVINC" if r['Rimborsato_Star'] else ("✂️ TAGLIO" if r['Rimborsato_Taglio'] else "🏃 ROSA"), axis=1)
        st.dataframe(df_r.sort_values(by=['Stato','Nome'])[['Stato', 'Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    # --- 🟢 GIOCATORI LIBERI ---
    elif menu == "🟢 Giocatori Liberi":
        st.title("🟢 Giocatori Svincolati Ovunque")
        try:
            df_esclusi = pd.read_csv('esclusi.csv', sep='\t', header=None)
            bl_ids = set(pd.to_numeric(df_esclusi.iloc[:, 0], errors='coerce').dropna().unique())
        except: bl_ids = set()
        df_lib = df_all_quot[~df_all_quot['Id'].isin(set(df_base['Id'])) & ~df_all_quot['Id'].isin(bl_ids)]
        st.dataframe(df_lib.sort_values(by='FVM', ascending=False)[['Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    # --- ⚙️ GESTIONE SQUADRE ---
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione")
        edited = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Salva"):
            st.session_state.df_leghe_full = fix_league_names(edited); st.success("Dati aggiornati!"); st.rerun()
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.download_button("database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("database_tagli.csv", pd.DataFrame([{'Id': k.split('_')[0], 'Squadra': k.split('_')[1]} for k in st.session_state.tagli_map]).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")

else: st.error("Carica i file CSV necessari (rose, quotazioni, leghe)!")
