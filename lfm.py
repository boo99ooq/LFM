import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM - Gestione Leghe", layout="wide", page_icon="⚽")

# --- FUNZIONI DI CARICAMENTO ---
@st.cache_data
def carica_dati_gioco():
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

def carica_mappa_leghe(nomi_squadre):
    try:
        # Legge il file che hai appena caricato su GitHub
        return pd.read_csv('leghe.csv', encoding='latin1')
    except:
        # Se c'è un errore, crea una lista base
        return pd.DataFrame({'Squadra': nomi_squadre, 'Lega': 'Da Assegnare'})

# --- LOGICA APPLICATIVA ---
dati_fanta = carica_dati_gioco()

if dati_fanta is not None:
    squadre_presenti = sorted(dati_fanta['Squadra_LFM'].unique())
    mappa_leghe = carica_mappa_leghe(squadre_presenti)

    st.sidebar.title("⚽ LFM Manager")
    modalita = st.sidebar.radio("Naviga tra:", ["App Fantacalcio", "⚙️ Configura Leghe"])

    if modalita == "⚙️ Configura Leghe":
        st.title("⚙️ Organizzazione Leghe")
        st.write("Modifica i nomi delle leghe direttamente nella tabella. Una volta finito, scarica il file e caricalo su GitHub.")
        
        # Tabella interattiva per assegnare le squadre
        df_editor = st.data_editor(mappa_leghe, use_container_width=True, num_rows="fixed")
        
        # Pulsante di scaricamento
        csv_data = df_editor.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Scarica leghe.csv aggiornato",
            data=csv_data,
            file_name='leghe.csv',
            mime='text/csv'
        )
        st.info("💡 Carica questo file su GitHub per salvare le modifiche permanentemente.")

    else:
        # UNIONE DATI GIOCATORI + ASSEGNAZIONE LEGA
        # Usiamo il df_editor se stiamo lavorando nella sessione, altrimenti la mappa caricata
        current_map = mappa_leghe 
        df_finale = pd.merge(dati_fanta, current_map, left_on='Squadra_LFM', right_on='Squadra', how='left')

        st.title("🔍 Analisi Rose e Quotazioni")

        # Filtro Lega
        lista_leghe = ["Tutte"] + sorted(list(df_finale['Lega'].unique().astype(str)))
        filtro_lega = st.sidebar.selectbox("Filtra per Lega:", lista_leghe)

        df_filtrato = df_finale if filtro_lega == "Tutte" else df_finale[df_finale['Lega'] == filtro_lega]

        # Sottodivisione Ricerca o Squadra
        sub_tab = st.radio("Cosa cerchi?", ["Giocatore Singolo", "Rosa Completa"], horizontal=True)

        if sub_tab == "Giocatore Singolo":
            cerca = st.text_input("Inserisci nome (anche parziale):")
            if cerca:
                ris = df_filtrato[df_filtrato['Nome'].str.contains(cerca, case=False, na=False)]
                st.dataframe(ris[['Nome', 'R', 'Squadra_LFM', 'Lega', 'Prezzo_Asta', 'FVM']], use_container_width=True)
        
        else:
            squadra_sel = st.selectbox("Seleziona Squadra:", sorted(df_filtrato['Squadra_LFM'].unique()))
            if squadra_sel:
                res_sq = df_filtrato[df_filtrato['Squadra_LFM'] == squadra_sel]
                
                # Statistiche
                m1, m2 = st.columns(2)
                m1.metric("Spesa Asta", f"{int(res_sq['Prezzo_Asta'].sum())} cr")
                m2.metric("Valore Mercato", f"{int(res_sq['FVM'].sum())} cr")
                
                st.table(res_sq[['Nome', 'R', 'Prezzo_Asta', 'FVM']].sort_values(by='R'))

else:
    st.error("Impossibile caricare i dati. Verifica i file CSV su GitHub.")
    
