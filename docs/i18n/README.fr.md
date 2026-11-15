# Intégration VIDAA Smart TV pour Home Assistant

<p align="center">
  <a href="../../README.md"><img src="https://img.shields.io/badge/🇬🇧_English-gray?style=flat-square" alt="English"></a>
  <a href="README.de.md"><img src="https://img.shields.io/badge/🇩🇪_Deutsch-gray?style=flat-square" alt="Deutsch"></a>
  <a href="README.it.md"><img src="https://img.shields.io/badge/🇮🇹_Italiano-gray?style=flat-square" alt="Italiano"></a>
  <a href="README.fr.md"><img src="https://img.shields.io/badge/🇫🇷_Français-blue?style=flat-square" alt="Français"></a>
  <a href="README.ru.md"><img src="https://img.shields.io/badge/🇷🇺_Русский-gray?style=flat-square" alt="Русский"></a>
  <a href="README.uk.md"><img src="https://img.shields.io/badge/🇺🇦_Українська-gray?style=flat-square" alt="Українська"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_简体中文-gray?style=flat-square" alt="简体中文"></a>
</p>

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Une intégration native Home Assistant pour téléviseurs intelligents et projecteurs fonctionnant sous **VIDAA OS** (Hisense, Toshiba, Loewe, Philips, Sharp, JVC, TOPTRO et marques partenaires).

Elle se connecte **directement** au courtier MQTT interne du téléviseur (port TLS `36669`) via des certificats clients, offrant des mises à jour push locales instantanées, le contrôle multimédia, le lancement d'applications, le Wake-on-LAN et une télécommande virtuelle, sans aucun cloud ni passerelle externe.

---

## 🔰 Démarrage Rapide (Guide Débutant)

L'installation prend moins de 3 minutes en 3 étapes simples :

### 1️⃣ Installation via le Marketplace Home Assistant
1. Dans Home Assistant, allez dans **Paramètres → Appareils et services → Marketplace → menu ⋮ → Ajouter un dépôt personnalisé**.
2. Saisissez l'URL du dépôt de ce fork (`https://github.com/T4cC0re/vidaa`), choisissez la catégorie **Intégration** et la branche **main**, puis ajoutez le dépôt.
3. Ouvrez l'entrée **VIDAA Smart TV (T4cC0re fork)** et cliquez sur **Télécharger**.

### 2️⃣ Certificat – rien à faire
Le certificat client universel VIDAA (`hisense.crt`/`hisense.key` ainsi que `client_mobile_android.p12`/`El.p12`) est **inclus dans le paquet d'intégration** (`custom_components/vidaa/certs/`) et est détecté automatiquement – aucune extraction d'APK ni dossier `ssl` nécessaire.

> [!TIP]
> **Besoin d'instructions pas à pas ?**  
> Consultez le **[Guide de démarrage rapide pour débutants](../quick_start_beginners.md)** avec captures d'écran (pour des certificats PEM personnalisés, voir le [Guide avancé SSL](../certificates.md)).

### 3️⃣ Appairage avec le code PIN à l'écran
1. Redémarrez Home Assistant (`Paramètres` → `Système` → `Redémarrer`).
2. Allez dans **Paramètres → Appareils et services → Ajouter une intégration** et recherchez **VIDAA Smart TV**.
3. Saisissez l'adresse IP locale de votre téléviseur et cliquez sur **Soumettre**.
4. Saisissez le **code PIN à 4 chiffres** affiché sur l'écran du téléviseur pour finaliser la configuration !

---

## 📺 Marques et Modèles de Téléviseurs Compatibles

Prend officiellement en charge **tous les téléviseurs sous VIDAA OS** (appairage avec **code PIN à 4 chiffres à l'écran**) :

- 📺 **Hisense** (Séries U6, U7, U8, UX, A6, A7 — U4 à U8, années 2018 à 2026+)
- 📺 **Loewe** (Séries We. SEE, stellar sous VIDAA OS)
- 📺 **Toshiba** (Modèles VIDAA C350, M550, Z670)
- 📺 **Philips / TPV** (Séries OLED, The One, PUS équipées de VIDAA OS)
- 📺 **Metz, Schneider, Telefunken, Beko, Sharp, JVC** et autres marques sous licence
- 📽️ **TOPTRO** (Projecteurs intelligents portables sous VIDAA OS)

---

## ✨ Fonctionnalités Principales

- **Contrôle 100 % Local sur le LAN (`iot_class: local_push`)** : Zéro dépendance au cloud, fonctionne dans des VLANs IoT isolés.
- **Lecteur Multimédia (`media_player`)** : Allumage/extinction, volume, sélection des sources, changement de chaîne, lancement d'applications et touches contextuelles (zapping en direct, navigation de pistes dans les applications).
- **Réglages Image & Son (`select` & `number`)** : Modes d'image (`Standard`, `Cinéma`, `Dynamique`, `Sport`, `Filmmaker`), luminosité, contraste et rétroéclairage ; modes audio et sortie sonore.
- **Télécommande Dédiée (`remote`)** : Flèches directionnelles, pavé numérique, menu, touches de couleur et répétition de touches configurable.
- **Déclencheurs d'Allumage (`device_trigger`)** : Prise en charge native du déclencheur `vidaa.turn_on` pour activer des prises connectées ou Wake-on-LAN.

---

## 📚 Bibliothèque de Documentation

| Guide | Description |
| :--- | :--- |
| 🔰 **[Guide de démarrage pour débutants](../quick_start_beginners.md)** | Instructions pas à pas ; certificat inclus dans le paquet. |
| ⚙️ **[Configuration et Options](../parameters.md)** | Référence complète de tous les paramètres et menus de configuration. |
| ⚡ **[Paramètres d'Alimentation et de Veille](../power_and_standby_settings.md)** | Comportement de veille, démarrage rapide et préservation des jetons d'appairage. |
| 📱 **[Tableaux de Bord et Cartes Lovelace](../lovelace_cards.md)** | Cartes de télécommande, cartes à boutons et modèles d'interface. |
| 🛠️ **[Services et Automatisations](../services_and_automations.md)** | Exemples YAML pour soirées cinéma, sélection d'entrées et séquences de touches. |
| 🔒 **[Certificats SSL Avancés](../certificates.md)** | Emplacements des fichiers, certificats PEM personnalisés et commandes OpenSSL. |
| 🧪 **[Outils de Test et Diagnostic CLI](../cli_tools.md)** | Utilitaires autonomes (`scripts/test_client.py`, `scripts/debug_tv.py`). |
| 🩺 **[Dépannage et Résolution de Problèmes](../troubleshooting.md)** | Diagnostic et solutions pour les erreurs de connexion et d'appairage. |
