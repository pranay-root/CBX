# ⚡ CYBER BLOCKZ (CBX) AI TERMINAL ⚡



![Python 3.x](https://img.shields.io/badge/Python-3.x-blue.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Environment: Kali Linux](https://img.shields.io/badge/OS-Kali%20Linux%20%7C%20Debian-black.svg?logo=kalilinux)

**Cyber Blockz (CBX)** is an elite, autonomous AI terminal copilot designed for offensive security environments. 

Built to run seamlessly in the terminal, CBX acts as a local expert that translates natural language into direct system commands, scrapes web data, and can autonomously iterate through complex operational chains without leaving the command line.

---

## 🔥 Core Features

* **Dual Engine Support:** Run local, uncensored models via **Ollama**, or connect to cloud-scale intelligence via **NVIDIA NIM API**.
* **X11 Terminal Spawning (`/terminal`):** The AI can break out of the main prompt to launch secondary graphical terminal windows (using `x-terminal-emulator`) for listeners, reverse shells, or interactive installers.
* **Zero-Lag UI:** Optimized for Linux terminals with non-blocking ANSI line-clearing, completely eliminating GIL stuttering.
* **Execution Safety Check:** All background shells are bound by a strict 45-second execution timeout to prevent hanging commands.
* **Connection Pooling:** Lightning-fast subsequent API calls through persistent sessions.

---

## ⚙️ Prerequisites

CBX is heavily optimized for Debian-based systems, specifically **Kali Linux**.

* **Python 3**
* **Requests library:** `pip install requests`
* **X11 Emulator:** Native `x-terminal-emulator` (Pre-installed on Kali/Debian)
* *(Optional)* **Ollama:** Installed locally and running if using local models.

---

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/pranay-root/CBX.git
cd CBX
```

2. Make the script executable:
```bash
chmod +x cbx.py
pip install requests --break-system-packages
```

3. General usage
```bash
python3 cbx.py or python3 cbx.py --auto
```

4. Move it to your local binaries so you can run it from anywhere:
```bash
sudo mv cbx.py /usr/local/bin/cbx
```

---

## 💻 Usage

Launch the Agent simply by typing:

```bash
cbx
```

To run in entirely non-interactive mode (auto-approving all shell executions):
```bash
cbx --auto
```

### The Command Grid
Inside the CBX prompt, type `/` and press Enter to pull up the interactive command menu:

| Command | Action |
| :--- | :--- |
| `/set <ip>` | Sets the target IP context for the AI. |
| `/terminal` | Toggles the AI's permission to spawn new X11 terminal windows. |
| `/hack` | Toggles Agent Auto-Iteration loop (comming soon). |
| `/clear` | Resets the 49k token context memory. |
| `/save` | Exports the current session context to JSON. |
| `exit` | Closes the CBX interface. |

---

## ⚠️ Disclaimer

CBX is designed strictly for **authorized, educational, and professional security testing**. The developer assumes no liability and is not responsible for any misuse or damage caused by this program. Ensure you have explicit permission before running automated scripts or exploiting targets.


