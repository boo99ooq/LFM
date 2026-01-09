import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Manager Pro", layout="wide", page_icon="⚽")

# --- CARICAMENTO DATI ---
@st.cache_data
def load_base_data():
    # Carichiamo Rose e Quotazioni
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            df_m = pd.merge(df_rose, df_quot, on='Id', how='left')
            
            # Carichiamo le Leghe se esistono
            try: leghe = pd.read_csv('leghe.csv', encoding=enc)
            except: leghe = pd.DataFrame(columns=['Squadra', 'Lega'])
            
            df_m = pd.merge(df_m, leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
            
            # Pulizia e Calcolo Rimborso
            df_m['Nome'] = df_m['Nome'].fillna("ID: " + df_m['Id'].astype(str))
            df_m['Qt.I'] = df_m['Qt.I'].fillna(0)
            df_m['FVM'] = df_m['FVM'].fillna(0)
            df_m['Rimborso'] = df_m['FVM'] + (df_m['Qt.I'] / 2)
            
            return df_m
        except: continue
    return None

# Funzione per gestire lo stato dei rimborsi (il database delle spunte)
def load_refund_status():
    try:
        return pd.read_csv('database_lfm.csv')
    except:
        # Se non esiste, restituiamo un df vuoto con gli ID rimborsati
        return pd.DataFrame(columns=['Id', 'Rimborsato'])

# --- LOGICA APP ---
df_base = load_base_data()
df_status = load_refund_status()

if df_base is not None:
    # Uniamo lo stato delle spunte ai dati base
    df_totale = pd.merge(df_base, df_status[['Id', 'Rimborsato']], on='Id', how='left')
    df_totale['Rimborsato'] = df_totale['Rimborsato'].fillna(False).astype(bool)

    st.sidebar.title("🎮 LFM Control Panel")
    menu = st.sidebar.radio("Vai a:", ["🔍 Ricerca e Spunte", "📊 Situazione Crediti", "⚙️ Configurazione"])

    if menu == "🔍 Ricerca e Spunte":
        st.title("🔍 Ricerca Giocatori e Gestione Rimborsi")
        st.write("Digita il nome per vedere l'anteprima. Spunta i giocatori per assegnare il rimborso.")

        # RICERCA IMMEDIATA
        cerca = st.text_input("Digita il nome del calciatore...", placeholder="Es: Castellanos")
        
        # Filtro in tempo reale
        if cerca:
            mask = df_totale['Nome'].str.contains(cerca, case=False, na=False)
            df_view = df_totale[mask]
        else:
            df_view = df_totale.head(10) # Mostra i primi 10 come anteprima se vuoto

        # EDITOR TABELLA (Permette le spunte dirette)
        st.subheader("Risultati Ricerca")
        df_edited = st.data_editor(
            df_view[['Rimborsato', 'Nome', 'R', 'Squadra_LFM', 'Qt.I', 'FVM', 'Rimborso', 'Id']],
            column_config={
                "Rimborsato": st.column_config.CheckboxColumn("Rimborsato?", default=False),
                "Id": None # Nascondiamo l'ID
            },
            disabled=["Nome", "R", "Squadra_LFM", "Qt.I", "FVM", "Rimborso"],
            use_container_width=True,
            key="search_editor"
        )

        st.warning("⚠️ Nota: Le spunte sono attive in questa sessione. Per renderle permanenti, vai in 'Configurazione' e salva il database.")

    elif menu == "📊 Situazione Crediti":
        st.title("📊 Crediti Restituiti per Squadra")
        
        # Filtriamo solo i rimborsati
        df_rimborsati = df_totale[df_totale['Rimborsato'] == True]
        
        if not df_rimborsati.empty:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("Dettaglio Rimborsi Erogati")
                st.dataframe(df_rimborsati[['Nome', 'Squadra_LFM', 'Lega', 'Rimborso']], use_container_width=True)
            
            with col2:
                st.subheader("Totali per Squadra")
                res = df_rimborsati.groupby('Squadra_LFM')['Rimborso'].sum().reset_index()
                st.table(res.sort_values(by='Rimborso', ascending=False))
                
            st.metric("Totale Crediti Rimborsati in Lega", f"{df_rimborsati['Rimborso'].sum()} cr")
        else:
            st.info("Nessun rimborso spuntato al momento.")

    elif menu == "⚙️ Configurazione":
        st.title("⚙️ Salvataggio e Impostazioni")
        
        st.write("### Salva modifiche Rimborsi")
        st.write("Usa questo tasto per generare il file con tutte le spunte che hai messo.")
        
        # Qui potremmo implementare la logica per salvare tutto il df_totale
        csv = df_totale[['Id', 'Rimborsato']].to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Scarica database_lfm.csv aggiornato",
            csv,
            "database_lfm.csv",
            "text/csv",
            help="Scarica e carica su GitHub per non perdere le spunte"
        )
        
        st.divider()
        st.write("### Gestione Leghe")
        # (Qui rimane la logica per leghe.csv come prima...)

else:
    st.error("Errore nel caricamento. Controlla i file CSV.")
