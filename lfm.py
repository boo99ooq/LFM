import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM - Gestione Leghe", layout="wide")

@st.cache_data
def carica_dati():
    # Caricamento file principali con gestione codifica
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            return pd.merge(df_rose, df_quot, on='Id', how='left')
        except:
            continue
    return None

# Funzione per caricare le assegnazioni leghe
def carica_mappa_leghe(nomi_squadre):
    try:
        return pd.read_csv('leghe.csv')
    except:
        # Se il file non esiste, crea una mappa base con tutte "Senza Lega"
        return pd.DataFrame({'Squadra': nomi_squadre, 'Lega': 'Da Assegnare'})

dati = carica_dati()

if dati is not None:
    squadre_uniche = sorted(dati['Squadra_LFM'].unique())
    mappa_leghe = carica_mappa_leghe(squadre_uniche)

    # --- SIDEBAR NAVIGAZIONE ---
    st.sidebar.title("Menu")
    modalita = st.sidebar.radio("Vai a:", ["⚽ App Fantacalcio", "⚙️ Configura Leghe"])

    if modalita == "⚙️ Configura Leghe":
        st.title("⚙️ Gestione Suddivisione Leghe")
        st.write("Modifica la colonna 'Lega' qui sotto per spostare le squadre. Al termine, copia il tasto in fondo.")
        
        # TABELLA EDITABILE: Qui puoi scrivere direttamente i nomi delle leghe
        edited_df = st.data_editor(mappa_leghe, use_container_width=True, num_rows="fixed")
        
        # Poiché Streamlit non può salvare direttamente su GitHub, generiamo il file da scaricare
        csv = edited_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Scarica file leghe.csv aggiornato",
            data=csv,
            file_name='leghe.csv',
            mime='text/csv',
            help="Scarica questo file e caricalo su GitHub sovrascrivendo quello vecchio"
        )
        
        st.info("💡 Dopo aver scaricato il file, trascinalo nella tua repository GitHub per rendere le modifiche permanenti.")

    else:
        # --- APP DI RICERCA NORMALE ---
        # Uniamo le leghe definite dall'utente ai dati di gioco
        dati_completi = pd.merge(dati, edited_df if 'edited_df' in locals() else mappa_leghe, 
                                 left_on='Squadra_LFM', right_on='Squadra', how='left')
        
        st.title("🔍 Ricerca Giocatori e Rose")
        
        lega_filtro = st.sidebar.selectbox("Filtra per Lega:", ["Tutte"] + list(edited_df['Lega'].unique() if 'edited_df' in locals() else mappa_leghe['Lega'].unique()))
        
        df_visualizza = dati_completi if lega_filtro == "Tutte" else dati_completi[dati_completi['Lega'] == lega_filtro]
        
        nome_cerca = st.text_input("Cerca giocatore:")
        if nome_cerca:
            res = df_visualizza[df_visualizza['Nome'].str.contains(nome_cerca, case=False, na=False)]
            st.dataframe(res[['Nome', 'R', 'Squadra_LFM', 'Lega', 'Prezzo_Asta', 'FVM']])
        else:
            squadra_cerca = st.selectbox("Oppure seleziona squadra:", sorted(df_visualizza['Squadra_LFM'].unique()))
            res_sq = df_visualizza[df_visualizza['Squadra_LFM'] == squadra_cerca]
            st.table(res_sq[['Nome', 'R', 'Prezzo_Asta', 'FVM']])
