import streamlit as st
import pandas as pd
import math
import os
import re

st.set_page_config(page_title="LFM Dashboard - Golden Edition", layout="wide", page_icon="⚖️")

# --- COSTANTI GLOBALI ---
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

# --- FUNZIONI UTILITY ---
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def calculate_stadium_bonus(capienza):
    casa = capienza / 20
    trasferta = math.floor((casa / 2) * 2) / 2
    return casa, trasferta

def format_num(num):
    try:
        if num == int(num): return str(int(num))
        return str(round(num, 1))
    except: return str(num)

def fix_league_names(df):
    if 'Lega' in df.columns:
        df['Lega'] = df['Lega'].replace(['Lega A', 'nan', 'Da Assegnare', None], 'Serie A')
        df['Lega'] = df['Lega'].fillna('Serie A')
    return df

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

# --- 2. GESTIONE STATO ---
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
        df_temp['Crediti'] = pd.to_numeric(df_temp['Crediti'], errors='coerce').fillna(0)
        st.session_state.df_leghe_full = fix_league_names(df_temp)
    except: 
        st.session_state.df_leghe_full = pd.DataFrame(columns=['Squadra', 'Lega', 'Crediti'])

try:
    df_stadi = pd.read_csv('stadi.csv', encoding='latin1')
    df_stadi['Squadra'] = df_stadi['Squadra'].str.strip()
    df_stadi['Stadio'] = pd.to_numeric(df_stadi['Stadio'], errors='coerce').fillna(0)
except: 
    df_stadi = pd.DataFrame(columns=['Squadra', 'Stadio'])

df_base, df_all_quot = load_static_data()

if df_base is not None:
    leghe_pulite = st.session_state.df_leghe_full.copy()
    leghe_pulite['Squadra_Key'] = leghe_pulite['Squadra'].str.strip().str.upper()
    df_base['Squadra_Key'] = df_base['Squadra_LFM'].str.strip().str.upper()
    if 'Lega' in df_base.columns: df_base = df_base.drop(columns=['Lega', 'Crediti'], errors='ignore')
    df_base = pd.merge(df_base, leghe_pulite.drop(columns=['Squadra']), on='Squadra_Key', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    menu = st.sidebar.radio("Navigazione:", ["🏠 Dashboard", "🗓️ Calendari Campionati", "🏆 Coppe e Preliminari", "💰 Prospetto Finanze", "📊 Ranking FVM", "💰 Ranking Finanziario", "📋 Rose Complete", "🟢 Giocatori Liberi", "📈 Statistiche Leghe", "⚙️ Gestione Squadre"])

    # --- 🏠 DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Dashboard Riepilogo")
        leghe_eff = [l for l in ORDINE_LEGHE if l in df_base['Lega'].dropna().unique()]
        cols = st.columns(2)
        for i, lega_nome in enumerate(leghe_eff):
            with cols[i % 2]:
                df_l = df_base[df_base['Lega'] == lega_nome]
                df_attivi = df_l[~(df_l['Rimborsato_Star']) & ~(df_l['Rimborsato_Taglio'])]
                att_stats = df_attivi.groupby('Squadra_LFM').agg({'Nome': 'count', 'FVM': 'sum', 'Qt.I': 'sum'}).rename(columns={'Nome': 'NG', 'FVM': 'FVM_Tot', 'Qt.I': 'Quot_Tot'}).reset_index()
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum', 'Nome': lambda x: ", ".join(x)}).reset_index()
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum', 'Nome': lambda x: ", ".join(x)}).reset_index()
                tabella = pd.merge(df_l[['Squadra_LFM', 'Crediti']].drop_duplicates(), res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli.rename(columns={'Nome':'N_T'}), on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, att_stats, on='Squadra_LFM', how='left').fillna(0)
                tabella['Totale_Cr'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                
                st.markdown(f"### 🏆 {lega_nome}")
                for _, sq in tabella.sort_values(by='Squadra_LFM').iterrows():
                    cap = df_stadi[df_stadi['Squadra'].str.strip().str.upper() == sq['Squadra_LFM'].strip().upper()]['Stadio'].values
                    cap_txt = f"{int(cap[0])}k" if len(cap)>0 and cap[0] > 0 else "N.D."
                    color_ng = "#ff4b4b" if sq['NG'] < 25 or sq['NG'] > 35 else "#00ff00"
                    txt_svinc = f"✈️ {sq['Nome']}" if sq['Nome'] != 0 else ""
                    txt_tagli = f"✂️ {sq['N_T']}" if sq['N_T'] != 0 else ""
                    
                    st.markdown(f"""<div style="background-color: {MAPPATURA_COLORI.get(lega_nome)}; padding: 15px; border-radius: 10px; margin-bottom: 12px; color: white; border: 1px solid rgba(255,255,255,0.1);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                            <b style="font-size: 18px;">{sq['Squadra_LFM']}</b> 
                            <span style="font-size:12px; background: rgba(0,0,0,0.2); padding: 2px 6px; border-radius: 4px;">🏟️ {cap_txt}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: baseline;">
                            <div style="font-size:22px; font-weight:bold;">{format_num(sq['Totale_Cr'])} <small style="font-size:12px;">cr residui</small></div>
                            <div style="font-size:14px; font-weight:bold; color: {color_ng};">({int(sq['NG'])} gioc.)</div>
                        </div>
                        <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.2); display: flex; justify-content: space-between; font-size:11px; opacity:0.9;">
                            <span>📊 FVM: <b>{format_num(sq['FVM_Tot'])}</b></span>
                            <span>💰 Quot: <b>{format_num(sq['Quot_Tot'])}</b></span>
                        </div>
                        <div style="margin-top: 10px; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 8px; font-size: 15px; line-height: 1.5;">
                            <div style="color: #ffeb3b; font-weight: bold;">{txt_svinc}</div>
                            <div style="color: #ffffff; font-weight: 500; opacity: 0.9;">{txt_tagli}</div>
                        </div>
                    </div>""", unsafe_allow_html=True)

    # --- 🗓️ CALENDARI CAMPIONATI ---
    elif menu == "🗓️ Calendari Campionati":
        st.title("🗓️ Calendari Campionati")
        files = [f for f in os.listdir('.') if f.startswith("Calendario_") and all(x not in f.upper() for x in ["CHAMPIONS", "EUROPA", "PRELIMINARI"]) and f.endswith(".csv")]
        if files:
            camp = st.selectbox("Seleziona:", files)
            df_c = pd.read_csv(camp, header=None, encoding='latin1').fillna("")
            g_pos = [(str(df_c.iloc[r, c]).strip(), r, c) for c in [0, 6] for r in range(len(df_c)) if "Giornata" in str(df_c.iloc[r, c]) and "serie a" not in str(df_c.iloc[r, c]).lower()]
            if g_pos:
                sel_g = st.selectbox("Giornata:", sorted(list(set([x[0] for x in g_pos])), key=natural_sort_key))
                res = []
                for _, r, c in [x for x in g_pos if x[0] == sel_g]:
                    for i in range(1, 11):
                        if r+i < len(df_c):
                            row = df_c.iloc[r+i]
                            if "Giornata" in str(row[c]): break
                            h, a = str(row[c]).strip(), str(row[c+3]).strip()
                            if not h or h == "nan" or len(h) < 2: continue
                            cap_h = df_stadi[df_stadi['Squadra'].str.strip().str.upper() == h.upper()]['Stadio'].values[0] if h.upper() in df_stadi['Squadra'].str.upper().values else 0
                            cap_a = df_stadi[df_stadi['Squadra'].str.strip().str.upper() == a.upper()]['Stadio'].values[0] if a.upper() in df_stadi['Squadra'].str.upper().values else 0
                            bh, _ = calculate_stadium_bonus(cap_h); _, ba = calculate_stadium_bonus(cap_a)
                            res.append({"Casa": h, "Fuori": a, "Bonus Casa": f"+{format_num(bh)}", "Bonus Fuori": f"+{format_num(ba)}"})
                st.table(pd.DataFrame(res))

    # --- 🏆 COPPE E PRELIMINARI ---
    elif menu == "🏆 Coppe e Preliminari":
        st.title("🏆 Coppe e Preliminari")

        opzioni_coppe = {
            "Champions League": "Calendario_Champions-League.csv",
            "Europa League": "Calendario_Europa-League.csv",
            "Conference League": "Calendario_Conference-League.csv",
            "Preliminari CL": "Calendario_PRELIMINARI-CHAMPIONS-LEAGUE-FASE-3.csv"
        }
        
        scelta = st.selectbox("Seleziona competizione:", list(opzioni_coppe.keys()))
        nome_file = opzioni_coppe[scelta]

        if os.path.exists(nome_file):
            skip = 4 if "PRELIMINARI" not in nome_file else 0
            
            try:
                df_raw = pd.read_csv(nome_file, skiprows=skip, header=None, encoding='ISO-8859-1', on_bad_lines='skip')
                
                partite_pulite = []
                giornata_attuale_sx = "Giornata non definita"
                giornata_attuale_dx = "Giornata non definita"

                for i in range(len(df_raw)):
                    riga = df_raw.iloc[i].tolist()
                    
                    # --- LOGICA COLONNA SINISTRA ---
                    val_sx = str(riga[0]) if len(riga) > 0 else ""
                    if "Giornata" in val_sx:
                        giornata_attuale_sx = val_sx.split(" lega")[0]
                    
                    # Se la colonna 1 ha una squadra e la colonna 2 ha un numero (lo 0-0 del calendario)
                    if len(riga) > 4 and pd.notna(riga[1]) and str(riga[2]).strip() == "0":
                        partite_pulite.append({"G": giornata_attuale_sx, "Girone": riga[0], "Casa": riga[1], "Fuori": riga[4]})

                    # --- LOGICA COLONNA DESTRA (File a due blocchi) ---
                    if len(riga) > 7:
                        val_dx = str(riga[7])
                        if "Giornata" in val_dx:
                            giornata_attuale_dx = val_dx.split(" lega")[0]
                        
                        if len(riga) > 11 and pd.notna(riga[8]) and str(riga[9]).strip() == "0":
                            partite_pulite.append({"G": giornata_attuale_dx, "Girone": riga[7], "Casa": riga[8], "Fuori": riga[11]})

                if partite_pulite:
                    df_final = pd.DataFrame(partite_pulite)
                    
                    # Selezione Giornata
                    giornate_disponibili = sorted(df_final['G'].unique(), key=natural_sort_key)
                    sel_g = st.selectbox("Seleziona Giornata:", giornate_disponibili)
                    
                    view = df_final[df_final['G'] == sel_g]
                    res = []
                    for _, r in view.iterrows():
                        # Calcolo bonus stadi
                        cap_h = df_stadi[df_stadi['Squadra'].str.upper() == str(r['Casa']).upper()]['Stadio'].values[0] if str(r['Casa']).upper() in df_stadi['Squadra'].str.upper().values else 0
                        cap_a = df_stadi[df_stadi['Squadra'].str.upper() == str(r['Fuori']).upper()]['Stadio'].values[0] if str(r['Fuori']).upper() in df_stadi['Squadra'].str.upper().values else 0
                        
                        bh, _ = calculate_stadium_bonus(cap_h)
                        _, ba = calculate_stadium_bonus(cap_a)
                        
                        res.append({
                            "Girone": r['Girone'],
                            "Match": f"{r['Casa']} vs {r['Fuori']}",
                            "Bonus Casa": f"+{format_num(bh)}",
                            "Bonus Fuori": f"+{format_num(ba)}"
                        })
                    st.table(pd.DataFrame(res))
                else:
                    st.warning("Non è stato possibile estrarre partite dal file. Controlla il formato del CSV.")

            except Exception as e:
                st.error(f"Errore durante la lettura del file: {e}")
        else:
            st.error(f"File {nome_file} non trovato.")      
    # --- 💰 PROSPETTO FINANZE (Nuova Stagione) ---
    elif menu == "💰 Prospetto Finanze":
        st.title("💰 Prospetto Finanze: Budget Nuova Stagione")
        
        # 1. Filtro Lega
        lega_selezionata = st.selectbox("Seleziona Lega da visualizzare:", ["Tutte"] + ORDINE_LEGHE)

        # 2. Preparazione Dati Base
        df_pros = st.session_state.df_leghe_full.copy()
        if lega_selezionata != "Tutte":
            df_pros = df_pros[df_pros['Lega'] == lega_selezionata]
        
        df_pros['Squadra_Key'] = df_pros['Squadra'].str.strip().str.upper()
        
        # Merge Stadi
        stadi_p = df_stadi.copy()
        stadi_p['Squadra_Key'] = stadi_p['Squadra'].str.strip().str.upper()
        df_pros = pd.merge(df_pros, stadi_p[['Squadra_Key', 'Stadio']], on='Squadra_Key', how='left').fillna(0)
        
        # Calcolo Rimborsi Distinti
        res_june = df_base[df_base['Rimborsato_Star']].groupby('Squadra_Key')['Rimborso_Star'].sum().reset_index()
        res_sept = df_base[df_base['Rimborsato_Taglio']].groupby('Squadra_Key')['Rimborso_Taglio'].sum().reset_index()
        df_pros = pd.merge(df_pros, res_june, on='Squadra_Key', how='left').fillna(0)
        df_pros = pd.merge(df_pros, res_sept, on='Squadra_Key', how='left').fillna(0)
        
        # Inizializzazione parametri input
        if 'input_finanze' not in st.session_state:
            st.session_state.input_finanze = {sq: {"pos": 1, "coppa": "Nessuna", "mercato": 0.0} for sq in st.session_state.df_leghe_full['Squadra']}
        
        st.subheader("📝 Configurazione Premi e Risultati")
        
        # Tabella di input filtrata
        input_data = []
        for sq in df_pros['Squadra']:
            input_data.append({
                "Squadra": sq,
                "Posizione": st.session_state.input_finanze[sq]["pos"],
                "Coppa": st.session_state.input_finanze[sq]["coppa"],
                "Operazioni Mercato": st.session_state.input_finanze[sq]["mercato"]
            })
        
        df_input = pd.DataFrame(input_data)
        edited_df = st.data_editor(
            df_input,
            column_config={
                "Posizione": st.column_config.NumberColumn("Pos. Campionato", min_value=1, max_value=10, step=1),
                "Coppa": st.column_config.SelectboxColumn("Coppa", options=["Nessuna", "Champions", "Europa League", "Conference"]),
                "Operazioni Mercato": st.column_config.NumberColumn("Extra Mercato (+/-)", step=0.5)
            },
            hide_index=True,
            use_container_width=True,
            key=f"editor_{lega_selezionata}"
        )

        # Aggiornamento stato globale
        for _, row in edited_df.iterrows():
            st.session_state.input_finanze[row['Squadra']] = {"pos": row['Posizione'], "coppa": row['Coppa'], "mercato": row['Operazioni Mercato']}

        # 3. Logica Calcolo
        def get_tax(cap):
            if cap <= 50: return 70
            elif cap <= 60: return 90
            elif cap <= 70: return 120
            elif cap <= 80: return 150
            elif cap <= 90: return 185
            else: return 215

        premi_pos = {1:550, 2:555, 3:560, 4:565, 5:570, 6:575, 7:580, 8:585, 9:590, 10:600}
        premi_coppe = {"Nessuna":0, "Champions":50, "Europa League":25, "Conference":10}

        final_rows = []
        for _, row in df_pros.iterrows():
            sq = row['Squadra']
            inp = st.session_state.input_finanze[sq]
            
            tassa = get_tax(row['Stadio'])
            bonus_pos = premi_pos.get(inp['pos'], 0)
            bonus_coppa = premi_coppe.get(inp['coppa'], 0)
            
            totale = row['Crediti'] - tassa + bonus_pos + bonus_coppa + row['Rimborso_Star'] + row['Rimborso_Taglio'] + inp['mercato']
            
            final_rows.append({
                "Squadra": sq,
                "BUDGET FINALE": totale,
                "Lega": row['Lega'],
                "Residui": row['Crediti'],
                "Tassa": -tassa,
                "Premio Pos.": bonus_pos,
                "Bonus Coppa": bonus_coppa,
                "Rimb. *": row['Rimborso_Star'],
                "Rimb. Tagli": row['Rimborso_Taglio'],
                "Mercato": inp['mercato']
            })

        df_final = pd.DataFrame(final_rows)

        st.divider()
        st.subheader(f"📊 Bilancio Finale - {lega_selezionata}")

        # Stile: Budget Finale in evidenza (Seconda colonna dopo il nome)
        st.dataframe(
            df_final.style.format({
                "BUDGET FINALE": "{:.1f}", "Residui": "{:.1f}", "Tassa": "{:.0f}", 
                "Premio Pos.": "+{:.0f}", "Premio Coppa": "+{:.0f}",
                "Rimb. Giugno": "{:.1f}", "Rimb. Sett.": "{:.1f}", "Mercato": "{:.1f}"
            }).set_properties(subset=['BUDGET FINALE'], **{
                'background-color': '#2e7d32',
                'color': 'white',
                'font-weight': 'bold',
                'font-size': '18px'
            }),
            use_container_width=True,
            hide_index=True
        )
    # --- 📊 RANKING FVM ---
    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM Internazionale")
        c1, c2 = st.columns(2)
        r_f = c1.multiselect("Ruolo:", sorted(df_base['R'].dropna().unique()), default=sorted(df_base['R'].dropna().unique()))
        l_f = c2.multiselect("Lega:", ORDINE_LEGHE, default=ORDINE_LEGHE)
        df_rank = df_base[(df_base['R'].isin(r_f)) & (df_base['Lega'].isin(l_f))].copy()
        df_rank['Proprietario'] = df_rank.apply(lambda r: f"✈️ {r['Squadra_LFM']}" if r['Rimborsato_Star'] else (f"✂️ {r['Squadra_LFM']}" if r['Rimborsato_Taglio'] else r['Squadra_LFM']), axis=1)
        if not df_rank.empty:
            pivot = df_rank.pivot_table(index=['FVM', 'Nome', 'R'], columns='Lega', values='Proprietario', aggfunc=lambda x: " | ".join(x)).reset_index().fillna('🟢')
            st.dataframe(pivot.sort_values('FVM', ascending=False), use_container_width=True, hide_index=True)

    # --- 💰 RANKING FINANZIARIO ---
    elif menu == "💰 Ranking Finanziario":
        st.title("💰 Ranking Finanziario")
        ambito = st.selectbox("Ambito:", ["Mondiale (Top 40)"] + ORDINE_LEGHE)
        df_fin = st.session_state.df_leghe_full.copy()
        df_fin['Squadra_Key'] = df_fin['Squadra'].str.strip().str.upper()
        if ambito != "Mondiale (Top 40)":
            df_fin = df_fin[df_fin['Lega'] == ambito]
        stadi_fin = df_stadi.copy()
        stadi_fin['Squadra_Key'] = stadi_fin['Squadra'].str.strip().str.upper()
        df_fin = pd.merge(df_fin, stadi_fin[['Squadra_Key', 'Stadio']], on='Squadra_Key', how='left').fillna(0)
        res_star = df_base[df_base['Rimborsato_Star']].groupby('Squadra_Key')['Rimborso_Star'].sum().reset_index()
        res_tagli = df_base[df_base['Rimborsato_Taglio']].groupby('Squadra_Key')['Rimborso_Taglio'].sum().reset_index()
        df_fin = pd.merge(df_fin, res_star, on='Squadra_Key', how='left').fillna(0)
        df_fin = pd.merge(df_fin, res_tagli, on='Squadra_Key', how='left').fillna(0)
        df_fin['Crediti_Tot'] = df_fin['Crediti'] + df_fin['Rimborso_Star'] + df_fin['Rimborso_Taglio']
        df_attivi = df_base[~(df_base['Rimborsato_Star']) & ~(df_base['Rimborsato_Taglio'])]
        fvm_tot = df_attivi.groupby('Squadra_Key')['FVM'].sum().reset_index().rename(columns={'FVM': 'FVM_Rosa'})
        df_fin = pd.merge(df_fin, fvm_tot, on='Squadra_Key', how='left').fillna(0)
        df_fin['Punteggio'] = df_fin['Crediti_Tot'] + df_fin['FVM_Rosa'] + (df_fin['Stadio'] * 10)
        df_fin = df_fin.sort_values(by='Punteggio', ascending=False).reset_index(drop=True)
        df_fin.index += 1
        display_fin = df_fin[['Squadra', 'Lega', 'Crediti_Tot', 'FVM_Rosa', 'Stadio', 'Punteggio']].copy()
        display_fin.columns = ['Squadra', 'Lega', 'Crediti', 'FVM Rosa', 'Stadio (k)', 'TOT']
        for col in ['Crediti', 'FVM Rosa', 'Stadio (k)', 'TOT']:
            display_fin[col] = display_fin[col].apply(format_num)
        st.dataframe(display_fin, use_container_width=True)

    # --- 📋 ROSE COMPLETE ---
    elif menu == "📋 Rose Complete":
        st.title("📋 Consultazione Rose")
        leghe_disp = sorted(df_base['Lega'].dropna().unique())
        if leghe_disp:
            l_sel = st.selectbox("Lega:", leghe_disp)
            sq_sel = st.selectbox("Squadra:", sorted(df_base[df_base['Lega']==l_sel]['Squadra_LFM'].unique()))
            df_r = df_base[df_base['Squadra_LFM']==sq_sel].copy()
            df_r['Stato'] = df_r.apply(lambda r: "✈️ SVINC" if r['Rimborsato_Star'] else ("✂️ TAGLIO" if r['Rimborsato_Taglio'] else "🏃 ROSA"), axis=1)
            df_r['Ruolo_Ord'] = df_r['R'].map(ORDINE_RUOLI)
            df_r = df_r.sort_values(by=['Stato', 'Ruolo_Ord', 'FVM'], ascending=[False, True, False])
            styled_df = df_r[['Stato', 'Nome', 'R', 'Qt.I', 'FVM']].style.background_gradient(subset=['FVM'], cmap='Greens')
            st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # --- 🟢 GIOCATORI LIBERI ---
    elif menu == "🟢 Giocatori Liberi":
        st.title("🟢 Calciatori Liberi")
        try:
            df_esc = pd.read_csv('esclusi.csv', sep='\t', header=None)
            ids_esc = set(pd.to_numeric(df_esc[0], errors='coerce').dropna().astype(int))
        except: ids_esc = set()
        ids_occ = set(df_base['Id'])
        df_lib = df_all_quot[~df_all_quot['Id'].isin(ids_occ) & ~df_all_quot['Id'].isin(ids_esc)]
        st.dataframe(df_lib.sort_values('FVM', ascending=False)[['Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

    # --- 📈 STATISTICHE LEGHE ---
    elif menu == "📈 Statistiche Leghe":
        st.title("📈 Medie Comparative per Lega")
        df_stats_base = st.session_state.df_leghe_full.copy()
        df_stats_base['Squadra_Key'] = df_stats_base['Squadra'].str.strip().str.upper()
        
        # Recupero rimborsi e dati attivi per ogni squadra
        df_attivi = df_base[~(df_base['Rimborsato_Star']) & ~(df_base['Rimborsato_Taglio'])]
        stats_sq = df_attivi.groupby('Squadra_Key').agg({'FVM': 'sum', 'Qt.I': 'sum'}).reset_index().rename(columns={'FVM': 'FVM_Tot', 'Qt.I': 'Quot_Tot'})
        
        # Merge con crediti e stadi
        df_calc = pd.merge(df_stats_base, stats_sq, on='Squadra_Key', how='left').fillna(0)
        stadi_p = df_stadi.copy()
        stadi_p['Squadra_Key'] = stadi_p['Squadra'].str.strip().str.upper()
        df_calc = pd.merge(df_calc, stadi_p[['Squadra_Key', 'Stadio']], on='Squadra_Key', how='left').fillna(0)
        
        # Calcolo rimborsi per aggiungerli ai crediti
        res_star = df_base[df_base['Rimborsato_Star']].groupby('Squadra_Key')['Rimborso_Star'].sum().reset_index()
        res_tagli = df_base[df_base['Rimborsato_Taglio']].groupby('Squadra_Key')['Rimborso_Taglio'].sum().reset_index()
        df_calc = pd.merge(df_calc, res_star, on='Squadra_Key', how='left').fillna(0)
        df_calc = pd.merge(df_calc, res_tagli, on='Squadra_Key', how='left').fillna(0)
        df_calc['Crediti_Tot'] = df_calc['Crediti'] + df_calc['Rimborso_Star'] + df_calc['Rimborso_Taglio']
        
        if not df_calc.empty:
            medie_lega = df_calc.groupby('Lega').agg({'Stadio': 'mean', 'Crediti_Tot': 'mean', 'FVM_Tot': 'mean'}).reset_index()
            medie_lega.columns = ['Lega', 'Stadio Medio (k)', 'Crediti Medi', 'FVM Medio']
            for col in ['Stadio Medio (k)', 'Crediti Medi', 'FVM Medio']:
                medie_lega[col] = medie_lega[col].apply(format_num)
            st.table(medie_lega)

    # --- ⚙️ GESTIONE SQUADRE ---
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione & Backup")
        edited = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Salva Crediti"):
            st.session_state.df_leghe_full = edited; st.success("Dati aggiornati!"); st.rerun()
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.download_button("database_lfm.csv", pd.DataFrame({'Id': list(st.session_state.refunded_ids)}).to_csv(index=False).encode('utf-8'), "database_lfm.csv")
        c2.download_button("database_tagli.csv", pd.DataFrame([{'Id': k.split('_')[0], 'Squadra': k.split('_')[1]} for k in st.session_state.tagli_map]).to_csv(index=False).encode('utf-8'), "database_tagli.csv")
        c3.download_button("leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")

else:
    st.error("Carica i file base!")
