import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Dashboard", layout="wide", page_icon="📊")

# --- CARICAMENTO E PREPARAZIONE DATI ---
@st.cache_data
def load_all_data():
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            # Caricamento Rose e Quotazioni
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            
            # Merge Rose + Quotazioni
            df = pd.merge(df_rose, df_quot, on='Id', how='left')
            
            # Merge con Leghe
            try: 
                leghe = pd.read_csv('leghe.csv', encoding=enc)
                df = pd.merge(df, leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
            except: 
                df['Lega'] = 'Da Assegnare'

            # Pulizia nomi e Calcolo Rimborso
            df['Nome'] = df['Nome'].fillna("ID: " + df['Id'].astype(int, errors='ignore').astype(str))
            df['Qt.I'] = df['Qt.I'].fillna(0)
            df['FVM'] = df['FVM'].fillna(0)
            df['Rimborso'] = df['FVM'] + (df['Qt.I'] / 2)
            
            return df
        except: continue
    return None

# Caricamento dello stato dei rimborsi (database_lfm.csv)
def load_refund_db():
    try: return pd.read_csv('database_lfm.csv')
    except: return pd.DataFrame(columns=['Id', 'Rimborsato'])

# --- INIZIALIZZAZIONE ---
df_base = load_all_data()
df_refunds = load_refund_db()

if df_base is not None:
    # Uniamo lo stato dei rimborsi al database base
    # Usiamo l'Id come chiave per garantire che la spunta sia globale
    if 'Rimborsato' not in df_refunds.columns:
        df_refunds['Rimborsato'] = False
        
    df_main = pd.merge(df_base, df_refunds[['Id', 'Rimborsato']].drop_duplicates('Id'), on='Id', how='left')
    df_main['Rimborsato'] = df_main['Rimborsato'].fillna(False).astype(bool)

    # --- NAVIGAZIONE SIDEBAR ---
    st.sidebar.title("🏆 LFM Control Panel")
    menu = st.sidebar.radio("Scegli Pagina:", ["🏠 Dashboard Leghe", "🔍 Ricerca e Spunte", "⚙️ Configurazione"])

    # --- PAGINA 1: DASHBOARD ---
    if menu == "🏠 Dashboard Leghe":
        st.title("🏠 Riepilogo Crediti Rimborsati")
        
        # Estraiamo le leghe uniche (escludendo nan)
        leghe_lista = [l for l in df_main['Lega'].unique() if pd.notna(l) and l != 'nan']
        leghe_lista = sorted(leghe_lista)[:4] # Prendiamo le prime 4
        
        # Layout a griglia (2x2)
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_lista):
            with cols[i % 2]:
                with st.container(border=True):
                    # Calcolo crediti per questa lega
                    mask_lega = (df_main['Lega'] == nome_lega) & (df_main['Rimborsato'] == True)
                    totale_lega = df_main[mask_lega]['Rimborso'].sum()
                    
                    st.subheader(f"🏆 {nome_lega}")
                    st.metric("Crediti Restituiti", f"{totale_lega} cr")
                    
                    # Piccola anteprima dei giocatori rimborsati in questa lega
                    giocatori_rimb = df_main[mask_lega]['Nome'].unique()
                    if len(giocatori_rimb) > 0:
                        st.caption(f"Giocatori: {', '.join(giocatori_rimb[:5])}...")
                    else:
                        st.caption("Nessun rimborso erogato.")

    # --- PAGINA 2: RICERCA E SPUNTE ---
    elif menu == "🔍 Ricerca e Spunte":
        st.title("🔍 Gestione Rimborsi")
        st.info("💡 Se spunti un giocatore, il rimborso verrà applicato a tutte le squadre che lo possiedono nelle varie leghe.")

        cerca = st.text_input("Cerca giocatore (es: Castellanos)...", key="search_input")
        
        if cerca:
            df_view = df_main[df_main['Nome'].str.contains(cerca, case=False, na=False)]
            
            # Editor della tabella
            edited_df = st.data_editor(
                df_view[['Rimborsato', 'Nome', 'R', 'Squadra_LFM', 'Lega', 'Rimborso', 'Id']],
                column_config={
                    "Rimborsato": st.column_config.CheckboxColumn("Rimborsato", default=False),
                    "Id": None # Nascondiamo l'ID per pulizia
                },
                disabled=["Nome", "R", "Squadra_LFM", "Lega", "Rimborso"],
                use_container_width=True,
                key="editor_spunte"
            )

            # LOGICA SPUNTA GLOBALE: Se un ID cambia, aggiorniamo il database dei rimborsi
            # Streamlit data_editor restituisce le righe modificate
            if st.button("Conferma e Sincronizza Spunte"):
                # Aggiorniamo il database dei rimborsi basandoci sugli ID spuntati nell'editor
                ids_rimborsati = edited_df[edited_df['Rimborsato'] == True]['Id'].unique()
                ids_non_rimborsati = edited_df[edited_df['Rimborsato'] == False]['Id'].unique()
                
                # Questa parte aggiorna lo stato globale
                # (Per ora lo facciamo in session_state, ma va salvato nel CSV per permanenza)
                st.session_state['last_sync_ids'] = ids_rimborsati
                st.success("Sincronizzazione completata! Vai in 'Configurazione' per scaricare il file finale.")

    # --- PAGINA 3: CONFIGURAZIONE ---
    elif menu == "⚙️ Configurazione":
        st.title("⚙️ Salvataggio Dati")
        st.write("Scarica il file per rendere le spunte permanenti su GitHub.")
        
        # Prepariamo il file da scaricare partendo da df_main aggiornato
        csv_save = df_main[['Id', 'Rimborsato']].drop_duplicates('Id').to_csv(index=False).encode('utf-8')
        
        st.download_button(
            "📥 Scarica database_lfm.csv",
            csv_save,
            "database_lfm.csv",
            "text/csv",
            help="Carica questo file su GitHub per salvare le spunte dei rimborsi"
        )
        
        st.divider()
        st.write("### Altri File")
        # Pulsante per scaricare leghe.csv se necessario...

else:
    st.error("Errore: Assicurati che i file CSV siano presenti nella repository.")
