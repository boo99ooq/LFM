import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Control Panel", layout="wide", page_icon="⚖️")

# --- 1. CARICAMENTO DATI ---
@st.cache_data
def load_all_data():
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            
            # Merge Rose + Quotazioni
            df = pd.merge(df_rose, df_quot, on='Id', how='left')
            
            # Caricamento Leghe (con pulizia nomi per evitare l'errore Fiorentina)
            try: 
                leghe = pd.read_csv('leghe.csv', encoding=enc)
                leghe['Squadra'] = leghe['Squadra'].str.strip()
                df['Squadra_LFM'] = df['Squadra_LFM'].str.strip()
                df = pd.merge(df, leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
            except: 
                df['Lega'] = 'Da Assegnare'

            # Pulizia e Calcolo Rimborso
            df['Nome'] = df['Nome'].fillna("ID: " + df['Id'].astype(int, errors='ignore').astype(str))
            df['Qt.I'] = df['Qt.I'].fillna(0).astype(float)
            df['FVM'] = df['FVM'].fillna(0).astype(float)
            df['Prezzo_Asta'] = df['Prezzo_Asta'].fillna(0).astype(float)
            df['Rimborso'] = df['FVM'] + (df['Qt.I'] / 2)
            
            return df
        except: continue
    return None

# --- 2. GESTIONE DATABASE PERSISTENTE (SESSION STATE) ---
if 'refunded_ids' not in st.session_state:
    try:
        db_p = pd.read_csv('database_lfm.csv')
        st.session_state.refunded_ids = set(db_p[db_p['Rimborsato'] == True]['Id'].tolist())
    except:
        st.session_state.refunded_ids = set()

# --- 3. LOGICA APP ---
df_base = load_all_data()

if df_base is not None:
    # Applichiamo lo stato dei rimborsi basandoci sull'ID (LOGICA GLOBALE)
    df_base['Rimborsato'] = df_base['Id'].isin(st.session_state.refunded_ids)

    # Sidebar
    st.sidebar.title("🎮 LFM Admin Panel")
    budget_iniziale = st.sidebar.number_input("Budget Iniziale Crediti:", value=500, step=50)
    menu = st.sidebar.radio("Naviga:", ["🏠 Dashboard Leghe", "🔍 Ricerca e Spunte", "⚙️ Configurazione"])

    # --- PAGINA 1: DASHBOARD ---
    if menu == "🏠 Dashboard Leghe":
        st.title("🏠 Situazione Crediti e Rimborsi")
        
        # Pulizia lista leghe (escludiamo nan e prendiamo solo i nomi validi)
        df_base['Lega'] = df_base['Lega'].fillna("Non Assegnata")
        leghe_disponibili = sorted([l for l in df_base['Lega'].unique() if l != "Non Assegnata"])
        
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_disponibili):
            with cols[i % 2]:
                with st.container(border=True):
                    st.subheader(f"🏆 {nome_lega}")
                    
                    # Dati della lega
                    df_l = df_base[df_base['Lega'] == nome_lega]
                    
                    # Calcoli per squadra
                    stats = []
                    for sq in sorted(df_l['Squadra_LFM'].unique()):
                        df_sq = df_l[df_l['Squadra_LFM'] == sq]
                        spesa = df_sq['Prezzo_Asta'].sum()
                        rimborso = df_sq[df_sq['Rimborsato'] == True]['Rimborso'].sum()
                        residuo = budget_iniziale - spesa + rimborso
                        stats.append({'Squadra': sq, 'Spesa': int(spesa), 'Rimborso': int(rimborso), 'Residuo': int(residuo)})
                    
                    st.table(pd.DataFrame(stats))

    # --- PAGINA 2: RICERCA E SPUNTE ---
    elif menu == "🔍 Ricerca e Spunte":
        st.title("🔍 Gestione Rimborsi")
        st.info("Spunta un giocatore qui: verrà rimborsato automaticamente in tutte le squadre di tutte le leghe.")

        cerca = st.text_input("Cerca calciatore (anteprima istantanea):")
        
        # Mostriamo ogni giocatore una sola volta per la spunta globale
        df_display = df_base.drop_duplicates('Id').copy()
        
        if cerca:
            df_filtered = df_display[df_display['Nome'].str.contains(cerca, case=False, na=False)]
        else:
            df_filtered = df_display.head(10)

        # Editor
        res_editor = st.data_editor(
            df_filtered[['Rimborsato', 'Nome', 'R', 'Qt.I', 'FVM', 'Rimborso', 'Id']],
            column_config={"Rimborsato": st.column_config.CheckboxColumn("Svincola", default=False), "Id": None},
            disabled=["Nome", "R", "Qt.I", "FVM", "Rimborso"],
            use_container_width=True,
            key="global_sync_editor"
        )

        if st.button("💾 Conferma Modifiche Sessione"):
            for _, row in res_editor.iterrows():
                if row['Rimborsato']: st.session_state.refunded_ids.add(row['Id'])
                else: st.session_state.refunded_ids.discard(row['Id'])
            st.success("Sincronizzazione completata! Ricorda di salvare in 'Configurazione'.")
            st.rerun()

    # --- PAGINA 3: CONFIGURAZIONE ---
    elif menu == "⚙️ Configurazione":
        st.title("⚙️ Salvataggio")
        df_save = pd.DataFrame({'Id': list(st.session_state.refunded_ids), 'Rimborsato': True})
        st.download_button("📥 Scarica database_lfm.csv", df_save.to_csv(index=False).encode('utf-8'), "database_lfm.csv", "text/csv")
        st.warning("Dopo il download, caricalo su GitHub per non perdere le spunte.")

else:
    st.error("File non trovati.")
