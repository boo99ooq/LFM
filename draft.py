import pandas as pd

def genera_draft_agosto(file_roster, file_leghe, file_quot_nuovo, file_quot_vecchio):
    # 1. Caricamento e pulizia dati
    roster = pd.read_csv(file_roster)
    roster = roster[pd.to_numeric(roster['Id'], errors='coerce').notna()].copy()
    roster['Id'] = roster['Id'].astype(int)

    leghe = pd.read_csv(file_leghe)
    
    # Uniamo rose e leghe per avere Campionato e Crediti
    roster_full = pd.merge(roster, leghe[['Squadra', 'Lega', 'Crediti']], 
                           left_on='Squadra_LFM', right_on='Squadra', how='left')

    q_nuova = pd.read_csv(file_quot_nuovo)
    q_vecchia = pd.read_csv(file_quot_vecchio)

    # 2. Logica di Draft per ogni Campionato
    lista_campionati = ['Serie A', 'Premier League', 'Liga BBVA', 'Bundesliga']
    risultati_finali = []

    for camp in lista_campionati:
        # Giocatori della lega attuale
        df_camp = roster_full[roster_full['Lega'] == camp]
        ids_occupati = set(df_camp['Id'])
        
        # Identifica chi è sparito dal nuovo listone
        persi = df_camp[~df_camp['Id'].isin(q_nuova['Id'])]
        
        # Recupera Ruolo e Quotazione dal vecchio listone per la priorità
        asteriscati = pd.merge(persi, q_vecchia[['Id', 'Nome', 'R', 'Qt.I']], on='Id', how='left')
        
        # Ordine di scelta: Quotazione (Qt.I) decrescente
        asteriscati = asteriscati.sort_values(by='Qt.I', ascending=False)

        # Identifica svincolati per questa specifica lega
        svincolati = q_nuova[~q_nuova['Id'].isin(ids_occupati)]

        for _, riga in asteriscati.iterrows():
            # Filtro: stesso ruolo e costo <= al giocatore perso
            sostituti = svincolati[(svincolati['R'] == riga['R']) & (svincolati['Qt.I'] <= riga['Qt.I'])]
            consigli = sostituti.sort_values(by='Qt.I', ascending=False).head(3)['Nome'].tolist()

            risultati_finali.append({
                "Campionato": camp,
                "Squadra": riga['Squadra_LFM'],
                "Crediti": riga['Crediti'],
                "Perso (Asterisco)": riga['Nome'],
                "Ruolo": riga['R'],
                "Quota Perso": riga['Qt.I'],
                "Opzioni Mercato": ", ".join(consigli)
            })

    return pd.DataFrame(risultati_finali)

# ESECUZIONE (Assicurati che i nomi dei file siano corretti nella tua cartella)
# df_report = genera_draft_agosto('fantamanager-2021-rosters.csv', 'leghe.csv', 'quot.csv', 'quot_luglio.csv')
# df_report.to_excel("Draft_Agosto_Risultati.xlsx", index=False)
# print("File Excel generato con successo!")
