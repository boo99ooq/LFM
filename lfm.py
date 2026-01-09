@st.cache_data
def load_and_merge():
    # Usiamo l'argomento 'encoding' per gestire i caratteri speciali
    # 'latin1' o 'cp1252' solitamente risolvono il problema dei CSV di Excel
    try:
        df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding='latin1')
    except:
        df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding='utf-8')
        
    df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
    
    try:
        df_quot = pd.read_csv('quot.csv', encoding='latin1')
    except:
        df_quot = pd.read_csv('quot.csv', encoding='utf-8')

    # Unisco
    df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
    df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
    return pd.merge(df_rose, df_quot, on='Id', how='inner')
