import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="LFM - Registro Rimborsi", layout="wide", page_icon="📝")

# --- FUNZIONI CARICAMENTO ---
@st.cache_data
def carica_dati_completi():
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            df_merged = pd.merge(df_rose, df_quot, on='Id', how='left')
            df_merged['Qt.I'] = df_merged['Qt.I'].fillna(0)
            df_merged['FVM'] = df_merged['FVM'].fillna(0)
            df_merged['Rimborso'] = df_merged['FVM'] + (df_merged['Qt.I'] / 2)
            return df_merged
        except:
            continue
    return None

def get_mappe():
    try: leghe = pd.read_csv('leghe.csv', encoding='latin1')
    except: leghe = pd.DataFrame(columns=['Squadra', 'Lega'])
    try: storico = pd.read_csv('rimborsi_storico.csv', encoding='latin1')
    except: storico = pd.DataFrame(columns=['Id','Nome','Squadra_LFM','Lega','Rimborso_Ottenuto','Data_Sessione'])
    return leghe, storico

# --- LOGICA ---
dati = carica_dati_completi()
leghe, storico = get_mappe()

st.sidebar.title("⚽ LFM Admin")
modalita = st.sidebar.radio("Vai a:", ["App Fantacalcio", "⚙️ Configura Leghe", "📝 Sessioni Rimborsi"])

if modalita == "📝 Sessioni Rimborsi":
    st.title("📝 Gestione Sessioni e Rimborsi")
    
    tab1, tab2 = st.tabs(["Spunta Rimborsi", "Database Storico"])
    
    with tab1:
        st.subheader("Seleziona i giocatori rimborsati in questa sessione")
        # Uniamo i dati per avere la Lega anche qui
        df_l = pd.merge(dati, leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
        
        # Filtro veloce per trovare i giocatori da rimborsare
        filtro_nome = st.text_input("Cerca giocatore da spuntare:")
        if filtro_nome:
            df_l = df_l[df_l['Nome'].str.contains(filtro_nome, case=False, na=False)]
        
        # Selezione multipla
        scelti = st.multiselect("Seleziona i giocatori rimborsati:", 
                                options=df_l['Nome'].unique(),
                                help="Puoi selezionare più giocatori contemporaneamente")
        
        if scelti:
            st.write("### Riepilogo Sessione Corrente")
            nuovi_rimborsi = df_l[df_l['Nome'].isin(scelti)][['Id', 'Nome', 'Squadra_LFM', 'Lega', 'Rimborso']]
            nuovi_rimborsi['Data_Sessione'] = st.date_input("Data della sessione ufficiale:", datetime.now())
            st.dataframe(nuovi_rimborsi)
            
            if st.button("Aggiungi al Database Storico"):
                aggiornato = pd.concat([storico, nuovi_rimborsi.rename(columns={'Rimborso': 'Rimborso_Ottenuto'})], ignore_index=True)
                st.session_state['db_aggiornato'] = aggiornato
                st.success("Aggiunti! Ora scarica il file e caricalo su GitHub.")

    with tab2:
        st.subheader("Database Rimborsi Ufficiali")
        db_da_mostrare = st.session_state.get('db_aggiornato', storico)
        st.dataframe(db_da_mostrare, use_container_width=True)
        
        # Calcolo rimborsi totali per squadra
        if not db_da_mostrare.empty:
            st.write("### Totali Rimborsi per Squadra")
            totali = db_da_mostrare.groupby('Squadra_LFM')['Rimborso_Ottenuto'].sum().reset_index()
            st.table(totali.sort_values(by='Rimborso_Ottenuto', ascending=False))

        # Download button
        csv_storico = db_da_mostrare.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Scarica rimborsi_storico.csv", csv_storico, "rimborsi_storico.csv", "text/csv")

elif modalita == "⚙️ Configura Leghe":
    # (Mantenere il codice precedente per la gestione leghe)
    st.title("⚙️ Configurazione Leghe")
    df_ed = st.data_editor(leghe, use_container_width=True)
    if st.download_button("Scarica leghe.csv", df_ed.to_csv(index=False).encode('utf-8'), "leghe.csv"):
        st.info("Caricalo su GitHub.")

else:
    # (Mantenere il codice precedente per l'App Fantacalcio con i filtri)
    st.title("⚽ App Fantacalcio")
    # ... (codice ricerca e visualizzazione rose)
