import streamlit as st
import pandas as pd
import numpy as np
from github import Github
import io
import time
from datetime import datetime

# --- 1. CONFIGURAZIONE E COSTANTI ---
st.set_page_config(page_title="LFM Mercato - Golden Edition", layout="wide", page_icon="⚖️")

ADMIN_SQUADRE = ["Liverpool Football Club", "Villarreal", "Reggina Calcio 1914", "Siviglia"]
CHIUSURA_MERCATO = datetime(2026, 8, 10)

ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

def format_num(num):
    try:
        val = float(num)
        return str(int(val)) if val == int(val) else str(round(val, 1))
    except:
        return "0"

# --- 2. CONNESSIONE GITHUB ---
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except Exception as e:
    st.error(f"❌ Errore Secrets! Verifica GITHUB_TOKEN e REPO_NAME nelle impostazioni di QUESTA app su Streamlit Cloud (Manage app → Settings → Secrets). Dettaglio: {e}")
    st.stop()

# --- 3. FUNZIONI API GITHUB ---
def get_df_from_github(file_path):
    try:
        content = repo.get_contents(file_path)
        df = pd.read_csv(io.StringIO(content.decoded_content.decode('utf-8')))
        if 'Rimborso' in df.columns and 'Totale' not in df.columns:
            df = df.rename(columns={'Rimborso': 'Totale'})
        return df
    except Exception as e:
        st.warning(f"⚠️ Impossibile leggere '{file_path}' da GitHub: {e}")
        return pd.DataFrame()

def save_to_github_direct(file_path, df, message):
    csv_content = df.to_csv(index=False)
    try:
        contents = repo.get_contents(file_path)
        repo.update_file(contents.path, message, csv_content, contents.sha)
    except:
        repo.create_file(file_path, message, csv_content)

# --- 3bis. LOGIN ---
if 'loggato' not in st.session_state:
    st.session_state.loggato = False
    st.session_state.squadra = None

if not st.session_state.loggato:
    st.title("🔒 LFM Mercato - Accesso")
    df_leghe_login = get_df_from_github('leghe.csv')
    if df_leghe_login.empty or 'PIN' not in df_leghe_login.columns:
        st.error("Impossibile caricare leghe.csv (o manca la colonna PIN).")
        st.stop()

    lega_login = st.selectbox("Lega", sorted(df_leghe_login['Lega'].unique()))
    squadre_lega = sorted(df_leghe_login[df_leghe_login['Lega'] == lega_login]['Squadra'].unique())
    squadra_login = st.selectbox("Squadra", squadre_lega)
    pin_login = st.text_input("PIN Segreto", type="password")

    if st.button("🚀 ACCEDI"):
        match = df_leghe_login[df_leghe_login['Squadra'] == squadra_login]
        if match.empty:
            st.error(f"❌ Squadra '{squadra_login}' non trovata.")
        elif str(pin_login).strip() == str(match['PIN'].values[0]).strip():
            st.session_state.loggato = True
            st.session_state.squadra = squadra_login
            st.rerun()
        else:
            st.error("❌ PIN errato. Riprova.")
    st.stop()

is_admin = st.session_state.squadra in ADMIN_SQUADRE

with st.sidebar:
    ruolo_label = "👑 Admin" if is_admin else "👤 Manager"
    st.markdown(f"**{st.session_state.squadra}**  \n{ruolo_label}")
    if st.button("🔓 Esci"):
        st.session_state.loggato = False
        st.session_state.squadra = None
        st.rerun()
    st.divider()

# --- 4. CARICAMENTO E PULIZIA PROFONDA (Versione Unificata) ---
@st.cache_data(ttl=2)
def load_all_data():
    # Caricamento file da GitHub
    df_rosters = get_df_from_github('fantamanager-2021-rosters.csv')
    df_leghe = get_df_from_github('leghe.csv')
    
    # Caricamento file locali con gestione errori
    try:
        df_quot = pd.read_csv('quot.csv', sep=None, engine='python', encoding='latin1')
        df_esclusi = pd.read_csv('esclusi.csv', sep=None, engine='python', encoding='latin1')
    except:
        df_quot = pd.DataFrame(columns=['Id', 'Nome', 'R', 'Qt.I', 'FVM'])
        df_esclusi = pd.DataFrame(columns=['Id'])

    try:
        df_stadi = pd.read_csv('stadi.csv', encoding='latin1')
    except:
        df_stadi = pd.DataFrame(columns=['Squadra', 'Stadio'])

    # Pulizia nomi colonne e spazi
    for d in [df_rosters, df_quot, df_esclusi, df_leghe]:
        if not d.empty:
            d.columns = d.columns.str.strip()
            cols_obj = d.select_dtypes(['object']).columns
            d[cols_obj] = d[cols_obj].apply(lambda x: x.str.strip() if x.dtype == "object" else x)

    # Forza ID come interi
    for d in [df_rosters, df_quot, df_esclusi]:
        if 'Id' in d.columns:
            d['Id'] = pd.to_numeric(d['Id'], errors='coerce').fillna(0).astype(int)

    # Merge dei dati
    df_m = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_m, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
    
    # Pulizia Valori Numerici
    df_base['Qt.I'] = pd.to_numeric(df_base['Qt.I'], errors='coerce').fillna(0)
    df_base['FVM'] = pd.to_numeric(df_base['FVM'], errors='coerce').fillna(0)
    
    # Calcoli rimborsi
    df_base['Meta_Qt'] = np.ceil(df_base['Qt.I'] / 2).astype(int)
    df_base['Meta_FVM'] = np.ceil(df_base['FVM'] / 2).astype(int)
    df_base['R_Star'] = (df_base['FVM'].astype(int) + df_base['Meta_Qt']).astype(int)
    df_base['R_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    # Identificazione Esclusi (Asteriscati)
    if 'Id' in df_esclusi.columns:
        esclusi_ids = set(df_esclusi['Id'].unique())
        df_base['Is_Escluso'] = df_base['Id'].isin(esclusi_ids)
    else:
        df_base['Is_Escluso'] = False
    
    # IMPORTANTE: I nomi qui devono essere quelli locali alla funzione
    esclusi_ids = set(df_esclusi['Id'].unique()) if 'Id' in df_esclusi.columns else set()
    return df_base, df_leghe, df_rosters, df_stadi, df_quot, esclusi_ids

# --- CHIAMATA ALLA FUNZIONE (Margine sinistro) ---
# Qui "afferri" i dati e puoi usare i nomi che vuoi per il resto dell'app
df_base, df_leghe_upd, df_rosters_upd, df_stadi, df_quot, esclusi_ids = load_all_data()
# --- 5. NAVIGAZIONE ---
menu = st.sidebar.radio("Scegli Pagina:", ["🏠 Dashboard", "1. Svincoli (*)", "2. Tagli", "3. Bilancio", "4. Rose", "5. Draft Estivo"])

# --- 🏠 DASHBOARD GOLDEN EDITION ---
if menu == "🏠 Dashboard":
    st.title("🏠 Riepilogo Globale")
    df_s = get_df_from_github('svincolati_gennaio.csv')
    df_t = get_df_from_github('tagli_volontari.csv')
    mov = pd.concat([df_s, df_t], ignore_index=True)
    
    leghe_per_dash = [l for l in ORDINE_LEGHE if l in df_base['Lega'].unique()]
    
    for lega_nome in leghe_per_dash:
        st.markdown(f"#### 🏆 {lega_nome}")
        df_l = df_base[df_base['Lega'] == lega_nome]
        if df_l.empty: continue
        
        uscite_nomi = mov.groupby('Squadra')['Giocatore'].apply(lambda x: ", ".join(x)) if not mov.empty else pd.Series()
        stats = df_l.groupby('Squadra_LFM').agg({'Nome': 'count', 'FVM': 'sum', 'Qt.I': 'sum'}).rename(columns={'Nome': 'NG', 'FVM': 'FVM_Tot', 'Qt.I': 'Quot_Tot'}).reset_index()

        cols = st.columns(3)
        for idx, (_, sq) in enumerate(stats.sort_values(by='Squadra_LFM').iterrows()):
            with cols[idx % 3]:
                cap = df_stadi[df_stadi['Squadra'].str.upper() == sq['Squadra_LFM'].upper()]['Stadio'].values
                cap_txt = f"{int(cap[0])}k" if len(cap)>0 and cap[0] > 0 else "N.D."
                cred_val = df_leghe_upd[df_leghe_upd['Squadra'] == sq['Squadra_LFM']]['Crediti'].sum()
                gioc_usciti = uscite_nomi.get(sq['Squadra_LFM'], "-")
                color_ng = "#00ff00" if 25 <= sq['NG'] <= 35 else "#ff4b4b"
                
                st.markdown(f"""
                    <div style="background-color: {MAPPATURA_COLORI.get(lega_nome, '#333')}; padding: 12px; border-radius: 10px; margin-bottom: 12px; color: white; border: 1px solid rgba(255,255,255,0.1); line-height: 1.2;">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 5px; margin-bottom: 8px;">
                            <b style="font-size: 15px;">{sq['Squadra_LFM']}</b>
                            <span style="font-size: 10px; background: rgba(0,0,0,0.2); padding: 2px 4px; border-radius: 4px;">🏟️ {cap_txt}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: baseline;">
                            <div style="font-size: 22px; font-weight: 900;">{format_num(cred_val)} <small style="font-size: 12px;">cr</small></div>
                            <div style="font-size: 14px; font-weight: bold; color: {color_ng};">{int(sq['NG'])} <small style="font-size: 10px; color: white;">gioc.</small></div>
                        </div>
                        <div style="margin-top: 8px; display: grid; grid-template-columns: 1fr 1fr; gap: 4px; font-size: 10px; text-align: center;">
                            <div style="background: rgba(255,255,255,0.1); padding: 4px; border-radius: 4px;">FVM: {format_num(sq['FVM_Tot'])}</div>
                            <div style="background: rgba(255,255,255,0.1); padding: 4px; border-radius: 4px;">Qt: {format_num(sq['Quot_Tot'])}</div>
                        </div>
                        <div style="font-size: 9px; margin-top: 8px; color: rgba(255,255,255,0.8); font-style: italic;">❌ {gioc_usciti}</div>
                    </div>
                """, unsafe_allow_html=True)

# --- 1. SVINCOLI ---
elif menu == "1. Svincoli (*)":
    st.title("✈️ Svincoli (*) Automatici")
    df_star = df_base[df_base['Is_Escluso']]
    
    if df_star.empty:
        st.success("Tutti i rimborsi asteriscati sono stati processati.")
    else:
        nomi_gioc = sorted([str(n) for n in df_star['Nome'].unique() if n != 'Sconosciuto'])
        scelta = st.selectbox("Seleziona Giocatore Asteriscato:", [""] + nomi_gioc)
        
        if scelta:
            targets = df_star[df_star['Nome'] == scelta]
            
            if not targets.empty:
                st.warning(f"Svincolo di {scelta}. Rimborso: {targets.iloc[0]['R_Star']} cr.")
                
                if not is_admin:
                    st.caption("🔒 Solo l'amministratore può eseguire questa operazione.")
                else:
                    # Tutto il codice sotto è dentro il BUTTON
                    if st.button("ESEGUI SVINCOLO GLOBALE"):
                        # 1. Aggiorna i crediti per ogni squadra che ha quel giocatore
                        for _, row in targets.iterrows():
                            df_leghe_upd.loc[df_leghe_upd['Squadra'] == row['Squadra_LFM'], 'Crediti'] += row['R_Star']
                        
                        # 2. Rimuovi il giocatore dal roster globale
                        df_rosters_upd = df_rosters_upd[df_rosters_upd['Id'] != targets.iloc[0]['Id']]
                        
                        # 3. Prepara il log
                        log = targets[['Nome', 'Squadra_LFM', 'Lega', 'R', 'FVM', 'Meta_Qt', 'R_Star']].copy()
                        log.columns = ['Giocatore', 'Squadra', 'Lega', 'Ruolo', 'Quota_FVM', 'Quota_Qt', 'Totale']
                        log['Tipo'] = "STAR (*)"
                        
                        # 4. Salva tutto su GitHub
                        save_to_github_direct('leghe.csv', df_leghe_upd, f"Svincolo {scelta}")
                        save_to_github_direct('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimozione {scelta}")
                        
                        old_l = get_df_from_github('svincolati_gennaio.csv')
                        save_to_github_direct('svincolati_gennaio.csv', pd.concat([old_l, log], ignore_index=True), "Log Star")
                        
                        # 5. Messaggio finale e reset
                        st.success(f"Operazione completata per {scelta}!")
                        st.cache_data.clear()
                        time.sleep(1)
                        st.rerun()
            else:
                st.error(f"Errore: il giocatore {scelta} non è presente nei dati correnti.")

# --- 2. TAGLI ---
elif menu == "2. Tagli":
    st.title("✂️ Tagli Volontari")
    sq_list = sorted([str(s) for s in df_base['Squadra_LFM'].unique() if s not in ['N/A', 'Sconosciuta']])
    sq = st.selectbox("Squadra:", sq_list, index=None, placeholder="Scegli squadra...")
    if sq:
        gioc_list = sorted([str(n) for n in df_base[df_base['Squadra_LFM'] == sq]['Nome'].tolist()])
        gioc = st.selectbox("Giocatore:", gioc_list, index=None, placeholder="Scegli giocatore...")
        if gioc:
            info = df_base[(df_base['Squadra_LFM'] == sq) & (df_base['Nome'] == gioc)].iloc[0]
            if not is_admin:
                st.caption("🔒 Solo l'amministratore può eseguire questa operazione.")
            elif st.button("ESEGUI TAGLIO"):
                df_leghe_upd.loc[df_leghe_upd['Squadra'] == sq, 'Crediti'] += info['R_Taglio']
                df_rosters_upd = df_rosters_upd[~((df_rosters_upd['Squadra_LFM'] == sq) & (df_rosters_upd['Id'] == info['Id']))]
                log_t = pd.DataFrame([{'Giocatore': gioc, 'Squadra': sq, 'Lega': info['Lega'], 'Ruolo': info['R'], 'Quota_FVM': info['Meta_FVM'], 'Quota_Qt': info['Meta_Qt'], 'Totale': info['R_Taglio'], 'Tipo': 'TAGLIO'}])
                save_to_github_direct('leghe.csv', df_leghe_upd, f"Taglio {gioc}")
                save_to_github_direct('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimozione {gioc}")
                old_t = get_df_from_github('tagli_volontari.csv')
                save_to_github_direct('tagli_volontari.csv', pd.concat([old_t, log_t], ignore_index=True), "Log Taglio")
                st.cache_data.clear(); st.rerun()

# --- 3. BILANCIO (PROTEZIONE TYPEERROR) ---
elif menu == "3. Bilancio":
    st.title("💰 Bilancio Finanziario")
    # Usiamo ORDINE_LEGHE come riferimento sicuro
    leghe_l = [l for l in ORDINE_LEGHE if l in df_base['Lega'].unique()]
    lega_s = st.selectbox("Filtra Lega:", leghe_l)
    
    df_s = get_df_from_github('svincolati_gennaio.csv')
    df_t = get_df_from_github('tagli_volontari.csv')
    mov = pd.concat([df_s, df_t], ignore_index=True)
    bonus = mov.groupby('Squadra')['Totale'].sum() if not mov.empty else pd.Series()
    
    bil = df_leghe_upd[df_leghe_upd['Lega'] == lega_s].copy()
    bil['Bonus'] = bil['Squadra'].map(bonus).fillna(0).astype(int)
    bil['Iniziale'] = bil['Crediti'] - bil['Bonus']
    st.table(bil[['Squadra', 'Iniziale', 'Bonus', 'Crediti']].rename(columns={'Crediti': 'Attuali'}))

# --- 4. ROSE ---
elif menu == "4. Rose":
    st.title("📋 Rose e Registro")
    
    # Selezione della Lega
    leghe_l = [l for l in ORDINE_LEGHE if l in df_base['Lega'].unique()]
    lega_sel = st.selectbox("Lega:", leghe_l)
    
    # Visualizzazione delle Rose
    df_v = df_base[df_base['Lega'] == lega_sel].sort_values('Squadra_LFM')
    for s in df_v['Squadra_LFM'].unique():
        with st.expander(f"Rosa {s}"):
            d_sq = df_v[df_v['Squadra_LFM'] == s].copy()
            d_sq['Ord'] = d_sq['R'].map(ORDINE_RUOLI)
            
            # Pulizia decimali .0 per Qt.I e FVM
            d_sq['Qt.I'] = d_sq['Qt.I'].apply(format_num)
            d_sq['FVM'] = d_sq['FVM'].apply(format_num)
            
            st.table(d_sq.sort_values('Ord')[['R', 'Nome', 'Qt.I', 'FVM']])
    
    # --- REGISTRO USCITE (Tagli e Svincoli) ---
    st.divider()
    st.subheader(f"❌ Registro Uscite - {lega_sel}")
    
    # Carichiamo i due file dei movimenti
    df_s = get_df_from_github('svincolati_gennaio.csv')
    df_t = get_df_from_github('tagli_volontari.csv')
    
    # Uniamo i movimenti
    res = pd.concat([df_s, df_t], ignore_index=True)
    
    if not res.empty:
        # Pulizia nomi colonne e dati
        res.columns = res.columns.str.strip()
        
        # Filtriamo solo per la lega selezionata
        res_view = res[res['Lega'] == lega_sel].copy()
        
        if not res_view.empty:
            # Definiamo le colonne da mostrare
            cols_to_show = ['Squadra', 'Ruolo', 'Giocatore', 'Tipo', 'Totale']
            # Verifichiamo quali esistono effettivamente nel file
            cols_final = [c for c in cols_to_show if c in res_view.columns]
            
            # Pulizia decimale .0 sulla colonna Totale (il rimborso)
            if 'Totale' in res_view.columns:
                res_view['Totale'] = res_view['Totale'].apply(format_num)
            
            # Visualizzazione tabella registro
            st.dataframe(
                res_view[cols_final].sort_values(['Squadra', 'Giocatore']),
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info(f"Nessuna uscita registrata per la {lega_sel}.")
    else:
        st.info("Registro movimenti ancora vuoto.")

# --- 5. DRAFT ESTIVO ---
elif menu == "5. Draft Estivo":
    st.title("🔄 Draft Estivo — Sostituzioni Temporanee")
    st.caption(
        "Copre le rose dopo le uscite dalla Serie A, prima dell'asta a mercato chiuso. "
        "L'assegnazione è temporanea (Prezzo = 0 nel file rose) e va rimossa quando il mercato chiude. "
        "L'ordine di chiamata per ogni ruolo segue la quotazione del giocatore perso: chi ha perso il "
        "giocatore con quotazione più alta in quel ruolo chiama per primo."
    )

    leghe_l = [l for l in ORDINE_LEGHE if l in df_base['Lega'].unique()]
    lega_sel = st.selectbox("Lega:", leghe_l, key="draft_lega")

    df_lega = df_base[df_base['Lega'] == lega_sel]
    persi_globale = df_lega[df_lega['Is_Escluso']].copy()

    df_draft_log = get_df_from_github('draft_estivo.csv')
    log_lega = df_draft_log[df_draft_log['Lega'] == lega_sel] if (not df_draft_log.empty and 'Lega' in df_draft_log.columns) else pd.DataFrame()

    persi_visibili = persi_globale if is_admin else persi_globale[persi_globale['Squadra_LFM'] == st.session_state.squadra]

    if persi_visibili.empty:
        msg = f"✅ Nessun giocatore perso da sostituire in {lega_sel}." if is_admin else "✅ Non hai giocatori persi da sostituire in questa Lega."
        st.success(msg)
    else:
        persi_label = persi_visibili.apply(
            lambda r: f"{r['Squadra_LFM']} — {r['Nome']} ({r['R']}, Qt.I {format_num(r['Qt.I'])})", axis=1
        )
        scelta_idx = st.selectbox(
            "Giocatore perso da sostituire:",
            persi_visibili.index, format_func=lambda i: persi_label[i], key="draft_perso"
        )
        riga_persa = persi_visibili.loc[scelta_idx]
        ruolo = riga_persa['R']

        # --- Coda di chiamata per questo ruolo in questa Lega ---
        # "In attesa": tutti i persi di questo ruolo (di qualsiasi squadra) non ancora sostituiti
        in_attesa = persi_globale[persi_globale['R'] == ruolo][['Squadra_LFM', 'Id', 'Nome', 'Qt.I', 'FVM']].copy()
        in_attesa = in_attesa.rename(columns={'Qt.I': 'Qt_Eff', 'FVM': 'FVM_Eff'})
        in_attesa['Fatto'] = False

        # "Già chiamati": dal log, stesso ruolo
        if not log_lega.empty and 'Ruolo' in log_lega.columns:
            gia_chiamati = log_lega[log_lega['Ruolo'] == ruolo][['Squadra', 'Id_Perso', 'Nome_Perso', 'Qt_Perso', 'FVM_Perso']].copy()
            gia_chiamati = gia_chiamati.rename(columns={
                'Squadra': 'Squadra_LFM', 'Id_Perso': 'Id', 'Nome_Perso': 'Nome',
                'Qt_Perso': 'Qt_Eff', 'FVM_Perso': 'FVM_Eff'
            })
            gia_chiamati['Fatto'] = True
        else:
            gia_chiamati = pd.DataFrame(columns=['Squadra_LFM', 'Id', 'Nome', 'Qt_Eff', 'FVM_Eff', 'Fatto'])

        coda = pd.concat([in_attesa, gia_chiamati], ignore_index=True)
        coda['Qt_Eff'] = pd.to_numeric(coda['Qt_Eff'], errors='coerce').fillna(0)
        coda['FVM_Eff'] = pd.to_numeric(coda['FVM_Eff'], errors='coerce').fillna(0)
        coda = coda.sort_values(['Qt_Eff', 'FVM_Eff'], ascending=[False, False]).reset_index(drop=True)

        st.markdown(f"**📜 Coda di chiamata — Ruolo {ruolo} — {lega_sel}**")
        coda_display = coda.copy()
        coda_display['Stato'] = coda_display['Fatto'].map({True: '✅ Chiamato', False: '⏳ In attesa'})
        coda_display.index = coda_display.index + 1
        st.dataframe(
            coda_display[['Squadra_LFM', 'Nome', 'Qt_Eff', 'FVM_Eff', 'Stato']].rename(columns={'Qt_Eff': 'Qt.I', 'FVM_Eff': 'FVM'}),
            use_container_width=True
        )

        # Chi precede la riga scelta ed è ancora "in attesa"?
        posizione = coda[(coda['Squadra_LFM'] == riga_persa['Squadra_LFM']) & (coda['Id'] == riga_persa['Id'])].index
        pos_idx = posizione[0] if len(posizione) else None
        precedenti_bloccanti = coda.iloc[:pos_idx][~coda.iloc[:pos_idx]['Fatto']] if pos_idx is not None else pd.DataFrame()

        if not precedenti_bloccanti.empty:
            nomi_bloccanti = ", ".join(f"{r['Squadra_LFM']} ({r['Nome']})" for _, r in precedenti_bloccanti.iterrows())
            st.error(f"🚫 Non è ancora il turno di {riga_persa['Squadra_LFM']} per il ruolo {ruolo}. Devono chiamare prima: {nomi_bloccanti}")
        else:
            # Pool liberi: non in nessuna rosa di QUESTA Lega, non esclusi, stesso ruolo,
            # quotazione >= quella del giocatore perso (nessuno deve uscirne peggio)
            ids_in_lega = set(df_lega['Id'])
            liberi = df_quot[
                (~df_quot['Id'].isin(ids_in_lega)) &
                (~df_quot['Id'].isin(esclusi_ids)) &
                (df_quot['R'] == ruolo) &
                (df_quot['Qt.I'] >= riga_persa['Qt.I'])
            ].sort_values(['Qt.I', 'FVM'], ascending=[False, False])

            if liberi.empty:
                st.warning("⚠️ Nessun giocatore libero idoneo (stesso ruolo, quotazione ≥ persa) trovato in questa Lega.")
            else:
                liberi_label = liberi.apply(
                    lambda r: f"{r['Nome']} ({r['R']}, Qt.I {format_num(r['Qt.I'])}, FVM {format_num(r['FVM'])})", axis=1
                )
                nuovo_idx = st.selectbox(
                    "Sostituto disponibile:",
                    liberi.index, format_func=lambda i: liberi_label[i], key="draft_nuovo"
                )
                nuovo = liberi.loc[nuovo_idx]

                st.info(
                    f"**{riga_persa['Squadra_LFM']}** sostituisce **{riga_persa['Nome']}** "
                    f"(perso, Qt.I {format_num(riga_persa['Qt.I'])}) con **{nuovo['Nome']}** "
                    f"(Qt.I {format_num(nuovo['Qt.I'])})"
                )

                if st.button("✅ CONFERMA DRAFT"):
                    # Rimuove il giocatore perso dalla rosa
                    df_rosters_new = df_rosters_upd[
                        ~((df_rosters_upd['Squadra_LFM'] == riga_persa['Squadra_LFM']) & (df_rosters_upd['Id'] == riga_persa['Id']))
                    ]
                    # Aggiunge il sostituto: Prezzo=0 segnala "temporaneo da draft", nessun
                    # giocatore comprato all'asta può avere questo valore
                    nuova_riga = pd.DataFrame([{
                        'Squadra_LFM': riga_persa['Squadra_LFM'], 'Id': nuovo['Id'], 'Prezzo': 0
                    }])
                    df_rosters_new = pd.concat([df_rosters_new, nuova_riga], ignore_index=True)
                    save_to_github_direct(
                        'fantamanager-2021-rosters.csv', df_rosters_new,
                        f"Draft: {nuovo['Nome']} al posto di {riga_persa['Nome']} ({riga_persa['Squadra_LFM']})"
                    )

                    # Log dedicato: tracciabilità completa, base per la coda di chiamata
                    # e per smontare i draft a mercato chiuso
                    log_draft = pd.DataFrame([{
                        'Squadra': riga_persa['Squadra_LFM'], 'Lega': lega_sel, 'Ruolo': ruolo,
                        'Id_Perso': riga_persa['Id'], 'Nome_Perso': riga_persa['Nome'],
                        'Qt_Perso': riga_persa['Qt.I'], 'FVM_Perso': riga_persa['FVM'],
                        'Id_Preso': nuovo['Id'], 'Nome_Preso': nuovo['Nome'], 'Qt_Preso': nuovo['Qt.I'],
                        'Orario': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                    }])
                    old_draft = get_df_from_github('draft_estivo.csv')
                    save_to_github_direct(
                        'draft_estivo.csv', pd.concat([old_draft, log_draft], ignore_index=True),
                        f"Log draft {nuovo['Nome']}"
                    )

                    st.success(f"✅ {nuovo['Nome']} assegnato a {riga_persa['Squadra_LFM']} (temporaneo, Prezzo 0).")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()

    st.divider()
    st.subheader("📋 Registro Draft Estivo")
    if not df_draft_log.empty:
        st.dataframe(
            df_draft_log.sort_values('Orario', ascending=False),
            use_container_width=True, hide_index=True
        )
    else:
        st.info("Nessun draft ancora effettuato.")

    # --- CHIUSURA DRAFT: solo admin, solo dalla data di chiusura mercato in poi,
    # nascosto prima di allora per evitare click accidentali durante il draft ---
    if is_admin and datetime.now() >= CHIUSURA_MERCATO:
        st.divider()
        st.subheader("🔒 Chiudi Draft Estivo")
        draftati = df_rosters_upd[df_rosters_upd['Prezzo'] == 0]
        if draftati.empty:
            st.info("Nessuna assegnazione temporanea da rimuovere.")
        else:
            st.warning(
                f"⚠️ Questo rimuoverà **{len(draftati)}** assegnazioni temporanee da draft "
                f"(Prezzo = 0) da tutte le rose, in preparazione dell'asta. Operazione irreversibile "
                f"(ma tracciata nel registro qui sopra)."
            )
            st.dataframe(draftati[['Squadra_LFM', 'Id']], use_container_width=True, hide_index=True)
            conferma = st.checkbox("Confermo di voler chiudere il draft estivo e rimuovere queste assegnazioni.")
            if conferma and st.button("🗑️ CHIUDI DRAFT ESTIVO DEFINITIVAMENTE"):
                df_rosters_finale = df_rosters_upd[df_rosters_upd['Prezzo'] != 0]
                save_to_github_direct(
                    'fantamanager-2021-rosters.csv', df_rosters_finale,
                    f"Chiusura draft estivo: rimosse {len(draftati)} assegnazioni temporanee"
                )
                st.success(f"✅ Draft estivo chiuso. Rimosse {len(draftati)} assegnazioni temporanee.")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
    elif is_admin:
        st.caption(f"🔒 Lo strumento 'Chiudi Draft Estivo' sarà disponibile dal {CHIUSURA_MERCATO.strftime('%d/%m/%Y')}.")
