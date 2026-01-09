if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Crediti e Operazioni")
        
        leghe_nel_file = sorted(df_base['Lega'].unique().tolist())
        cols_container = st.columns(2)
        
        for i, nome_lega in enumerate(leghe_nel_file):
            with cols_container[i % 2]:
                st.markdown(f"## 🏆 {nome_lega}")
                df_l = df_base[df_base['Lega'] == nome_lega]
                
                # --- PREPARAZIONE DATI SQUADRA ---
                # Rimborsi * (Pieni)
                res_star = df_l[df_l['Rimborsato_Star']].groupby('Squadra_LFM').agg({
                    'Rimborso_Star': 'sum',
                    'Nome': lambda x: ", ".join(x)
                }).reset_index()
                res_star.columns = ['Squadra_LFM', 'Valore_Star', 'Nomi_Star']
                
                # Tagli Volontari (50%)
                res_tagli = df_l[df_l['Rimborsato_Taglio']].groupby('Squadra_LFM').agg({
                    'Rimborso_Taglio': 'sum',
                    'Nome': lambda x: ", ".join(x)
                }).reset_index()
                res_tagli.columns = ['Squadra_LFM', 'Valore_Taglio', 'Nomi_Taglio']
                
                df_crediti = df_l[['Squadra_LFM', 'Crediti']].drop_duplicates()
                
                # Merge unico
                tabella = pd.merge(df_crediti, res_star, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_tagli, on='Squadra_LFM', how='left').fillna(0)
                
                # Sostituiamo gli 0 nelle stringhe dei nomi con stringa vuota
                tabella['Nomi_Star'] = tabella['Nomi_Star'].replace(0, "")
                tabella['Nomi_Taglio'] = tabella['Nomi_Taglio'].replace(0, "")
                
                tabella['Totale'] = tabella['Crediti'] + tabella['Valore_Star'] + tabella['Valore_Taglio']
                tabella = tabella.sort_values(by='Squadra_LFM')

                bg_color = MAPPATURA_COLORI.get(nome_lega, "#f5f5f5")

                for _, sq in tabella.iterrows():
                    # Costruiamo il dettaglio in modo pulito
                    dettaglio_html = ""
                    if sq['Nomi_Star']:
                        dettaglio_html += f"<div style='font-size: 13px; color: #d32f2f;'><b>* Svincolati:</b> {sq['Nomi_Star']} (+{int(sq['Valore_Star'])} cr)</div>"
                    if sq['Nomi_Taglio']:
                        dettaglio_html += f"<div style='font-size: 13px; color: #7b1fa2;'><b>✂️ Tagli Vol.:</b> {sq['Nomi_Taglio']} (+{int(sq['Valore_Taglio'])} cr)</div>"
                    if not dettaglio_html:
                        dettaglio_html = "<div style='font-size: 13px; color: #777; font-style: italic;'>Nessuna operazione attiva</div>"

                    st.markdown(f"""
                        <div style="background-color: {bg_color}; padding: 15px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #ddd; color: #333; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 22px; font-weight: bold; color: #000;">{sq['Squadra_LFM']}</span>
                                <span style="font-size: 22px; font-weight: bold; color: #1e88e5;">{int(sq['Totale'])} <small style="font-size: 14px;">cr</small></span>
                            </div>
                            <hr style="margin: 8px 0; border: 0; border-top: 1px solid #bbb;">
                            <div style="display: flex; justify-content: space-between; font-size: 15px; margin-bottom: 8px;">
                                <span><b>Residuo:</b> {int(sq['Crediti'])}</span>
                                <span><b>Extra:</b> {int(sq['Valore_Star'] + sq['Valore_Taglio'])}</span>
                            </div>
                            <div style="background-color: rgba(255,255,255,0.4); padding: 8px; border-radius: 6px; border: 1px dashed #999;">
                                {dettaglio_html}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
