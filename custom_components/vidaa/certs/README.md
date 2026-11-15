# Bundled VIDAA mTLS client certificate

The mutual-TLS client keystore that Hisense/VIDAA bundles inside the official
free "VIDAA Smart TV" Android app (`com.universal.remote.multi`). Every VIDAA
OS brand (Hisense, Toshiba, Loewe, Philips, Sharp, JVC, TOPTRO) accepts this
same keystore; it is anchored to Hisense's private root CA `RemoteCA` and is
paired with the on-screen 4-digit PIN pairing (the cert alone does not
authorize anything).

This fork ships the certificate **inside the integration package** so no
manual `/config/ssl/` setup step is required. The integration's certificate
resolver (`protocol/certs.py`) auto-discovers this `certs/` directory by
walking up from the package root, and the filenames below match the built-in
candidate lists directly:

| File | Purpose |
| --- | --- |
| `hisense.crt` / `hisense.key` | Primary PEM pair (the `hisense` filename also yields the brand hint `his`). First candidates for the `auto` and `modern` auth profiles. |
| `client_mobile_android.p12` | The keystore as extracted from the APK (PKCS#12 fallback, password `186e990688070325a1c4b0ce275d2388`). |
| `El.p12` | Byte-identical copy under the legacy filename used by older guides. |
| `remote_ca.pem` | Public `RemoteCA` root for optional strict server verification. |
| `CHECKSUMS.sha256` | SHA-256 of every file. |

## Provenance

- Source: `res/raw/client_mobile_android.p12` inside the base APK of
  **VIDAA Smart TV `com.universal.remote.multi` version 1.09.06.003.1**,
  fetched with `apkeep -d apk-pure`. `.xapk` container sha256
  `2bec0de0eacebc0575a6c2fd4ae396aa8066d921ff7eb187338f84a5bb0e8ab2`;
  inner base `com.universal.remote.multi.apk` sha256
  `62fe81383a9465714d0a25ff3d0df0d0c8c3bfe78c50a0a7466436d29a0df496`.
- Keystore password `186e990688070325a1c4b0ce275d2388` opens store MAC,
  cert bag and shrouded key bag.
- Certificate: `CN=VidaaAppAndroidV01, OU=multimedia, O=hh, ST=shandong, C=CN`,
  issuer `CN=RemoteCA`, serial `0C` (12), validity `2024-06-27 … 2034-06-25`,
  SHA-256 fingerprint `31:F9:14:63:0F:86:36:D6:C4:31:3E:02:E9:EB:37:24:B4:70:6C:6B:50:49:C8:38:B0:42:13:AB:56:90:5A:A3`.
- `openssl verify -CAfile remote_ca.pem hisense.crt` → **OK** (cryptographically
  signed by Hisense's RemoteCA). Extracted private key's public key matches the
  certificate public key.
- Matches the independent third-party spec in
  `warrenrees/pyvidaa/VIDAA_PROTOCOL_ANALYSIS.md` (subject, issuer, serial 12,
  validity, password all identical) — this is the modern 2024-generation cert,
  not the 2018 RemoteNOW one that new firmware rejects (`rc: 5`).

This is the same key that every official VIDAA app ships — a vendor-shared
interoperability key, not a personal or device-specific secret. Verified
against a Hisense U7NQ (VIDAA 2024/2025 generation): TLSv1.3 handshake with
client cert succeeds and the `modern` dynamic auth profile is accepted.

The files remain the intellectual property of Hisense/VIDAA; they are obtained
from the vendor's own freely distributed app, for local interoperability with
hardware you own.
