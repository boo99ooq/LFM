import streamlit as st
import pandas as pd

# 1. IMPOSTAZIONI DELLA PAGINA
st.set_page_config(page_title="LFM - Manager League", layout="wide", page_icon="⚽")

# 2. FUNZIONE PER CARICARE I DATI (Gestisce automaticamente i caratteri speciali)
@st.cache_data
def carica_dati():
    # Proviamo diverse codifiche per evitare errori con nomi accentati come Montipò
    for codifica in ['latin1', 'cp1252', 'utf-8']:
        try:
            # Carichiamo le rose
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=codifica)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            
            # Carichiamo le quotazioni
            df_quot = pd.read_csv('quot.csv', encoding=codifica)
            
            # Trasformiamo gli ID in numeri per poterli unire
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            
            # Uniamo i due file in uno solo
            return pd.merge(df_rose, df_quot, on='Id', how='inner')
        except:
            continue
    return None

# 3. CREAZIONE DELL'INTERFACCIA NELL'APP
st.title("⚽ LFM - Manager League")
st.markdown("---")

try:
    dati = carica_dati()

    if dati is not None:
        # Menu laterale
        st.sidebar.header("Menu di Navigazione")
        modalita = st.sidebar.selectbox("Cosa vuoi visualizzare?", ["🔍 Cerca Giocatore", "📋 Rosa Completa Squadra"])

        if modalita == "🔍 Cerca Giocatore":
            st.header("Ricerca Rapida Calciatore")
            # La ricerca si attiva scrivendo anche solo una parte del nome
            input_utente = st.text_input("Scrivi qui il nome (es: 'lau' per Lautaro o 'dy' per Dybala):")
            
            if input_utente:
                # Filtro: case=False permette di scrivere minuscolo, na=False evita errori
                risultati = dati[dati['Nome'].str.contains(input_utente, case=False, na=False)]
                
                if not risultati.empty:
                    st.success(f"Ho trovato {len(risultati)} corrispondenze:")
                    # Mostriamo i risultati in una tabella pulita
                    st.dataframe(
                        risultati[['Nome', 'R', 'Squadra_LFM', 'Prezzo_Asta', 'Qt.I', 'FVM']].sort_values(by='Nome'),
                        use_container_width=True
                    )
                else:
                    st.warning("Nessun giocatore trovato con queste lettere.")

        else:
            st.header("Analisi Rose della Lega")
            elenco_squadre = sorted(dati['Squadra_LFM'].unique())
            squadra_scelta = st.selectbox("Seleziona una squadra per vedere tutti i suoi giocatori:", elenco_squadre)
            
            if squadra_scelta:
                df_squadra = dati[dati['Squadra_LFM'] == squadra_scelta]
                
                # Riassunto numerico in alto
                col1, col2, col3 = st.columns(3)
                col1.metric("Giocatori", len(df_squadra))
                col2.metric("Totale Speso", f"{int(df_squadra['Prezzo_Asta'].sum())} cr")
                col3.metric("Valore Mercato (FVM)", f"{int(df_squadra['FVM'].sum())} cr")
                
                # Tabella della squadra
                st.table(df_squadra[['Nome', 'R', 'Prezzo_Asta', 'Qt.I', 'FVM']].sort_values(by='R'))
    else:
        st.error("❌ Non riesco a trovare i file CSV. Controlla che siano nella tua repository GitHub!")

except Exception as errore:
    st.error(f"Si è verificato un problema: {errore}")
