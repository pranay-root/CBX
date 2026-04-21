#!/usr/bin/env python3
import sys
import requests
import json
import argparse
import subprocess
import re
import os
import time
import shutil
import math
import getpass

try:
    import readline
except ImportError:
    pass 

CONFIG_FILE = os.path.expanduser("~/.lsgpt_config")

# --- UI & UX Helpers ---

def print_rainbow_header():
    ascii_art = [
        "  ██████╗██╗  ██╗██████╗ ███████╗██████╗     ██████╗ ██╗      ██████╗  ██████╗██╗  ██╗███████╗",
        " ██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗    ██╔══██╗██║     ██╔═══██╗██╔════╝██║ ██╔╝╚══███╔╝",
        " ██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝    ██████╔╝██║     ██║   ██║██║     █████╔╝   ███╔╝ ",
        " ██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗    ██╔══██╗██║     ██║   ██║██║     ██╔═██╗  ███╔╝  ",
        " ╚██████╗   ██║   ██████╔╝███████╗██║  ██║    ██████╔╝███████╗╚██████╔╝╚██████╗██║  ██╗███████╗",
        "  ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝    ╚═════╝ ╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝",
        "                      ⚡ CYBER BLOCKZ AI TERMINAL ⚡                                         "
    ]
    for r_idx, line in enumerate(ascii_art):
        colored = ""
        for c_idx, char in enumerate(line):
            r = int(math.sin(0.1 * c_idx + r_idx + 0) * 127 + 128)
            g = int(math.sin(0.1 * c_idx + r_idx + 2) * 127 + 128)
            b = int(math.sin(0.1 * c_idx + r_idx + 4) * 127 + 128)
            colored += f"\033[38;2;{r};{g};{b}m{char}"
        print(colored + "\033[0m")

def print_gemini_box(cmd, output, action_type="Shell"):
    term_width = shutil.get_terminal_size().columns if sys.stdout.isatty() else 100
    border = "─" * (term_width - 4)
    print(f"\n\033[90m╭{border}╮\033[0m")
    print(f"\033[90m│\033[0m \033[92m✓\033[0m  {action_type} \033[1m{cmd}\033[0m")
    print(f"\033[90m│\033[0m")
    lines = output.strip().split('\n')
    for line in lines[:15]: 
        print(f"\033[90m│\033[0m {line[:term_width-6]}")
    if len(lines) > 15: 
        print(f"\033[90m│\033[0m \033[90m... truncated ({len(lines)-15} more lines)\033[0m")
    print(f"\033[90m╰{border}╯\033[0m")

def extract_text_from_html(html_content):
    text = re.sub(r'<script.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

# --- Config & Initialization ---

def get_llm_config():
    config = {
        "mode": "local", 
        "host": "http://127.0.0.1:11434", 
        "api_key": "", 
        "ext_model": "qwen/qwen3.5-122b-a10b"
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: config.update(json.load(f))
        except json.JSONDecodeError: 
            print("\033[91mError reading config, using defaults.\033[0m")

    print("\n\033[1m[ LLM Engine Selection ]\033[0m")
    print("1. Local Machine (Ollama)")
    print("2. NVIDIA Cloud API (NIM)")
    
    choice = input("\nSelect Engine [1 or 2] (Default 1): ").strip() or '1'
    
    if choice == '2':
        config["mode"] = "nvidia"
        print("\n\033[90m--- NVIDIA API Setup ---\033[0m")
        config["ext_url"] = "https://integrate.api.nvidia.com/v1"
        
        key_in = getpass.getpass("NVIDIA API Key (Press enter to keep saved): ").strip()
        if key_in: config["api_key"] = key_in
        
        print(f"Current Model: {config['ext_model']}")
        model_in = input("Model Name (Press enter to keep current): ").strip()
        if model_in: config["ext_model"] = model_in
    else:
        config["mode"] = "local"
        host_in = input(f"Ollama Host (Default: {config['host']}): ").strip()
        if host_in: config["host"] = host_in
        if not config["host"].startswith("http"): config["host"] = f"http://{config['host']}"

    with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
    return config

# --- Core Agent ---

class LSGPTAgent:
    def __init__(self, model_name, base_url, md_file=None, auto_mode=False, config=None):
        self.model_name = model_name
        self.base_url = base_url
        self.auto_mode = auto_mode
        self.config = config or {}
        
        self.session = requests.Session()
        
        if self.config.get("mode") == "nvidia":
            self.chat_url = f"{base_url.rstrip('/')}/chat/completions"
            self.session.headers.update({
                "Authorization": f"Bearer {self.config.get('api_key')}",
                "Content-Type": "application/json"
            })
        else:
            self.chat_url = f"{base_url.rstrip('/')}/api/chat"
            
        self.target_ip = "None"
        self.terminal_mode = False
        self.messages = []
        self.md_file = md_file
        self.load_system_prompt()

    def load_system_prompt(self):
        extra = ""
        if self.md_file and os.path.exists(self.md_file):
            with open(self.md_file, 'r') as f: 
                extra = f"\n\n--- ADDITIONAL SKILLSET / SCENARIO RULES ---\n{f.read()}"
                
        terminal_instruction = ""
        if self.terminal_mode:
            terminal_instruction = "\n6. NEW TERMINALS: You have the power to open separate terminal windows for interactive installers, reverse shells, or long-running servers. Use <spawn>command</spawn> to run a command in a brand new graphical terminal window."
        
        self.system_prompt_content = f"""You are CBX (Cyber Blockz), an elite terminal copilot and Kali Linux expert.
Target IP: {self.target_ip}

CORE DIRECTIVES (STRICT EXECUTOR MODE):
1. OBEY DIRECT INSTRUCTIONS: Only perform the exact actions requested by the user. Do not do anything extra or assume follow-up steps.
2. TERMINAL EXPERTISE: Use <execute>command</execute> to run tools silently in the background (e.g., <execute>nmap -p 80 localhost</execute>). You have root access.
3. ONLINE RESEARCH: Use <fetch>URL</fetch> to scrape web pages.
4. INTENT: Always begin your response with '✦ ' stating the exact action you are taking. Do not chat or offer advice unless specifically asked.
5. NO REDIRECTIONS: Never use `> /dev/null` for discovery. Filter large outputs using `grep`, `head`, etc.{terminal_instruction}
{extra}"""
        
        self.messages = [{"role": "system", "content": self.system_prompt_content}]

    def _call_api(self):
        payload = {
            "model": self.model_name, 
            "messages": self.messages,
            "temperature": 0.2
        }
        if self.config.get("mode") == "nvidia":
            payload["max_tokens"] = 4096
        else:
            payload["stream"] = False
            payload["options"] = {"num_ctx": 49152}

        r = self.session.post(self.chat_url, json=payload, timeout=300)
        
        if r.status_code == 429:
            print("\n\033[91m✕ API Rate Limit Exceeded.\033[0m Wait 30-60 seconds.")
            self.messages.pop() 
            return None
            
        r.raise_for_status() 
        
        if self.config.get("mode") == "nvidia":
            return r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        return r.json().get("message", {}).get("content", "")

    def chat(self, user_prompt):
        task_start = time.time()
        self.messages.append({"role": "user", "content": user_prompt})
        
        sys.stdout.write(f"\r\033[1;36m[ CYBER BLOCKZ ⚡ ]\033[0m \033[90mThinking...\033[0m")
        sys.stdout.flush()
        
        try:
            ai_msg = self._call_api()
            
            sys.stdout.write("\r\033[K") 
            sys.stdout.flush()
            
            if not ai_msg: return

            self.messages.append({"role": "assistant", "content": ai_msg})
            
            cmds = re.findall(r'<execute>\s*((?:(?!<execute>).)*?)\s*</execute>', ai_msg, re.DOTALL | re.IGNORECASE)
            urls = re.findall(r'<fetch>\s*((?:(?!<fetch>).)*?)\s*</fetch>', ai_msg, re.DOTALL | re.IGNORECASE)
            spawns = re.findall(r'<spawn>\s*((?:(?!<spawn>).)*?)\s*</spawn>', ai_msg, re.DOTALL | re.IGNORECASE)
            
            if cmds or urls or spawns:
                intent = re.sub(r'<(execute|fetch|spawn)>.*?</\1>', '', ai_msg, flags=re.DOTALL | re.IGNORECASE).strip()
                if intent: print(f"\n{intent if intent.startswith('✦') else '✦ ' + intent}")
                
                results = self._process_commands(cmds) + self._process_urls(urls) + self._process_spawns(spawns)

                self.messages.append({"role": "user", "content": f"System Output:\n{results}\n(Awaiting user instruction)"})
                print(f"\033[90m(Ready for next instruction - {time.time() - task_start:.2f}s)\033[0m")
            else:
                print(f"\n\033[93m{ai_msg.strip() if ai_msg.strip().startswith('✦') else '✦ ' + ai_msg.strip()}\033[0m")
                print(f"\033[90m(Task Completed in {time.time() - task_start:.2f}s)\033[0m")
                
        except Exception as e:
            sys.stdout.write("\r\033[K")
            print(f"\n\033[91m✕ Chat Error: {e}\033[0m")

    def _process_commands(self, cmds):
        results = ""
        for cmd in cmds:
            if not self.auto_mode:
                if input(f"\033[90mAllow shell `{cmd}`? [y/N]: \033[0m").lower() != 'y': continue
            
            if cmd.strip().startswith("cd "):
                try:
                    os.chdir(os.path.expanduser(cmd.strip()[3:].strip()))
                    out = f"Changed directory to {os.getcwd()}"
                except Exception as e: out = str(e)
            else:
                try:
                    # 45-second execution timeout prevents hanging the copilot
                    res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=45)
                    out = res.stdout + res.stderr
                    if not out: out = "[Success - No Output]"
                except subprocess.TimeoutExpired as e:
                    partial_out = e.stdout.decode('utf-8') if getattr(e, 'stdout', None) else ""
                    out = f"{partial_out}\n\033[93m[Process timed out after 45 seconds]\033[0m"
            
            print_gemini_box(cmd, out, action_type="Shell")
            results += f"Output of `{cmd}`:\n{out}\n"
        return results
        
    def _process_spawns(self, spawns):
        results = ""
        for cmd in spawns:
            if not self.auto_mode:
                if input(f"\033[90mAllow SPAWN new terminal for `{cmd}`? [y/N]: \033[0m").lower() != 'y': continue
            
            try:
                # Safely escape the command for bash -c execution
                safe_cmd = cmd.replace("'", "'\\''")
                # Uses x-terminal-emulator, the standard Debian/Kali graphical terminal wrapper
                spawn_cmd = f"x-terminal-emulator -e bash -c '{safe_cmd}; echo \"\"; echo \"[Process Completed]\"; exec bash'"
                
                # Popen runs it completely asynchronously
                subprocess.Popen(spawn_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                out = f"[Successfully spawned in separate terminal window: {cmd}]"
                print_gemini_box(cmd, out, action_type="Spawn")
                results += f"Spawn Event:\n{out}\n"
            except Exception as e:
                out = f"Failed to spawn `{cmd}`: {e}"
                print_gemini_box(cmd, out, action_type="Spawn Error")
                results += f"{out}\n"
        return results

    def _process_urls(self, urls):
        results = ""
        for url in urls:
            if not self.auto_mode:
                if input(f"\033[90mAllow fetch `{url}`? [y/N]: \033[0m").lower() != 'y': continue
            
            try:
                req = self.session.get(url, timeout=10) 
                clean_text = extract_text_from_html(req.text)[:15000]
                out = f"Successfully read {len(clean_text)} chars from {url}"
                print_gemini_box(url, out, action_type="Fetch")
                results += f"Web Data from `{url}`:\n{clean_text}\n"
            except Exception as e:
                print(f"\033[91m✕ Fetch Failed: {e}\033[0m")
                results += f"Failed to fetch `{url}`: {e}\n"
        return results

    def interactive_loop(self):
        cmds = ['/help', '/clear', '/set', '/ip', '/save', '/auth', '/terminal', 'exit', 'quit']
        
        if 'readline' in sys.modules:
            def completer(text, state):
                options = [i for i in cmds if i.startswith(text)]
                if state < len(options):
                    return options[state]
                else:
                    return None
            
            readline.set_completer(completer)
            # Enable standard tab completion
            readline.parse_and_bind("tab: complete")
            # Show all matches on a single Tab press instead of requiring a double tap
            readline.parse_and_bind("set show-all-if-ambiguous on")
        
        print_rainbow_header()
        mode_str = "AUTO" if self.auto_mode else "MANUAL"
        print(f"\033[90mEngine: {self.model_name} | Mode: {mode_str} | Host: {self.base_url}\033[0m")

        while True:
            try:
                user_input = input("\n> ").strip()
                
                # Check for just a forward slash to manually display the menu
                if user_input == "/":
                    print("\n\033[1mAvailable Commands:\033[0m")
                    print("  \033[96m/set <ip>\033[0m   - Set Target IP")
                    print("  \033[96m/terminal\033[0m   - Toggle AI permission to spawn new terminals")
                    print("  \033[96m/clear\033[0m      - Reset Memory/Context")
                    print("  \033[96m/save\033[0m       - Export Context to JSON")
                    print("  \033[96m/help\033[0m       - Show this menu")
                    print("  \033[96mexit / quit\033[0m - Close CBX")
                    continue
                
                if not user_input: continue
                
                if user_input.lower() in ['exit', 'quit', '/exit', '/quit']:
                    break
                
                if user_input.startswith('/'):
                    parts = user_input.split()
                    cmd = parts[0].lower()
                    if cmd == '/auth': print(f"Connected: {self.base_url}")
                    elif cmd in ['/clear', '/unload']: 
                        self.load_system_prompt()
                        print("\033[92mMemory Reset.\033[0m")
                    elif cmd in ['/set', '/ip'] and len(parts) > 1:
                        self.target_ip = parts[1]
                        self.load_system_prompt()
                        print(f"\033[92mTarget set to: {self.target_ip}\033[0m")
                    elif cmd == '/terminal':
                        self.terminal_mode = not self.terminal_mode
                        self.load_system_prompt()
                        state = "\033[92mENABLED\033[0m" if self.terminal_mode else "\033[91mDISABLED\033[0m"
                        print(f"AI Terminal Spawning is now {state}.")
                    elif cmd == '/save':
                        with open("session_save.json", "w") as f: json.dump(self.messages, f, indent=2)
                        print("\033[92mSession Saved to session_save.json.\033[0m")
                    elif cmd == '/help':
                        print("\n\033[1mCommands:\033[0m\n/set <ip>  Set Target IP\n/terminal  Toggle new terminal access\n/clear     Reset Memory\n/save      Export Context\nexit       Quit")
                    else:
                        print("\033[91mUnknown command. Type / and press enter for a list.\033[0m")
                    continue
                
                self.chat(user_input)
            except KeyboardInterrupt: 
                print("\n\033[90mType exit or quit to leave.\033[0m")
            except EOFError:
                break

def main():
    parser = argparse.ArgumentParser(description="CBX AI Terminal Copilot")
    parser.add_argument("-m", "--md", help="Context markdown file")
    parser.add_argument("--auto", action="store_true", help="Run autonomously without prompts")
    args = parser.parse_args()
    
    print_rainbow_header()
    config = get_llm_config()
    
    try:
        if config["mode"] == "local":
            m_data = requests.get(f"{config['host']}/api/tags", timeout=5).json().get('models', [])
            print("\n\033[1m[ Local Models Found ]\033[0m")
            for i, m in enumerate(m_data): print(f"[{i+1}] {m['name']}")
            idx = int(input("\nSelect model (Default 1): ") or 1) - 1
            model_name = m_data[idx]['name']
            agent = LSGPTAgent(model_name, config['host'], args.md, args.auto, config=config)
        else:
            print(f"\n\033[92mConnecting to NVIDIA NIM: {config['ext_model']}\033[0m")
            agent = LSGPTAgent(config['ext_model'], config['ext_url'], args.md, args.auto, config=config)
            
        agent.interactive_loop()
    except requests.exceptions.RequestException as e:
        print(f"\n\033[91mConnection Failed: Could not connect to LLM backend. ({e})\033[0m")
    except Exception as e: 
        print(f"\n\033[91mInitialization Error: {e}\033[0m")

if __name__ == "__main__": 
    main()
