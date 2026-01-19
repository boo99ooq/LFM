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
    """Rimuove il .0 se presente per pulizia visiva"""
    if num == int(num):
        return str(int(num))
    return str(round(num, 1))

def fix_league_names(df):
    if 'Lega' in df.columns:
        df['Lega'] = df['Lega'].replace(['Lega A', 'nan', 'Da Assegnare', None], 'Serie A')
        df['Lega'] = df['Lega'].fillna('Serie A')
    return df

# --- 1. CARICAMENTO DATI ---
@st.cache_data
def load_data():
    try:
        # Caricamento standard (virgola)
        rosters = pd.read_csv('fantamanager-2021-rosters.csv', encoding='latin1')
        leghe = pd.read_csv('leghe.csv', encoding='latin1')
        quot = pd.read_csv('quot.csv', encoding='latin1')
        
        # Caricamento speciale per ESCLUSI (Tabulazione)
        # header=0 significa che la prima riga contiene i nomi Id, R, Nome...
        esclusi = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1', header=0)
        
        # Uniformiamo i nomi delle colonne per sicurezza
        esclusi.columns = ['Id', 'R', 'Nome', 'Qt.I', 'FVM']
        
        # Pulizia fondamentale per evitare KeyError: 'Id'
        for df in [rosters, quot, esclusi]:
            # Rimuove righe dove l'Id non è un numero (come quelle col $)
            df['Id'] = pd.to_numeric(df['Id'], errors='coerce')
            df.dropna(subset=['Id'], inplace=True)
            df['Id'] = df['Id'].astype(int)
            
            # Se esiste la colonna FVM, puliamola
            if 'FVM' in df.columns:
                df['FVM'] = pd.to_numeric(df['FVM'], errors='coerce').fillna(0)

        return rosters, leghe, quot, esclusi
    except Exception as e:
        st.error(f"Errore tecnico durante la lettura dei CSV: {e}")
        return None, None, None, None

# --- 2. GESTIONE STATO E DATABASE ---
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
    
    if 'Lega' in df_base.columns: df_base = df_base.drop(columns=['Lega', 'Crediti', 'Squadra_y'], errors='ignore')

    df_base = pd.merge(df_base, leghe_pulite.drop(columns=['Squadra']), on='Squadra_Key', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Golden Edition")
    menu = st.sidebar.radio("Navigazione:", ["🏠 Dashboard", "🗓️ Calendari Campionati", "🏆 Coppe e Preliminari", "🏃 Gestione Mercato", "📊 Ranking FVM", "📋 Rose Complete", "🟢 Giocatori Liberi", "📈 Statistiche Leghe", "⚙️ Gestione Squadre"])

    # --- 🏠 DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Dashboard Riepilogo")
        leghe_eff = [l for l in ORDINE_LEGHE if l in df_base['Lega'].dropna().unique()]
        cols = st.columns(2)
        for i, lega_nome in enumerate(leghe_eff):
            with cols[i % 2]:
                df_l = df_base[df_base['Lega'] == lega_nome]
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({'Rimborso_Star':'sum', 'Nome': lambda x: ", ".join(x)}).reset_index()
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({'Rimborso_Taglio':'sum', 'Nome': lambda x: ", ".join(x)}).reset_index()
                df_attivi = df_l[~(df_l['Rimborsato_Star']) & ~(df_l['Rimborsato_Taglio'])]
                att_stats = df_attivi.groupby('Squadra_LFM').agg({'Nome': 'count', 'FVM': 'sum', 'Qt.I': 'sum'}).rename(columns={'Nome': 'NG', 'FVM': 'FVM_Tot', 'Qt.I': 'Quot_Tot'}).reset_index()
                tabella = pd.merge(df_l[['Squadra_LFM', 'Crediti']].drop_duplicates(), res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli.rename(columns={'Nome':'N_T'}), on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, att_stats, on='Squadra_LFM', how='left').fillna(0)
                tabella['Totale_Cr'] = tabella['Crediti'] + tabella['Rimborso_Star'] + tabella['Rimborso_Taglio']
                st.markdown(f"### 🏆 {lega_nome}")
                for _, sq in tabella.sort_values(by='Squadra_LFM').iterrows():
                    cap = df_stadi[df_stadi['Squadra'].str.strip().str.upper() == sq['Squadra_LFM'].strip().upper()]['Stadio'].values
                    cap_txt = f"{int(cap[0])}k" if len(cap)>0 and cap[0] > 0 else "N.D."
                    color_ng = "#ff4b4b" if sq['NG'] < 25 or sq['NG'] > 35 else "#00ff00"
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
                            <span>📊 Valore FVM: <b>{format_num(sq['FVM_Tot'])}</b></span>
                            <span>💰 Valore Quot: <b>{format_num(sq['Quot_Tot'])}</b></span>
                        </div>
                        <div style="font-size:10px; opacity:0.7; margin-top: 5px;">
                            ✈️ {sq['Nome'] if sq['Nome'] != 0 else '-'} | ✂️ {sq['N_T'] if sq['N_T'] != 0 else '-'}
                        </div>
                    </div>""", unsafe_allow_html=True)

    # --- 🗓️ CALENDARI ---
    elif menu == "🗓️ Calendari Campionati":
        st.title("🗓️ Calendari Campionati")
        files = [f for f in os.listdir('.') if f.startswith("Calendario_") and "CHAMPIONS" not in f.upper() and "PRELIMINARI" not in f.upper() and f.endswith(".csv")]
        if files:
            camp = st.selectbox("Seleziona:", files)
            df_c = pd.read_csv(camp, header=None, encoding='latin1').fillna("")
            g_pos = [(str(df_c.iloc[r, c]).strip(), r, c) for c in [0, 6] for r in range(len(df_c)) if "Giornata" in str(df_c.iloc[r, c]) and "serie a" not in str(df_c.iloc[r, c]).lower()]
            sel_g = st.selectbox("Giornata:", sorted(list(set([x[0] for x in g_pos])), key=natural_sort_key))
            res = []
            for _, r, c in [x for x in g_pos if x[0] == sel_g]:
                for i in range(1, 10):
                    if r+i < len(df_c):
                        row = df_c.iloc[r+i]
                        if "Giornata" in str(row[c]): break
                        h, a = str(row[c]).strip(), str(row[c+3]).strip()
                        if not h or h == "nan": continue
                        try:
                            cap_h = df_stadi[df_stadi['Squadra'].str.strip().str.upper() == h.upper()]['Stadio'].values[0] if h.upper() in df_stadi['Squadra'].str.upper().values else 0
                            cap_a = df_stadi[df_stadi['Squadra'].str.strip().str.upper() == a.upper()]['Stadio'].values[0] if a.upper() in df_stadi['Squadra'].str.upper().values else 0
                            bh, _ = calculate_stadium_bonus(cap_h); _, ba = calculate_stadium_bonus(cap_a)
                            
                            # MODIFICA QUI: Separazione in CASA e FUORI
                            res.append({
                                "CASA": h, 
                                "FUORI": a, 
                                "Bonus Casa": f"+{format_num(bh)}", 
                                "Bonus Fuori": f"+{format_num(ba)}"
                            })
                        except: pass
            
            if res:
                st.table(pd.DataFrame(res))
            else:
                st.info("Nessun match trovato per questa giornata.")

    # --- 🏆 COPPE E PRELIMINARI ---
    elif menu == "🏆 Coppe e Preliminari":
        st.title("🏆 Coppe e Preliminari")
        files = [f for f in os.listdir('.') if ("CHAMPIONS" in f.upper() or "PRELIMINARI" in f.upper()) and f.endswith(".csv")]
        if files:
            camp = st.selectbox("Seleziona Competizione:", files)
            df_co = pd.read_csv(camp, header=None, encoding='latin1').fillna("")
            g_pos = []
            for r in range(len(df_co)):
                for c in range(len(df_co.columns)):
                    if "Giornata" in str(df_co.iloc[r, c]) and "serie a" not in str(df_co.iloc[r, c]).lower():
                        g_pos.append((str(df_co.iloc[r, c]).strip(), r, c))
            
            if g_pos:
                sel_g = st.selectbox("Giornata:", sorted(list(set([x[0] for x in g_pos])), key=natural_sort_key))
                res, rip = [], []
                for label, r, col_idx in [x for x in g_pos if x[0] == sel_g]:
                    for i in range(1, 16):
                        if r+i < len(df_co):
                            row = df_co.iloc[r+i]
                            if "Giornata" in str(row[col_idx]): break
                            if "Riposa" in str(row[col_idx]) or "Riposa" in str(row[col_idx+1]):
                                rip.append(str(row[col_idx] if "Riposa" in str(row[col_idx]) else row[col_idx+1]).replace("Riposa","").strip())
                                continue
                            try:
                                h, a = str(row[col_idx+1]).strip(), str(row[col_idx+4]).strip()
                                if h and h != "nan" and len(h) > 2:
                                    cap_h = df_stadi[df_stadi['Squadra'].str.strip().str.upper() == h.upper()]['Stadio'].values[0] if h.upper() in df_stadi['Squadra'].str.upper().values else 0
                                    cap_a = df_stadi[df_stadi['Squadra'].str.strip().str.upper() == a.upper()]['Stadio'].values[0] if a.upper() in df_stadi['Squadra'].str.upper().values else 0
                                    bh, _ = calculate_stadium_bonus(cap_h); _, ba = calculate_stadium_bonus(cap_a)
                                    
                                    # MODIFICA: Separazione colonne CASA e FUORI
                                    res.append({
                                        "Girone": str(row[col_idx]).strip(), 
                                        "CASA": h, 
                                        "FUORI": a, 
                                        "Bonus Casa": f"+{format_num(bh)}", 
                                        "Bonus Fuori": f"+{format_num(ba)}"
                                    })
                            except: continue
                
                if res:
                    st.table(pd.DataFrame(res))
                if rip: 
                    st.info("☕ **Riposano:** " + ", ".join(sorted(list(set(filter(None, rip))))))
    # --- 📈 STATISTICHE LEGHE ---
    elif menu == "📈 Statistiche Leghe":
        st.title("📈 Medie Comparative per Lega")
        df_stats_base = st.session_state.df_leghe_full.copy()
        df_stats_base['Squadra_Key'] = df_stats_base['Squadra'].str.strip().str.upper()
        stadi_puliti = df_stadi.copy()
        stadi_puliti['Squadra_Key'] = stadi_puliti['Squadra'].str.strip().str.upper()
        df_stats_base = pd.merge(df_stats_base, stadi_puliti[['Squadra_Key', 'Stadio']], on='Squadra_Key', how='left').fillna(0)
        df_attivi = df_base[~(df_base['Rimborsato_Star']) & ~(df_base['Rimborsato_Taglio'])]
        tecnici = df_attivi.groupby('Squadra_Key').agg({'FVM': 'sum', 'Qt.I': 'sum'}).reset_index().rename(columns={'FVM': 'FVM_Tot', 'Qt.I': 'Quot_Tot'})
        df_final_stats = pd.merge(df_stats_base, tecnici, on='Squadra_Key', how='left').fillna(0)
        
        if 'Lega' in df_final_stats.columns and not df_final_stats[df_final_stats['Lega'] != 0].empty:
            df_calc = df_final_stats[df_final_stats['Lega'] != 0]
            medie_lega = df_calc.groupby('Lega').agg({'Stadio': 'mean', 'Crediti': 'mean', 'FVM_Tot': 'mean', 'Quot_Tot': 'mean'}).reset_index()
            
            # Formattazione per la tabella senza .0
            display_stats = medie_lega.copy()
            for col in ['Stadio', 'Crediti', 'FVM_Tot', 'Quot_Tot']:
                display_stats[col] = display_stats[col].apply(format_num)
            display_stats['Stadio'] = display_stats['Stadio'] + "k"
            display_stats.columns = ['Lega', 'Media Stadio', 'Media Crediti Residui', 'Media Valore FVM', 'Media Valore Quot.']
            st.table(display_stats)
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Confronto FVM Medio")
                st.bar_chart(medie_lega.set_index('Lega')['FVM_Tot'])
            with c2:
                st.subheader("Confronto Crediti Medi")
                st.bar_chart(medie_lega.set_index('Lega')['Crediti'])

    # --- ALTRO MENU (MERCATO, RANKING, ROSE, ECC.) ---
    elif menu == "🏃 Gestione Mercato":
        st.title("🏃 Gestione Mercato")
        t1, t2 = st.tabs(["✈️ Svincoli (*)", "✂️ Tagli"])
        with t1:
            c = st.text_input("Cerca giocatore per svincolo (*):")
            if c:
                df_f = df_base[df_base['Nome'].str.contains(c, case=False, na=False)].drop_duplicates('Id')
                
                # 1. Creiamo il data_editor con l'Id incluso ma nascosto
                ed = st.data_editor(
                    df_f[['Id', 'Rimborsato_Star', 'Nome', 'Squadra_LFM', 'Qt.I', 'FVM', 'Rimborso_Star']], 
                    hide_index=True,
                    column_config={
                        "Id": st.column_config.Column(hidden=True),
                    },
                    key="editor_svincoli" # Aggiungi una chiave univoca
                )
                
                # 2. AGGIUNGI QUESTO: Il pulsante per confermare le modifiche
                if st.button("Conferma Svincoli (*)"):
                    for _, r in ed.iterrows():
                        if r['Rimborsato_Star']:
                            st.session_state.refunded_ids.add(r['Id']) # Qui l'Id ora esiste!
                        else:
                            st.session_state.refunded_ids.discard(r['Id'])
                    st.rerun() # Ricarica per aggiornare i calcoli
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

    elif menu == "🟢 Giocatori Liberi":
        st.title("🟢 Calciatori Liberi")
        try:
            df_esc = pd.read_csv('esclusi.csv', sep='\t', header=None)
            ids_esc = set(pd.to_numeric(df_esc[0], errors='coerce').dropna().astype(int))
        except: ids_esc = set()
        ids_occ = set(df_base['Id'])
        df_lib = df_all_quot[~df_all_quot['Id'].isin(ids_occ) & ~df_all_quot['Id'].isin(ids_esc)]
        st.dataframe(df_lib.sort_values('FVM', ascending=False)[['Nome', 'R', 'Qt.I', 'FVM']], use_container_width=True, hide_index=True)

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
else: st.error("Carica i file base!")
