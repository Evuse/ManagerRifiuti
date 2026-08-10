# Manager Rifiuti

Applicazione desktop locale per leggere un calendario semestrale dei rifiuti,
controllare le raccolte riconosciute e importarle in Home Assistant. Le immagini
non lasciano il computer: OpenCV e RapidOCR lavorano offline.

## Da dove iniziare

- Windows 11: segui [`docs/GUIDA_WINDOWS_11.md`](docs/GUIDA_WINDOWS_11.md).
- macOS Intel: la guida è in [`docs/GUIDA_MAC_INTEL.md`](docs/GUIDA_MAC_INTEL.md).

## Funzioni dell'app

- trascinamento di una o due fotografie;
- correzione prospettica e riconoscimento locale dei simboli;
- revisione obbligatoria con nomi completi dei rifiuti;
- selezione delle tipologie da importare e modifica delle singole righe;
- tema chiaro o scuro, colori e dimensione del testo personalizzabili;
- salvataggio opzionale dell'indirizzo e dell'ID di Home Assistant;
- caricamento dei backup e azzeramento guidato del calendario remoto;
- backup JSON automatico dopo ogni revisione;
- invio diretto a Home Assistant mediante ID di importazione protetto.

## Avvio per sviluppatori

Su Windows è consigliato Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[ocr,test]"
.\.venv\Scripts\python.exe -m manager_rifiuti
```

## Home Assistant

1. Copia `custom_components/manager_rifiuti` in `/config/custom_components/`.
2. Riavvia Home Assistant.
3. Aggiungi **Manager Rifiuti** da *Impostazioni → Dispositivi e servizi*.
4. Copia nell'app il valore del sensore **ID importazione Manager Rifiuti**.
5. Nelle opzioni scegli orari e servizi `notify.mobile_app_*`, uno per riga.

L'integrazione crea un calendario, i sensori delle raccolte di oggi e domani e
un pulsante per indicare che i rifiuti sono già stati esposti.

## Build portabile Windows

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
.\.venv\Scripts\python.exe -m PyInstaller manager-rifiuti.spec --clean --noconfirm
```

L'applicazione si trova in `dist/ManagerRifiuti/ManagerRifiuti.exe`. La cartella
`ManagerRifiuti` è portabile e contiene tutte le dipendenze: non copiare il solo
file `.exe`. Python non è necessario sul computer che esegue il pacchetto.

La workflow **Build portatile** può inoltre produrre gli ZIP per Windows x64,
macOS Intel, macOS Apple Silicon e il pacchetto Home Assistant.

## Limiti del riconoscimento

Il lettore è specializzato per la griglia a sei mesi del calendario supportato.
La revisione resta obbligatoria. Fotografie nitide, senza parti tagliate, con il
foglio interamente visibile e ripreso frontalmente danno il risultato migliore.
