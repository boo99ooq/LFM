import streamlit as st
import pandas as pd
import numpy as np
from github import Github
import io
import time

# --- 1. CONFIGURAZIONE E COSTANTI ---
st.set_page_config(page_title="LFM Mercato - Golden Edition", layout="wide", page_icon="⚖️")

ORDINE_LEGHE = ["Serie A", "Bundesliga", "Premier League", "Liga BBVA"]
MAPPATURA_COLORI = {"Serie A": "#00529b", "Bundesliga": "#d3010c", "Premier League": "#3d195b", "Liga BBVA": "#ee8707"}
ORDINE_RUOLI = {'P': 0, 'D': 1, 'C': 2, 'A': 3}

def format_num(num):
    """Rimuove il .0 per pulizia visiva"""
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
except:
    st.error("Errore Secrets! Verifica GITHUB_TOKEN e REPO_NAME.")

# --- 3. FUNZIONI API GITHUB ---
def get_df_from_github(file_path):
    try:
        content = repo.get_contents(file_path)
        df = pd.read_csv(io.StringIO(content.decoded_content.decode('utf-8')))
        # Fix per KeyError: se esiste 'Rimborso' ma non 'Totale', rinomina
        if 'Rimborso' in df.columns and 'Totale' not in df.columns:
            df = df.rename(columns={'Rimborso': 'Totale'})
        return df
    except:
        return pd.DataFrame()

def save_to_github_direct(file_path, df, message):
    csv_content = df.to_csv(index=False)
    try:
        contents = repo.get_contents(file_path)
        repo.update_file(contents.path, message, csv_content, contents.sha)
    except:
        repo.create_file(file_path, message, csv_content)

# --- 4. CARICAMENTO E PULIZIA PROFONDA DATI ---
@st.cache_data(ttl=2)
def load_all_data():
    df_rosters = get_df_from_github('fantamanager-2021-rosters.csv')
    df_leghe = get_df_from_github('leghe.csv')
    df_quot = pd.read_csv('quot.csv', encoding='latin1')
    df_esclusi = pd.read_csv('esclusi.csv', sep='\t', encoding='latin1')
    
    try:
        df_stadi = pd.read_csv('stadi.csv', encoding='latin1')
        df_stadi['Squadra'] = df_stadi['Squadra'].astype(str).str.strip()
    except:
        df_stadi = pd.DataFrame(columns=['Squadra', 'Stadio'])

    # PULIZIA TOTALE: Fondamentale per evitare TypeError nei menu sorted()
    for df in [df_rosters, df_quot, df_esclusi, df_leghe]:
        if 'Id' in df.columns:
            df['Id'] = pd.to_numeric(df['Id'], errors='coerce').fillna(0).astype(int)
        if 'Lega' in df.columns:
            df['Lega'] = df['Lega'].astype(str).replace(['nan', 'None', '', 'NaN'], 'N/A').str.strip()
        if 'Squadra_LFM' in df.columns:
            df['Squadra_LFM'] = df['Squadra_LFM'].astype(str).replace(['nan', 'None', ''], 'Sconosciuta').str.strip()
        if 'Squadra' in df.columns:
            df['Squadra'] = df['Squadra'].astype(str).replace(['nan', 'None', ''], 'Sconosciuta').str.strip()

    # Merge Rose + Leghe + Quotazioni
    df_m = pd.merge(df_rosters, df_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base = pd.merge(df_m, df_quot[['Id', 'Nome', 'R', 'Qt.I', 'FVM']], on='Id', how='left')
    
    # Pulizia Valori Numerici
    df_base['Qt.I'] = pd.to_numeric(df_base['Qt.I'], errors='coerce').fillna(0)
    df_base['FVM'] = pd.to_numeric(df_base['FVM'], errors='coerce').fillna(0)
    df_base['Crediti'] = pd.to_numeric(df_base['Crediti'], errors='coerce').fillna(0)
    
    # CALCOLO COMPONENTI RIMBORSO
    df_base['Meta_Qt'] = np.ceil(df_base['Qt.I'] / 2).astype(int)
    df_base['R_Star'] = (df_base['FVM'].astype(int) + df_base['Meta_Qt']).astype(int)
    df_base['Meta_FVM'] = np.ceil(df_base['FVM'] / 2).astype(int)
    df_base['R_Taglio'] = np.ceil((df_base['FVM'] + df_base['Qt.I']) / 2).astype(int)
    
    esclusi_ids = set(df_esclusi['Id'])
    df_base['Is_Escluso'] = df_base['Id'].isin(esclusi_ids)
    
    return df_base, df_leghe, df_rosters, df_stadi

df_base, df_leghe_upd, df_rosters_upd, df_stadi = load_all_data()

# --- 5. NAVIGAZIONE ---
menu = st.sidebar.radio("Scegli Pagina:", ["🏠 Dashboard", "1. Svincoli (*)", "2. Tagli", "3. Bilancio", "4. Rose"])

# --- 🏠 PAGINA: DASHBOARD ---
if menu == "🏠 Dashboard":
    st.title("🏠 Dashboard Riepilogo Globale")
    
    df_s = get_df_from_github('svincolati_gennaio.csv')
    df_t = get_df_from_github('tagli_volontari.csv')
    mov = pd.concat([df_s, df_t], ignore_index=True)
    
    # Leghe ordinate come da costante
    leghe_effettive = [l for l in ORDINE_LEGHE if l in df_base['Lega'].unique()]
    
    for lega_nome in leghe_effettive:
        st.markdown(f"#### 🏆 {lega_nome}")
        df_l = df_base[df_base['Lega'] == lega_nome]
        if df_l.empty: continue
        
        # Statistiche Squadra
        uscite_nomi = mov.groupby('Squadra')['Giocatore'].apply(lambda x: ", ".join(x)) if not mov.empty else pd.Series()
        stats = df_l.groupby('Squadra_LFM').agg({'Nome': 'count', 'FVM': 'sum', 'Qt.I': 'sum'}).rename(columns={'Nome': 'NG', 'FVM': 'FVM_Tot', 'Qt.I': 'Quot_Tot'}).reset_index()

        cols = st.columns(3)
        for idx, (_, sq) in enumerate(stats.sort_values(by='Squadra_LFM').iterrows()):
            with cols[idx % 3]:
                # Recupero Stadio
                cap = df_stadi[df_stadi['Squadra'].str.upper() == sq['Squadra_LFM'].upper()]['Stadio'].values
                cap_txt = f"{int(cap[0])}k" if len(cap)>0 and cap[0] > 0 else "N.D."
                
                # Crediti Attuali
                try:
                    cred_val = df_leghe_upd[df_leghe_upd['Squadra'] == sq['Squadra_LFM']]['Crediti'].values[0]
                except:
                    cred_val = 0
                
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

# --- 1. SVINCOLI (*) ---
elif menu == "1. Svincoli (*)":
    st.title("✈️ Svincoli (*) Automatici")
    df_star = df_base[df_base['Is_Escluso']].copy()
    if df_star.empty:
        st.success("Tutti i rimborsi (*) sono stati completati.")
    else:
        scelta = st.selectbox("Seleziona Giocatore:", [""] + sorted([str(n) for n in df_star['Nome'].unique().tolist()]))
        if scelta:
            targets = df_star[df_star['Nome'] == scelta]
            info = targets.iloc[0]
            st.warning(f"Svincolo di {scelta} ({info['R']}). Rimborso: FVM {info['FVM']} + 50% Qt ({info['Meta_Qt']}) = {info['R_Star']} cr.")
            
            if st.button("CONFERMA SVINCOLO GLOBALE"):
                for _, row in targets.iterrows():
                    df_leghe_upd.loc[df_leghe_upd['Squadra'] == row['Squadra_LFM'], 'Crediti'] += row['R_Star']
                
                id_target = info['Id']
                df_rosters_upd = df_rosters_upd[df_rosters_upd['Id'] != id_target]
                
                log = targets[['Nome', 'Squadra_LFM', 'Lega', 'R', 'FVM', 'Meta_Qt', 'R_Star']].copy()
                log.columns = ['Giocatore', 'Squadra', 'Lega', 'Ruolo', 'Quota_FVM', 'Quota_Qt', 'Totale']
                log['Tipo'] = "STAR (*)"
                
                save_to_github_direct('leghe.csv', df_leghe_upd, f"Svincolo {scelta}")
                save_to_github_direct('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimosso {scelta}")
                
                old_log = get_df_from_github('svincolati_gennaio.csv')
                save_to_github_direct('svincolati_gennaio.csv', pd.concat([old_log, log], ignore_index=True), f"Log {scelta}")
                
                st.cache_data.clear(); st.rerun()

# --- 2. TAGLI ---
elif menu == "2. Tagli":
    st.title("✂️ Tagli Volontari")
    squadre_list = sorted([str(s) for s in df_base['Squadra_LFM'].unique() if s not in ['N/A', 'Sconosciuta']])
    sq = st.selectbox("Squadra:", squadre_list, index=None, placeholder="Scegli squadra...")
    
    if sq:
        giocatori_filtro = sorted([str(n) for n in df_base[df_base['Squadra_LFM'] == sq]['Nome'].tolist()])
        gioc = st.selectbox("Giocatore:", giocatori_filtro, index=None, placeholder="Scegli giocatore...")
        
        if gioc:
            info = df_base[(df_base['Squadra_LFM'] == sq) & (df_base['Nome'] == gioc)].iloc[0]
            st.info(f"Rimborso previsto: {info['R_Taglio']} crediti.")
            
            if st.button("ESEGUI TAGLIO"):
                df_leghe_upd.loc[df_leghe_upd['Squadra'] == sq, 'Crediti'] += info['R_Taglio']
                df_rosters_upd = df_rosters_upd[~((df_rosters_upd['Squadra_LFM'] == sq) & (df_rosters_upd['Id'] == info['Id']))]
                
                log_t = pd.DataFrame([{
                    'Giocatore': gioc, 'Squadra': sq, 'Lega': info['Lega'], 'Ruolo': info['R'],
                    'Quota_FVM': info['Meta_FVM'], 'Quota_Qt': info['Meta_Qt'], 
                    'Totale': info['R_Taglio'], 'Tipo': 'TAGLIO'
                }])
                
                save_to_github_direct('leghe.csv', df_leghe_upd, f"Taglio {gioc}")
                save_to_github_direct('fantamanager-2021-rosters.csv', df_rosters_upd, f"Rimosso {gioc}")
                
                old_log_t = get_df_from_github('tagli_volontari.csv')
                save_to_github_direct('tagli_volontari.csv', pd.concat([old_log_t, log_t], ignore_index=True), f"Log {gioc}")
                
                st.cache_data.clear(); st.rerun()

# --- 3. BILANCIO ---
elif menu == "3. Bilancio":
    st.title("💰 Bilancio")
    # Filtro leghe sicuro
    leghe_l = [l for l in ORDINE_LEGHE if l in df_base['Lega'].unique()]
    lega_sel = st.selectbox("Lega:", leghe_l)
    
    df_s = get_df_from_github('svincolati_gennaio.csv')
    df_t = get_df_from_github('tagli_volontari.csv')
    mov = pd.concat([df_s, df_t], ignore_index=True)
    bonus = mov.groupby('Squadra')['Totale'].sum() if not mov.empty and 'Totale' in mov.columns else pd.Series()

    bil = df_leghe_upd[df_leghe_upd['Lega'] == lega_sel].copy()
    bil['Bonus'] = bil['Squadra'].map(bonus).fillna(0).astype(int)
    bil['Iniziale'] = bil['Crediti'] - bil['Bonus']
    
    st.table(bil[['Squadra', 'Iniziale', 'Bonus', 'Crediti']].rename(columns={'Crediti': 'Attuali'}))

# --- 4. ROSE ---
elif menu == "4. Rose":
    st.title("📋 Rose e Registro")
    leghe_l = [l for l in ORDINE_LEGHE if l in df_base['Lega'].unique()]
    lega_sel = st.selectbox("Lega:", leghe_l)
    
    df_v = df_base[df_base['Lega'] == lega_sel].sort_values('Squadra_LFM')
for s in df_v['Squadra_LFM'].unique():
       with st.expander(f"Rosa {s}"):
            d_sq = df_v[df_v['Squadra_LFM'] == s].copy()
            d_sq['Ord'] = d_sq['R'].map(ORDINE_RUOLI)
            
            # PULIZIA DEI DECIMALI PRIMA DI MOSTRARE LA TABELLA
            d_sq['Qt.I'] = d_sq['Qt.I'].apply(format_num)
            d_sq['FVM'] = d_sq['FVM'].apply(format_num)
            
            st.table(d_sq.sort_values('Ord')[['R', 'Nome', 'Qt.I', 'FVM']])
            st.divider()
            st.subheader("❌ Registro Uscite")
            df_s = get_df_from_github('svincolati_gennaio.csv')
            df_t = get_df_from_github('tagli_volontari.csv')
            res = pd.concat([df_s, df_t], ignore_index=True)
            
            if not res.empty:
                available_cols = [c for c in ['Squadra', 'Ruolo', 'Giocatore', 'Tipo', 'Quota_FVM', 'Quota_Qt', 'Totale'] if c in res.columns]
                res_view = res[res['Lega'] == lega_sel].sort_values(['Squadra', 'Giocatore'])
                st.dataframe(res_view[available_cols], use_container_width=True, hide_index=True)
            else:
                st.info("Nessun registro disponibile.")
