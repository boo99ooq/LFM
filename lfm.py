import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Control Panel", layout="wide", page_icon="⚖️")

# --- 1. CARICAMENTO DATI BASE ---
@st.cache_data
def load_base_data():
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            df = pd.merge(df_rose, df_quot, on='Id', how='left')
            try:
                leghe = pd.read_csv('leghe.csv', encoding=enc)
                df = pd.merge(df, leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
            except:
                df['Lega'] = 'Da Assegnare'
            df['Nome'] = df['Nome'].fillna("ID: " + df['Id'].astype(int, errors='ignore').astype(str))
            df['Qt.I'] = df['Qt.I'].fillna(0)
            df['FVM'] = df['FVM'].fillna(0)
            df['Rimborso'] = df['FVM'] + (df['Qt.I'] / 2)
            return df
        except: continue
    return None

# --- 2. GESTIONE STATO RIMBORSI (SESSION STATE) ---
if 'refunded_ids' not in st.session_state:
    try:
        db_persistente = pd.read_csv('database_lfm.csv')
        st.session_state.refunded_ids = set(db_persistente[db_persistente['Rimborsato'] == True]['Id'].tolist())
    except:
        st.session_state.refunded_ids = set()

# --- 3. LOGICA PRINCIPALE ---
df_base = load_base_data()

if df_base is not None:
    # Applichiamo lo stato dei rimborsi basandoci sull'ID (Logica Globale)
    df_base['Rimborsato'] = df_base['Id'].isin(st.session_state.refunded_ids)

    st.sidebar.title("🎮 LFM Admin Panel")
    menu = st.sidebar.radio("Naviga:", ["🏠 Dashboard Leghe", "🔍 Ricerca e Spunte", "⚙️ Configurazione"])

    # --- PAGINA 1: DASHBOARD ---
    if menu == "🏠 Dashboard Leghe":
        st.title("🏠 Situazione Rimborsi per Lega")
        
        leghe_disponibili = [l for l in df_base['Lega'].unique() if pd.notna(l) and l != 'nan']
        leghe_disponibili = sorted(leghe_disponibili)

        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_disponibili):
            with cols[i % 2]:
                with st.container(border=True):
                    st.subheader(f"🏆 {nome_lega}")
                    
                    # Prendiamo tutte le squadre della lega
                    squadre_lega = df_base[df_base['Lega'] == nome_lega]['Squadra_LFM'].unique()
                    
                    # Calcoliamo i rimborsi
                    df_lega = df_base[df_base['Lega'] == nome_lega]
                    res = df_lega[df_lega['Rimborsato'] == True].groupby('Squadra_LFM')['Rimborso'].sum().reset_index()
                    
                    # Uniamo con tutte le squadre per mostrare anche chi ha 0
                    tabella_finale = pd.DataFrame({'Squadra': squadre_lega})
                    tabella_finale = pd.merge(tabella_finale, res, left_on='Squadra', right_on='Squadra_LFM', how='left').fillna(0)
                    
                    st.table(tabella_finale[['Squadra', 'Rimborso']].sort_values(by='Squadra'))
                    st.write(f"**Totale Lega:** {tabella_finale['Rimborso'].sum()} cr")

    # --- PAGINA 2: RICERCA E SPUNTE ---
    elif menu == "🔍 Ricerca e Spunte":
        st.title("🔍 Gestione Rimborsi Globali")
        st.info("Basta spuntare UN giocatore per rimborsarlo in TUTTE le squadre della lega.")

        cerca = st.text_input("Digita il nome del calciatore (es: Castellanos):")
        
        # Mostriamo solo una riga per ogni calciatore unico nella ricerca per evitare confusione
        df_unique_players = df_base.drop_duplicates('Id')
        
        if cerca:
            df_view = df_unique_players[df_unique_players['Nome'].str.contains(cerca, case=False, na=False)]
        else:
            df_view = df_unique_players.head(10)

        # Editor
        edited_df = st.data_editor(
            df_view[['Rimborsato', 'Nome', 'R', 'Qt.I', 'FVM', 'Rimborso', 'Id']],
            column_config={"Rimborsato": st.column_config.CheckboxColumn("Svincola", default=False), "Id": None},
            disabled=["Nome", "R", "Qt.I", "FVM", "Rimborso"],
            use_container_width=True,
            key="global_editor"
        )

        # Se l'utente interagisce con l'editor, aggiorniamo il set globale degli ID
        if st.button("Salva Modifiche Sessione"):
            for index, row in edited_df.iterrows():
                player_id = row['Id']
                if row['Rimborsato']:
                    st.session_state.refunded_ids.add(player_id)
                else:
                    st.session_state.refunded_ids.discard(player_id)
            st.success("Spunte sincronizzate con successo in tutto il database!")
            st.rerun()

    # --- PAGINA 3: CONFIGURAZIONE ---
    elif menu == "⚙️ Configurazione":
        st.title("⚙️ Salvataggio Permanente")
        st.write("Per non perdere le spunte alla chiusura del browser, scarica questo file e caricalo su GitHub.")
        
        # Creiamo il DF da salvare
        df_save = pd.DataFrame({'Id': list(st.session_state.refunded_ids)})
        df_save['Rimborsato'] = True
        
        csv = df_save.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Scarica database_lfm.csv", csv, "database_lfm.csv", "text/csv")
        
        st.divider()
        st.write("### Altri file")
        # Pulsanti per leghe.csv...

else:
    st.error("Controlla i file CSV nella repository.")
