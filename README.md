# ShipDesk

Flet desktop workspace for inspecting store releases and preparing screenshot assets. Runs on Windows, macOS, and Linux with Python 3.10+ and Flet. Apple connections also require OpenSSL on PATH.

Run `python app.py` (on Windows, `py app.py`). Connection settings can be entered in the app or supplied as environment variables listed in .env.example. The app does not load dotenv files automatically or persist credentials. Leave Issuer ID blank for an Apple individual key.

- Apple: list authorized apps, releases and attached build IDs, screenshot inventory by locale and device, and subscription offer configuration. Compare offer mode, active state and customer eligibility when troubleshooting redemption.
- Google: enter a short-lived OAuth access token with the Android Publisher scope and access to the target package. ShipDesk opens a temporary edit to read listing metadata, then deletes the edit without committing changes.
- Screenshots: compare two folders of PNG files by filename and SHA-256, display dimensions, and export the new folder as a ZIP. Exact file comparison can flag a change caused by encoding or metadata.

Run checks with `python -m unittest -v` and `python -m compileall -q .`.

The current build supports inspection and local export. Native mobile apps, installer packages, screenshot capture, store upload and submission, billing, and live integration verification are pending.

Use **Audit Apple account** to inspect accessible apps and **Audit this package**
to check Google Play listing text. Audit results identify observations, missing
data, and items that still require console review. Google listing reads use a
temporary edit that is discarded. Avoid running this while editing the same
package through another publishing API workflow.

Windows setup: extract the ZIP and double-click Setup.cmd. The default
destination is D:\ShipDesk. A different destination can be passed with
-ProjectPath. Setup installs the Flet desktop dependencies into an existing Python. Pillow is
required for resizing, and OpenSSL is required for connecting to Apple.

Distribution placeholders: website navigation, checkout, paid download URL,
license delivery, and signed installer are pending. The ZIP can run locally
using the desktop shortcut created by setup.
