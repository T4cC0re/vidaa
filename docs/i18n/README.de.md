# VIDAA Smart TV Integration für Home Assistant

<p align="center">
  <a href="../../README.md"><img src="https://img.shields.io/badge/🇬🇧_English-gray?style=flat-square" alt="English"></a>
  <a href="README.de.md"><img src="https://img.shields.io/badge/🇩🇪_Deutsch-blue?style=flat-square" alt="Deutsch"></a>
  <a href="README.it.md"><img src="https://img.shields.io/badge/🇮🇹_Italiano-gray?style=flat-square" alt="Italiano"></a>
  <a href="README.fr.md"><img src="https://img.shields.io/badge/🇫🇷_Français-gray?style=flat-square" alt="Français"></a>
  <a href="README.ru.md"><img src="https://img.shields.io/badge/🇷🇺_Русский-gray?style=flat-square" alt="Русский"></a>
  <a href="README.uk.md"><img src="https://img.shields.io/badge/🇺🇦_Українська-gray?style=flat-square" alt="Українська"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_简体中文-gray?style=flat-square" alt="简体中文"></a>
</p>

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Eine native Home Assistant-Integration für Smart-TVs und Projektoren mit **VIDAA OS** (Hisense, Toshiba, Loewe, Philips, Sharp, JVC, TOPTRO und Partner-Marken).

Verbindet sich **direkt** mit dem internen MQTT-Broker des Fernsehers (TLS-Port `36669`) mittels Client-Zertifikaten. Bietet sofortige lokale Push-Aktualisierungen, Mediensteuerung, App-Start, Wake-on-LAN und virtuelle Fernbedienung – ganz ohne Cloud oder externe Bridges.

---

## 🔰 Schnellstart (Anleitung für Einsteiger)

Die Einrichtung dauert weniger als 3 Minuten in 3 einfachen Schritten:

### 1️⃣ Installation über den Home Assistant Marketplace
1. Gehen Sie zu **Einstellungen → Geräte & Dienste → Marketplace → ⋮-Menü → Benutzerdefiniertes Repository hinzufügen**.
2. Geben Sie die Repository-URL dieses Forks ein (`https://github.com/T4cC0re/vidaa`), wählen Sie die Kategorie **Integration** und den Branch **main**, und fügen Sie das Repository hinzu.
3. Öffnen Sie den Eintrag **VIDAA Smart TV (T4cC0re fork)** und klicken Sie auf **Herunterladen**.

### 2️⃣ Zertifikat – nichts zu tun
Das universelle VIDAA-Client-Zertifikat (`hisense.crt`/`hisense.key` sowie `client_mobile_android.p12`/`El.p12`) ist **bereits im Integrationspaket enthalten** (`custom_components/vidaa/certs/`) und wird automatisch erkannt – kein APK-Entpacken, kein `ssl`-Ordner erforderlich.

> [!TIP]
> **Schritt-für-Schritt-Anleitung gesucht?**  
> Siehe **[Schnellstart-Leitfaden für Einsteiger](../quick_start_beginners.md)** mit Screenshots (für eigene PEM-Zertifikate siehe [SSL-Zertifikate](../certificates.md)).

### 3️⃣ Kopplung mit Bildschirm-PIN
1. Starten Sie Home Assistant neu (`Einstellungen` → `System` → `Neu starten`).
2. Gehen Sie zu **Einstellungen → Geräte & Dienste → Integration hinzufügen** und suchen Sie nach **VIDAA Smart TV**.
3. Geben Sie die lokale IP-Adresse Ihres Fernsehers ein und klicken Sie auf **Absenden**.
4. Geben Sie den auf dem Fernsehbildschirm angezeigten **4-stelligen PIN-Code** ein. Fertig!

---

## 📺 Unterstützte TV-Marken & Modelle

Unterstützt offiziell **alle Smart-TVs mit VIDAA OS** (Kopplung per **4-stelligem Bildschirm-PIN**):

- 📺 **Hisense** (U6, U7, U8, UX, A6, A7 Serien — U4 bis U8, Baujahre 2018 bis 2026+)
- 📺 **Loewe** (We. SEE, stellar VIDAA OS Serien)
- 📺 **Toshiba** (C350, M550, Z670 VIDAA-Modelle)
- 📺 **Philips / TPV** (OLED, The One, PUS Serien mit VIDAA OS)
- 📺 **Metz, Schneider, Telefunken, Beko, Sharp, JVC** und weitere Lizenzpartner
- 📽️ **TOPTRO** (Tragbare Smart-Beamer mit VIDAA OS)

---

## ✨ Wichtigste Funktionen

- **100 % Lokale LAN-Steuerung (`iot_class: local_push`)**: Vollständig lokal, keine Cloud-Abhängigkeit, funktioniert in isolierten IoT-VLANs.
- **Mediaplayer**: Ein-/Ausschalten, Lautstärkeregelung, Eingangsquellen, Senderumschaltung, App-Start und kontextsensitive Tasten (Senderwechsel im Live-TV, Titelsprung in Apps).
- **Bild & Tonjustierung (`select` & `number`)**: Bildmodi (`Standard`, `Kino`, `Dynamisch`, `Sport`, `Filmmaker`) und Helligkeit/Kontrast/Hintergrundbeleuchtung einstellen; Tonmodi und Tonausgabe umschalten.
- **Dedizierte Fernbedienung (`remote`)**: Steuerkreuz-Navigation, Zifferntasten, Menü, Farbtasten und konfigurierbare Tastenwiederholung.
- **Einschalt-Automationen (`device_trigger`)**: Native Unterstützung für `vidaa.turn_on`-Trigger zum Schalten von Zwischensteckern oder Wake-on-LAN.

---

## 📚 Dokumentations-Bibliothek

| Leitfaden | Beschreibung |
| :--- | :--- |
| 🔰 **[Einsteiger-Schnellstart](../quick_start_beginners.md)** | Schritt-für-Schritt-Anleitung; Zertifikat ist im Paket enthalten. |
| ⚙️ **[Konfiguration & Optionen](../parameters.md)** | Vollständige Parameter-Referenz für alle Einstellungsmenüs. |
| ⚡ **[Strom- & Standby-Einstellungen](../power_and_standby_settings.md)** | Standby-Verhalten, Schnellstart und Schutz vor Token-Verlust. |
| 📱 **[Lovelace Dashboards & Karten](../lovelace_cards.md)** | Fernbedienungs-Karten, Button-Cards und Dashboard-Vorlagen. |
| 🛠️ **[Dienste & Automationen](../services_and_automations.md)** | Fertige YAML-Vorlagen für Kinoabende, Eingangswahl und Tastenfolgen. |
| 🔒 **[Erweiterte SSL-Zertifikate](../certificates.md)** | Dateipfade, eigene PEM-Zertifikate und OpenSSL-Befehle. |
| 🧪 **[CLI-Test & Diagnose-Tools](../cli_tools.md)** | Eigenständige Werkzeuge (`scripts/test_client.py`, `scripts/debug_tv.py`). |
| 🩺 **[Fehlerbehebung & Problembehebung](../troubleshooting.md)** | Diagnose und Lösungen für Verbindungs- und Kopplungsfehler. |
