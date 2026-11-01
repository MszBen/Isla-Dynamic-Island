# Third-party software

Isla is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE). It is built on, and the
`Isla.exe` download bundles, the following software, each under its own licence:

| Component | Used for | Licence |
|---|---|---|
| [PySide6 / Qt 6](https://doc.qt.io/qtforpython-6/) | The whole user interface | LGPL-3.0 (see below) |
| [requests](https://requests.readthedocs.io) | Looking up lyrics | Apache-2.0 |
| [winrt (pywinrt)](https://github.com/pywinrt/pywinrt) | Windows media controls | MIT |
| [PyInstaller](https://pyinstaller.org) | Building `Isla.exe` (its bootloader is inside the exe) | GPL-2.0 with a special exception that allows bundling in any app |
| [Pillow](https://python-pillow.org) | Only for generating the icon and README images (not in `Isla.exe`) | MIT-CMU (HPND) |
| [LRCLIB](https://lrclib.net) | Online lyrics service (a service, not bundled code) | see their site |

## Qt (LGPL-3.0)

Qt is used as a shared library (DLLs); Isla's own code is not a derivative of Qt. You are free to obtain Qt's source
from [qt.io](https://www.qt.io/download-open-source) and PySide6's from [code.qt.io](https://code.qt.io/cgit/pyside/pyside-setup.git/),
and to run Isla from source (`python -m isla`) with a different build of PySide6 if you prefer. The LGPL-3.0 text is at
<https://www.gnu.org/licenses/lgpl-3.0.html>.

Isla's ideas were inspired by Nusa, TwoCode and Coucou; no code from those projects is included.
