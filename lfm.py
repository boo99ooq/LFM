import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Admin Pro", layout="wide", page_icon="⚖️")

# --- 1. FUNZIONI DI CARICAMENTO ---
@st.cache_data
def load_data():
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            # Caricamento Rose
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            
            # Caricamento Quotazioni
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            
            # Pulizia ID
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            
            # Merge Rose + Quotazioni
            df = pd.merge(df_rose, df_quot, on='Id', how='left')
            
            # Merge con Leghe (Pulizia nomi per evitare l'errore Serie A/Fiorentina)
            try: 
                leghe = pd.read_csv('leghe.csv', encoding=enc)
                leghe.columns = ['Squadra', 'Lega']
                leghe['Squadra'] = leghe['Squadra'].str.strip()
                leghe['Lega'] = leghe['Lega'].str.strip()
                df['Squadra_LFM'] = df['Squadra_LFM'].str.strip()
                df = pd.merge(df, leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
            except: 
                df['Lega'] = 'Da Assegnare'

            # Pulizia dati e Calcolo Rimborso
            df['Nome'] = df['Nome'].fillna("ID: " + df['Id'].astype(int, errors='ignore').astype(str))
            df['Qt.I'] = pd.to_numeric(df['Qt.I'], errors='coerce').fillna(0)
            df['FVM'] = pd.to_numeric(df['FVM'], errors='coerce').fillna(0)
            df['Prezzo_Asta'] = pd.to_numeric(df['Prezzo_Asta'], errors='coerce').fillna(0)
            df['Rimborso'] = df['FVM'] + (df['Qt.I'] / 2)
            
            return df
        except: continue
    return None

# --- 2. GESTIONE STATO (SESSION STATE) ---
if 'refunded_ids' not in st.session_state:
    try:
        # Carichiamo le spunte salvate dal file
        db_p = pd.read_csv('database_lfm.csv')
        st.session_state.refunded_ids = set(db_p[db_p['Rimborsato'] == True]['Id'].tolist())
    except:
        st.session_state.refunded_ids = set()

# --- 3. LOGICA PRINCIPALE ---
df_base = load_data()

if df_base is not None:
    # Applichiamo la spunta GLOBALE basata sull'ID
    df_base['Rimborsato'] = df_base['Id'].isin(st.session_state.refunded_ids)

    # Sidebar
    st.sidebar.title("🎮 LFM Admin Panel")
    budget_iniziale = st.sidebar.number_input("Budget Iniziale Crediti:", value=500, step=50)
    menu = st.sidebar.radio("Naviga:", ["🏠 Dashboard Leghe", "🔍 Ricerca e Spunte", "⚙️ Configurazione"])

    # --- PAGINA 1: DASHBOARD ---
    if menu == "🏠 Dashboard Leghe":
        st.title("🏠 Riepilogo Crediti e Rimborsi")
        st.info(f"Budget Iniziale: {budget_iniziale} cr | Formula Residuo: Budget - Spesa + Rimborsi")
        
        # Filtriamo le leghe per ignorare eventuali errori come "Serie A"
        # Mostriamo solo le 4 leghe principali (A, B, C, D) o quelle che contengono la parola "Lega"
        leghe_valide = sorted([l for l in df_base['Lega'].unique() if pd.notna(l) and "Lega" in str(l)])
        
        if not leghe_valide:
            st.warning("Nessuna lega trovata. Controlla il file leghe.csv")
            leghe_valide = sorted(df_base['Lega'].unique().astype(str))

        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_valide):
            with cols[i % 2]:
                with st.container(border=True):
                    st.subheader(f"🏆 {nome_lega}")
                    
                    df_l = df_base[df_base['Lega'] == nome_lega]
                    stats = []
                    for sq in sorted(df_l['Squadra_LFM'].unique()):
                        df_sq = df_l[df_l['Squadra_LFM'] == sq]
                        spesa = df_sq['Prezzo_Asta'].sum()
                        rimborso = df_sq[df_sq['Rimborsato'] == True]['Rimborso'].sum()
                        residuo = budget_iniziale - spesa + rimborso
                        stats.append({
                            'Squadra': sq, 
                            'Rimborso Tot.': int(rimborso), 
                            'Crediti Residui': int(residuo)
                        })
                    
                    st.table(pd.DataFrame(stats))

    # --- PAGINA 2: RICERCA E SPUNTE ---
    elif menu == "🔍 Ricerca e Spunte":
        st.title("🔍 Gestione Rimborsi Globali")
        st.markdown("Spunta un calciatore qui sotto: il rimborso verrà applicato a **tutte le squadre** che lo possiedono.")

        cerca = st.text_input("Cerca calciatore (es: Castellanos):", placeholder="Inizia a scrivere...")
        
        # Lista unica di giocatori per la spunta globale
        df_display = df_base.drop_duplicates('Id').copy()
        
        if cerca:
            df_filtered = df_display[df_display['Nome'].str.contains(cerca, case=False, na=False)]
        else:
            df_filtered = df_display.head(10)

        # Editor Tabella
        res_editor = st.data_editor(
            df_filtered[['Rimborsato', 'Nome', 'R', 'Qt.I', 'FVM', 'Rimborso', 'Id']],
            column_config={
                "Rimborsato": st.column_config.CheckboxColumn("Svincola", default=False), 
                "Id": None
            },
            disabled=["Nome", "R", "Qt.I", "FVM", "Rimborso"],
            use_container_width=True,
            key="global_sync_editor"
        )

        if st.button("💾 Salva Modifiche Sessione"):
            # Sincronizziamo gli ID basandoci sulla tabella modificata
            for _, row in res_editor.iterrows():
                if row['Rimborsato']: st.session_state.refunded_ids.add(row['Id'])
                else: st.session_state.refunded_ids.discard(row['Id'])
            st.success("Sincronizzazione completata! I rimborsi sono stati aggiornati in tutte le leghe.")
            st.rerun()

    # --- PAGINA 3: CONFIGURAZIONE ---
    elif menu == "⚙️ Configurazione":
        st.title("⚙️ Gestione File")
        
        st.subheader("1. Salva i Rimborsi")
        df_save = pd.DataFrame({'Id': list(st.session_state.refunded_ids), 'Rimborsato': True})
        st.download_button("📥 Scarica database_lfm.csv", df_save.to_csv(index=False).encode('utf-8'), "database_lfm.csv", "text/csv")
        st.caption("Scarica e carica questo file su GitHub per non perdere le spunte.")

        st.divider()
        st.subheader("2. Verifica Mappatura Fiorentina")
        st.write("Se vedi la Fiorentina in 'Serie A', controlla qui sotto come è mappata:")
        try:
            leghe_check = pd.read_csv('leghe.csv', encoding='latin1')
            st.dataframe(leghe_check[leghe_check.iloc[:,0].str.contains("Fiorentina", case=False, na=False)])
        except: st.write("File leghe.csv non trovato.")

else:
    st.error("Errore: Verifica che i file CSV siano su GitHub.")
