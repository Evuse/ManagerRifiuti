# Manager Rifiuti

Applicazione desktop locale per leggere il calendario semestrale del Comune,
revisionare le raccolte riconosciute e importarle in Home Assistant. Nessuna
immagine lascia il computer: OpenCV e RapidOCR lavorano offline.

## Da dove iniziare

La guida completa per un Mac Intel e Home Assistant OS è disponibile in
[`docs/GUIDA_MAC_INTEL.md`](docs/GUIDA_MAC_INTEL.md). Seguila nell'ordine:
download dell'app, installazione della custom integration, configurazione delle
notifiche, importazione della foto e verifica finale.

## Avvio per sviluppatori

```bash
python -m venv .venv
. .venv/bin/activate                    # Windows: .venv\Scripts\activate
pip install -e '.[ocr,test]'
python -m manager_rifiuti
```

Il flusso guidato accetta uno o due file, corregge orientamento e prospettiva,
mostra una revisione obbligatoria, richiede la conferma dell'anno e infine
invia il JSON al webhook della custom integration.

## Home Assistant

1. Copiare `custom_components/manager_rifiuti` in `/config/custom_components/`.
2. Riavviare Home Assistant.
3. Aggiungere **Manager Rifiuti** da *Impostazioni → Dispositivi e servizi*.
4. Copiare il valore del sensore **ID importazione Manager Rifiuti** nell'app desktop.
5. Nelle opzioni scegliere orari e servizi `notify.mobile_app_*` (uno per riga).

L'integrazione crea `calendar.raccolta_rifiuti`, due sensori e un pulsante per
segnare come eseguite tutte le raccolte di domani. Ogni notifica contiene anche
un'azione dedicata; le raccolte multiple generano notifiche separate.

## Build standalone

Le build sono prodotte su macchine native perché PyInstaller non effettua
cross-compilation:

```bash
pip install -e '.[build]'
pyinstaller manager-rifiuti.spec --clean --noconfirm
```

La workflow GitHub Actions genera ZIP portabili per Windows x64, macOS Intel e
macOS Apple Silicon. Al primo avvio non è richiesta alcuna installazione.

## Limiti del riconoscimento

Il lettore è intenzionalmente specializzato per la griglia a sei mesi mostrata
nel calendario fornito. Evidenzia le celle incerte e non consente l'esportazione
prima della revisione. Fotografie nitide, senza parti tagliate e con il foglio
interamente visibile danno il risultato migliore.
