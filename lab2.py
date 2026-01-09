import streamlit as st
import pandas as pd
import math

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
            
            df_owned['Rimborso_Star'] = df_owned['FVM'] + (df_owned['Qt.I'] / 2)
            df_owned['Rimborso_Taglio'] = (df_owned['FVM'] + df_owned['Qt.I']) / 2
            
            return df_owned, df_quot
        except: continue
    return None, None

# --- 2. LOGICA STADI ---
def calculate_stadium_bonus(capienza):
    casa = capienza / 20
    # Arrotondamento per difetto allo 0.5 più vicino
    trasferta = math.floor((casa / 2) * 2) / 2
    return casa, trasferta

def load_stadi():
    try:
        df_s = pd.read_csv('stadi.csv')
        df_s['Squadra'] = df_s['Squadra'].str.strip()
        return df_s
    except:
        return pd.DataFrame(columns=['Squadra', 'Lega', 'Stadio'])

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

MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]

# --- 4. COSTRUZIONE DATI ---
df_base, df_all_quot = load_static_data()
df_stadi = load_stadi()

if df_base is not None:
    df_base = pd.merge(df_base, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato_Star'] = df_base['Id'].isin(st.session_state.refunded_ids)
    df_base['Taglio_Key'] = df_base['Id'].astype(int).astype(str) + "_" + df_base['Squadra_LFM'].astype(str)
    df_base['Rimborsato_Taglio'] = df_base['Taglio_Key'].isin(st.session_state.tagli_map)

    st.sidebar.title("⚖️ LFM Admin")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🏟️ Bonus Stadio", "🏃 Svincolati *", "✂️ Tagli Volontari", "📊 Ranking FVM", "📋 Visualizza Rose", "🟢 Giocatori Liberi", "⚙️ Gestione Squadre"])

    # --- 🏠 DASHBOARD ---
    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti e Statistiche")
        leghe_effettive = [l for l in ORDINE_LEGHE if l in df_base['Lega'].values]
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_effettive):
            with cols[i % 2]:
                df_l = df_base[df_base['Lega'] == nome_lega]
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
                    # Info Stadio per il box
                    info_s = df_stadi[df_stadi['Squadra'] == sq['Squadra_LFM']]
                    capienza_label = f"🏟️ {int(info_s['Stadio'].values[0])}k" if not info_s.empty else ""
                    
                    colore_count = "#81c784" if 25 <= sq['Num_Giocatori'] <= 35 else "#ef5350"
                    
                    st.markdown(f"""<div style="background-color: {bg_color}; padding: 15px; border-radius: 12px; margin-bottom: 12px; border: 1px solid rgba(255,255,255,0.2); color: white;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <b style="font-size:16px;">{sq['Squadra_LFM']}</b>
                            <span style="font-size:11px; opacity:0.8;">{capienza_label}</span>
                            <span style="background:{colore_count}; color:white; padding:2px 8px; border-radius:10px; font-size:11px;">🏃 {int(sq['Num_Giocatori'])}/25-35</span>
                        </div>
                        <div style="font-size:20px; font-weight:bold; margin-top:5px;">{int(sq['Totale'])} <small>cr</small></div>
                    </div>""", unsafe_allow_html=True)

    # --- 🏟️ BONUS STADIO (NUOVA PAGINA) ---
    elif menu == "🏟️ Bonus Stadio":
        st.title("🏟️ Calcolo Bonus Stadio")
        st.info("Regola: Casa (Capienza/20) | Fuori (Casa/2 arrotondato per difetto a 0.5)")
        
        c1, c2 = st.columns(2)
        casa_sq = c1.selectbox("Squadra in Casa:", sorted(df_base['Squadra_LFM'].unique()))
        fuori_sq = c2.selectbox("Squadra in Trasferta:", sorted(df_base['Squadra_LFM'].unique()))
        
        if casa_sq and fuori_sq:
            s_casa = df_stadi[df_stadi['Squadra'] == casa_sq]
            s_fuori = df_stadi[df_stadi['Squadra'] == fuori_sq]
            
            cap_casa = int(s_casa['Stadio'].values[0]) if not s_casa.empty else 0
            cap_fuori = int(s_fuori['Stadio'].values[0]) if not s_fuori.empty else 0
            
            b_casa_pieno, _ = calculate_stadium_bonus(cap_casa)
            _, b_fuori_mezzo = calculate_stadium_bonus(cap_fuori)
            
            col1, col2 = st.columns(2)
            col1.metric(f"Bonus {casa_sq}", f"+{b_casa_pieno}")
            col2.metric(f"Bonus {fuori_sq}", f"+{b_fuori_mezzo}")
            
            st.divider()
            st.write(f"Dettagli: {casa_sq} ({cap_casa}k posti) | {fuori_sq} ({cap_fuori}k posti)")

    # --- (PAGINE SVINCOLATI, TAGLI, RANKING, ROSE, LIBERI rimangono identiche) ---
    # [Inserire qui le sezioni del codice precedente per brevità]

    # --- ⚙️ GESTIONE SQUADRE ---
    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Configurazione")
        # Aggiunta gestione stadi
        st.subheader("🏟️ Database Stadi")
        st.dataframe(df_stadi, use_container_width=True, hide_index=True)
        st.download_button("Scarica Template Stadi", df_stadi.to_csv(index=False).encode('utf-8'), "stadi.csv")
        
        st.divider()
        # Gestione Crediti Classica
        edited = st.data_editor(st.session_state.df_leghe_full, use_container_width=True, hide_index=True)
        if st.button("Salva Modifiche"):
            st.session_state.df_leghe_full = edited; st.success("Dati aggiornati!"); st.rerun()

else: st.error("Carica i file CSV!")
