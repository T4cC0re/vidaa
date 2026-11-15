# Integrazione VIDAA Smart TV per Home Assistant

<p align="center">
  <a href="../../README.md"><img src="https://img.shields.io/badge/🇬🇧_English-gray?style=flat-square" alt="English"></a>
  <a href="README.de.md"><img src="https://img.shields.io/badge/🇩🇪_Deutsch-gray?style=flat-square" alt="Deutsch"></a>
  <a href="README.it.md"><img src="https://img.shields.io/badge/🇮🇹_Italiano-blue?style=flat-square" alt="Italiano"></a>
  <a href="README.fr.md"><img src="https://img.shields.io/badge/🇫🇷_Français-gray?style=flat-square" alt="Français"></a>
  <a href="README.ru.md"><img src="https://img.shields.io/badge/🇷🇺_Русский-gray?style=flat-square" alt="Русский"></a>
  <a href="README.uk.md"><img src="https://img.shields.io/badge/🇺🇦_Українська-gray?style=flat-square" alt="Українська"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_简体中文-gray?style=flat-square" alt="简体中文"></a>
</p>

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Integrazione nativa di Home Assistant per Smart TV e proiettori con sistema operativo **VIDAA OS** (Hisense, Toshiba, Loewe, Philips, Sharp, JVC, TOPTRO e marchi partner).

Si connette **direttamente** al broker MQTT interno del televisore (porta TLS `36669`) tramite certificati client, offrendo aggiornamenti push locali istantanei, controllo del lettore multimediale, avvio delle app, Wake-on-LAN e telecomando virtuale senza bridge o cloud.

---

## 🔰 Guida Rapida (Primi Passi)

La configurazione richiede meno di 3 minuti in 3 semplici passaggi:

### 1️⃣ Installazione tramite il Marketplace di Home Assistant
1. In Home Assistant vai su **Impostazioni → Dispositivi e servizi → Marketplace → menu ⋮ → Aggiungi repository personalizzato**.
2. Inserisci l'URL del repository di questo fork (`https://github.com/T4cC0re/vidaa`), scegli la categoria **Integrazione** e il ramo **main**, poi aggiungi il repository.
3. Apri la voce **VIDAA Smart TV (T4cC0re fork)** e fai clic su **Scarica**.

### 2️⃣ Certificato – nulla da fare
Il certificato client VIDAA universale (`hisense.crt`/`hisense.key` più `client_mobile_android.p12`/`El.p12`) è **incluso nel pacchetto dell'integrazione** (`custom_components/vidaa/certs/`) e viene rilevato automaticamente – nessuna estrazione APK, nessuna cartella `ssl`.

> [!TIP]
> **Serve una guida passo dopo passo?**  
> Consulta la **[Guida introduttiva per principianti](../quick_start_beginners.md)** con schermate dettagliate (per certificati PEM personalizzati, vedi la [Guida avanzata SSL](../certificates.md)).

### 3️⃣ Associazione con PIN su Schermo
1. Riavvia Home Assistant (`Impostazioni` → `Sistema` → `Riavvia`).
2. Vai su **Impostazioni → Dispositivi e servizi → Aggiungi integrazione** e cerca **VIDAA Smart TV**.
3. Inserisci l'indirizzo IP locale del tuo televisore e fai clic su **Invia**.
4. Digita il **codice PIN a 4 cifre** visualizzato sullo schermo della TV per completare la configurazione!

---

## 📺 Marchi e Modelli Supportati

Supporta ufficialmente **qualsiasi Smart TV con sistema VIDAA OS** (associazione tramite **PIN a 4 cifre**):

- 📺 **Hisense** (serie U6, U7, U8, UX, A6, A7 — da U4 a U8, modelli dal 2018 al 2026+)
- 📺 **Toshiba** (edizioni C350, M550, Z670 VIDAA)
- 📺 **Loewe** (serie We. SEE, stellar con VIDAA OS)
- 📺 **Philips / TPV** (serie OLED, The One, PUS con VIDAA OS)
- 📺 **Sharp, JVC, Schneider, Beko, Telefunken** e altri marchi autorizzati
- 📽️ **TOPTRO** (proiettori portatili con VIDAA OS)

---

## ✨ Funzionalità Principali

- **Controllo LAN Locale al 100% (`iot_class: local_push`)**: Nessuna dipendenza dal cloud, funziona perfettamente anche in VLAN isolate senza accesso a Internet.
- **Piattaforma Media Player**: Accensione/spegnimento, controllo volume, cambio sorgente d'ingresso, selezione canali e avvio rapido delle app (Netflix, Prime Video, YouTube, RaiPlay, Mediaset Infinity, TIMVISION, ecc.).
- **Regolazione Immagine e Audio (`select` e `number`)**: Modalità immagine (`Standard`, `Cinema`, `Dinamica`, `Sport`, `Filmmaker`) e regolazione di Luminosità, Contrasto e Retroilluminazione; selezione modalità audio ed equalizzatore.
- **Telecomando Dedicato (`remote`)**: Navigazione con D-pad, tasti colorati, menu e ripetizione tasti configurabile.
- **Automazioni di Accensione (`device_trigger`)**: Supporto nativo per trigger `vidaa.turn_on` per accendere prese smart o relè.

---

## 📚 Guide e Documentazione Completa

| Guida | Descrizione |
| :--- | :--- |
| 🔰 **[Guida Rapida Principianti](../quick_start_beginners.md)** | Configurazione guidata; certificato incluso nel pacchetto. |
| ⚙️ **[Parametri e Opzioni](../parameters.md)** | Riferimento completo a tutte le impostazioni e schede di configurazione. |
| ⚡ **[Impostazioni di Alimentazione e Standby](../power_and_standby_settings.md)** | Risparmio energetico, avvio rapido e prevenzione della perdita di token. |
| 📱 **[Schede Lovelace e Dashboard](../lovelace_cards.md)** | Telecomandi grafici, Button Card e template per la dashboard. |
| 🛠️ **[Automazioni ed Esempi di Servizi](../services_and_automations.md)** | Script e ricette YAML pronte all'uso per serate cinema e routine. |
| 🔒 **[Configurazione Avanzata SSL](../certificates.md)** | Gestione certificati PEM, directory di archiviazione e comandi OpenSSL. |
| 🧪 **[Strumenti di Test e Diagnostica CLI](../cli_tools.md)** | Script standalone di diagnostica (`scripts/test_client.py`, `scripts/debug_tv.py`). |
| 🩺 **[Risoluzione dei Problemi](../troubleshooting.md)** | Diagnosi rapida degli errori di associazione e problemi di rete. |
