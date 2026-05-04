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
import atexit

try:
    import readline
    HISTORY_FILE = os.path.expanduser("~/.cbx_history")
    try:
        readline.read_history_file(HISTORY_FILE)
        readline.set_history_length(1000)
    except FileNotFoundError:
        pass
    atexit.register(readline.write_history_file, HISTORY_FILE)
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
        self.memory_file = os.path.expanduser("~/.cbx_memory.log")
        
        self.load_system_prompt(reset_messages=True)

    def load_system_prompt(self, reset_messages=True):
        extra = ""
        if self.md_file and os.path.exists(self.md_file):
            with open(self.md_file, 'r') as f: 
                extra = f"\n\n--- ADDITIONAL SKILLSET / SCENARIO RULES ---\n{f.read()}"
        
        memory_context = ""
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f:
                logs = f.read().strip()
                if logs:
                    memory_context = f"\n\n--- PERSISTENT MEMORY / DISCOVERIES ---\n{logs}\n-------------------------------------"

        terminal_instruction = ""
        if self.terminal_mode:
            terminal_instruction = "\n6. NEW TERMINALS: Use <spawn>command</spawn> to open a separate interactive graphical terminal window. This terminal will remain open for the user even after the command finishes."

        self.system_prompt_content = f"""You are CBX (Cyber Blockz), an elite offensive security agent.
Target IP: {self.target_ip}

STRICT OPERATIONAL RULES:
1. ACTION OVER TALK: Never describe what you "will" do. Use <execute> to actually perform actions.
2. NO HALLUCINATION: Do not report that a command was successful until you see the 'System Output' in the next turn.
3. MANDATORY FETCH: Before installing any tool from a URL, you MUST use <fetch>URL</fetch> to read the documentation/README first.
4. MEMORY: Use <log>information</log> to save critical findings (ports, versions, paths).
5. FINISHING: Once you have successfully retrieved the requested information or completed the final action for the objective, you MUST immediately output <finish>Summary of results</finish> to exit the autonomous loop. Do not continue to search once the goal is met.
{terminal_instruction}

TOOLS:
- <execute>command</execute> : Run shell commands in the background (You read the results).
- <fetch>URL</fetch> : Scrape web pages/GitHub READMEs.
- <log>text</log> : Save to persistent memory.
- <spawn>command</spawn> : Open a new graphical terminal window for the user to interact with.
- <finish>text</finish> : Use this immediately when the objective is achieved.
{extra}{memory_context}"""
        
        if reset_messages:
            self.messages = [{"role": "system", "content": self.system_prompt_content}]
        elif self.messages:
            self.messages[0]["content"] = self.system_prompt_content

    def _stream_api(self):
        payload = {
            "model": self.model_name, 
            "messages": self.messages,
            "temperature": 0.1,
            "stream": True,
            "max_tokens": 4096
        }
        
        try:
            if self.config.get("mode") == "nvidia":
                r = self.session.post(self.chat_url, json=payload, stream=True, timeout=60)
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str.strip() == '[DONE]': break
                            try:
                                chunk = json.loads(data_str)['choices'][0]['delta'].get('content', '')
                                if chunk: yield chunk
                            except: pass
            else:
                payload["options"] = {"num_ctx": 49152}
                r = self.session.post(self.chat_url, json=payload, stream=True, timeout=60)
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line.decode('utf-8')).get('message', {}).get('content', '')
                            if chunk: yield chunk
                        except: pass
        except requests.exceptions.RequestException as e:
            yield f"\n[API Connection Error: {e}]"

    def chat(self, user_prompt, is_autonomous=False):
        self.messages.append({"role": "user", "content": user_prompt})
        sys.stdout.write(f"\r\033[1;36m[ CYBER BLOCKZ ⚡ ]\033[0m\n")
        sys.stdout.flush()
        
        ai_msg = ""
        line_buffer = ""
        in_code_block = False

        try:
            for chunk in self._stream_api():
                ai_msg += chunk
                line_buffer += chunk
                
                while '\n' in line_buffer:
                    line, line_buffer = line_buffer.split('\n', 1)
                    
                    line = re.sub(r'(</?(?:execute|fetch|log|spawn|finish)[^>]*>)', r'\033[1;36m\1\033[0m', line)
                    line = re.sub(r'\*\*(.*?)\*\*', r'\033[1m\1\033[0m', line)
                    
                    if line.strip().startswith('```'):
                        in_code_block = not in_code_block
                        if in_code_block:
                            print(f"\033[90m┌── [ Code / Data ] ──────────────\033[33m")
                        else:
                            print(f"\033[90m└─────────────────────────────────\033[0m")
                        continue
                    
                    if in_code_block:
                        print(f"\033[33m│\033[0m {line}")
                    else:
                        print(line)

            if line_buffer:
                line = line_buffer
                line = re.sub(r'(</?(?:execute|fetch|log|spawn|finish)[^>]*>)', r'\033[1;36m\1\033[0m', line)
                line = re.sub(r'\*\*(.*?)\*\*', r'\033[1m\1\033[0m', line)
                if in_code_block:
                    print(f"\033[33m│\033[0m {line}\n\033[90m└─────────────────────────────────\033[0m")
                else:
                    print(line)

        except KeyboardInterrupt:
            if is_autonomous:
                raise KeyboardInterrupt
            print("\n\033[91m[!] Generation Interrupted by User. Proceeding with captured output.\033[0m")

        if not ai_msg: return False, ""
        self.messages.append({"role": "assistant", "content": ai_msg})
        
        logs = re.findall(r'<log>\s*((?:(?!<log>).)*?)\s*</log>', ai_msg, re.DOTALL | re.IGNORECASE)
        for entry in logs:
            with open(self.memory_file, 'a') as f:
                f.write(f"[*] {entry.strip()}\n")
            print(f"\033[93m[MEMORY SAVED]\033[0m {entry.strip()[:70]}...")
            
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f: lines = f.readlines()
            if len(lines) > 50:
                with open(self.memory_file, 'w') as f: f.writelines(lines[-50:])
                
        if logs: self.load_system_prompt(reset_messages=False)

        if "<finish>" in ai_msg.lower():
            return True, ai_msg

        cmds = re.findall(r'<execute>\s*((?:(?!<execute>).)*?)\s*</execute>', ai_msg, re.DOTALL | re.IGNORECASE)
        urls = re.findall(r'<fetch>\s*((?:(?!<fetch>).)*?)\s*</fetch>', ai_msg, re.DOTALL | re.IGNORECASE)
        spawns = re.findall(r'<spawn>\s*((?:(?!<spawn>).)*?)\s*</spawn>', ai_msg, re.DOTALL | re.IGNORECASE)
        
        results = ""
        if cmds or urls or spawns:
            results = self._process_commands(cmds) + self._process_urls(urls) + self._process_spawns(spawns)
            if not is_autonomous:
                self.messages.append({"role": "user", "content": f"System Output:\n{results}"})
            return False, results
        else:
            return False, ""

    def _run_autonomous_loop(self, goal):
        orig_auto = self.auto_mode
        self.auto_mode = True 
        print(f"\n\033[1;35m[⚡] STARTING AUTONOMOUS AGENT\033[0m\n\033[90mObjective: {goal}\033[0m")
        
        current_prompt = f"OBJECTIVE: {goal}. Start by investigating requirements. Use <fetch> or <execute>."
        
        try:
            for i in range(1, 21):
                print(f"\n\033[1;34m--- Iteration {i}/20 ---\033[0m")
                
                if len(self.messages) > 12:
                    self.messages = [self.messages[0]] + self.messages[-4:]

                finished, output = self.chat(current_prompt, is_autonomous=True)
                
                if finished:
                    print(f"\n\033[92m[✔] GOAL ACHIEVED\033[0m")
                    break
                
                if not output.strip():
                    current_prompt = "You did not output any <execute> or <fetch> commands. If the objective is complete, you MUST use <finish>Summary</finish>. Otherwise, continue your attack."
                else:
                    current_prompt = f"System Output:\n{output[:5000]}\nReview output. If the main objective is achieved, output <finish>Summary</finish>. Otherwise, use <execute>."

        except KeyboardInterrupt:
            print("\n\033[91m[!] Autonomous Mode Aborted by User.\033[0m")
            
        finally:
            self.auto_mode = orig_auto

    def _process_commands(self, cmds):
        res_text = ""
        for cmd in cmds:
            if not self.auto_mode:
                if input(f"\n\033[90mAllow shell `{cmd}`? [y/N]: \033[0m").lower() != 'y': continue
            
            try:
                if cmd.strip().startswith("cd "):
                    os.chdir(os.path.expanduser(cmd.strip()[3:].strip()))
                    out = f"Changed directory to {os.getcwd()}"
                    print_gemini_box(cmd, out, "Shell")
                else:
                    term_width = shutil.get_terminal_size().columns if sys.stdout.isatty() else 100
                    border = "─" * (term_width - 4)
                    print(f"\n\033[90m╭{border}╮\033[0m")
                    print(f"\033[90m│\033[0m \033[92m✓\033[0m  Executing \033[1m{cmd}\033[0m \033[90m(Press Ctrl+C to abort command)\033[0m")
                    print(f"\033[90m│\033[0m")
                    
                    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                    out_lines = []
                    
                    try:
                        for line in process.stdout:
                            line_clean = line.rstrip()
                            print(f"\033[90m│\033[0m {line_clean[:term_width-6]}")
                            out_lines.append(line)
                        process.wait()
                    except KeyboardInterrupt:
                        process.terminate()
                        print(f"\033[90m│\033[0m \033[91m[!] Command Interrupted by User. Captured partial output.\033[0m")
                        out_lines.append("\n[!] Process terminated early by user.")
                    
                    print(f"\033[90m╰{border}╯\033[0m")
                    
                    out = "".join(out_lines)
                    if not out.strip(): out = "[Success - No Output]"
            except Exception as e: 
                out = f"Error: {e}"
                print_gemini_box(cmd, out, "Shell Error")
            
            res_text += f"Output of `{cmd}`:\n{out}\n"
        return res_text

    def _process_urls(self, urls):
        res_text = ""
        for url in urls:
            try:
                r = self.session.get(url, timeout=15)
                data = extract_text_from_html(r.text)[:10000]
                print_gemini_box(url, f"Fetched {len(data)} chars", "Fetch")
                res_text += f"Web Data from `{url}`:\n{data}\n"
            except Exception as e: res_text += f"Fetch failed for {url}: {e}\n"
        return res_text

    def _process_spawns(self, spawns):
        for cmd in spawns:
            try:
                safe = cmd.replace("'", "'\\''")
                if sys.platform == "win32":
                    full_cmd = f'start cmd /k "{cmd}"'
                elif sys.platform == "darwin":
                    safe_mac = cmd.replace('"', '\\"')
                    full_cmd = f"osascript -e 'tell app \"Terminal\" to do script \"{safe_mac}; exec bash\"'"
                else:
                    terminals = ['x-terminal-emulator', 'gnome-terminal', 'konsole', 'xfce4-terminal', 'xterm']
                    chosen_term = 'xterm'
                    for t in terminals:
                        if shutil.which(t):
                            chosen_term = t
                            break
                    if chosen_term in ['gnome-terminal', 'konsole', 'xfce4-terminal']:
                        full_cmd = f"{chosen_term} -e \"bash -c '{safe}; echo \\\"[Command Complete. Dropping to interactive shell...]\\\"; exec bash'\""
                    else:
                        full_cmd = f"{chosen_term} -e bash -c '{safe}; echo \"[Command Complete. Dropping to interactive shell...]\"; exec bash'"
                
                subprocess.Popen(full_cmd, shell=True)
                print_gemini_box(cmd, "Terminal Spawned (Interactive Shell Open)", "Spawn")
            except Exception as e: print(f"Spawn Error: {e}")
        return "[Spawn Commands Sent to External Terminal]"

    def interactive_loop(self):
        cmds_list = ['/help', '/clear', '/set', '/ip', '/save', '/auth', '/terminal', '/cbx', 'exit', 'quit']
        
        if 'readline' in sys.modules:
            def completer(text, state):
                options = [i for i in cmds_list if i.startswith(text)]
                if state < len(options):
                    return options[state]
                else:
                    return None
            
            readline.set_completer(completer)
            readline.parse_and_bind("tab: complete")
            readline.parse_and_bind("set show-all-if-ambiguous on")

        while True:
            try:
                inp = input("\n> ").strip()
                if not inp: continue
                if inp.lower() in ['exit', 'quit']: break
                
                if inp == "/":
                    print("\n\033[90m[ Available Commands ]")
                    print("  /cbx <goal> - Launch autonomous agent")
                    print("  /set <ip>   - Set Target IP")
                    print("  /terminal   - Toggle AI permission to spawn new terminals")
                    print("  /clear      - Reset Memory/Context and Logs")
                    print("  /help       - Show this menu")
                    print("  exit / quit - Close CBX\033[0m")
                    continue
                
                if inp.startswith('/'):
                    p = inp.split()
                    cmd = p[0].lower()
                    if cmd == '/cbx': self._run_autonomous_loop(" ".join(p[1:]))
                    elif cmd in ['/set', '/ip'] and len(p)>1: 
                        self.target_ip = p[1]
                        self.load_system_prompt(reset_messages=True)
                        print(f"Target: {self.target_ip}")
                    elif cmd == '/terminal':
                        self.terminal_mode = not self.terminal_mode
                        self.load_system_prompt(reset_messages=False)
                        state = "\033[92mENABLED\033[0m" if self.terminal_mode else "\033[91mDISABLED\033[0m"
                        print(f"AI Terminal Spawning is now {state}.")
                    elif cmd == '/clear':
                        if os.path.exists(self.memory_file): os.remove(self.memory_file)
                        self.load_system_prompt(reset_messages=True)
                        print("Context & Logs cleared.")
                    elif cmd == '/help':
                        print("/cbx <goal> | /set <ip> | /clear | /terminal | exit")
                    continue
                
                self.chat(inp)
            except KeyboardInterrupt: 
                print("\nUse 'exit' to quit.")

# --- Initialization ---

def get_config():
    config = {"mode": "local", "host": "[http://127.0.0.1:11434](http://127.0.0.1:11434)", "api_key": "", "ext_model": "qwen2.5-coder:latest"}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: config.update(json.load(f))
        except:
            pass
    
    print_rainbow_header()
    
    print("\n[ LLM Engine Selection ]")
    print("1. Local Machine (Ollama)")
    print("2. NVIDIA Cloud API (NIM)")
    
    c = input("\nSelect Engine [1 or 2] (Default 1): ") or "1"
    
    if c == "2":
        config["mode"] = "nvidia"
        config["ext_url"] = config.get("ext_url", "[https://integrate.api.nvidia.com/v1](https://integrate.api.nvidia.com/v1)")
        
        print("\n--- NVIDIA API Setup ---")
        key = getpass.getpass("NVIDIA API Key (Press enter to keep saved): ")
        if key: config["api_key"] = key
        
        if config.get("api_key"):
            print("\n\033[90mFetching available NVIDIA models...\033[0m")
            try:
                headers = {
                    "Authorization": f"Bearer {config['api_key']}",
                    "Accept": "application/json"
                }
                r = requests.get(f"{config['ext_url']}/models", headers=headers, timeout=10)
                r.raise_for_status()
                models_data = r.json().get("data", [])
                nvidia_models = sorted([m["id"] for m in models_data])
                
                if nvidia_models:
                    print("\n[ Available NVIDIA Models ]")
                    for i, m in enumerate(nvidia_models):
                        print(f"[{i+1}] {m}")
                        
                    idx_input = input(f"\nSelect model (Default 1): ") or "1"
                    try:
                        idx = int(idx_input) - 1
                        if idx < 0 or idx >= len(nvidia_models): idx = 0
                    except ValueError:
                        idx = 0
                    config["ext_model"] = nvidia_models[idx]
                else:
                    print(f"Current Model: {config.get('ext_model', 'meta/llama-3.1-70b-instruct')}")
                    model = input(f"Model Name (Press enter to keep current): ")
                    if model: config["ext_model"] = model
            except Exception as e:
                print(f"\n\033[91mFailed to fetch models: {e}\033[0m")
                print(f"Current Model: {config.get('ext_model', 'meta/llama-3.1-70b-instruct')}")
                model = input(f"Model Name (Press enter to keep current): ")
                if model: config["ext_model"] = model
        else:
            print(f"Current Model: {config.get('ext_model', 'meta/llama-3.1-70b-instruct')}")
            model = input(f"Model Name (Press enter to keep current): ")
            if model: config["ext_model"] = model
            
        host_url = config["ext_url"]
        selected_model = config["ext_model"]
        
    else:
        config["mode"] = "local"
        host = input(f"Ollama Host (Default: {config['host']}): ") or config["host"]
        if not host.startswith("http"):
            host = f"http://{host}"
        config["host"] = host
        
        print("\n[ Local Models Found ]")
        try:
            ms = requests.get(f"{config['host']}/api/tags", timeout=5).json().get('models', [])
            if not ms:
                print("\033[91mNo local models detected on host.\033[0m")
                ms = [{"name": config.get("ext_model", "qwen2.5-coder:latest")}]
        except Exception:
            print("\033[91mCould not connect to Ollama host. Using fallback listing.\033[0m")
            ms = [{"name": config.get("ext_model", "qwen2.5-coder:latest")}]
        
        for i, m in enumerate(ms):
            print(f"[{i+1}] {m['name']}")
            
        idx_input = input(f"\nSelect model (Default 1): ") or "1"
        try:
            idx = int(idx_input) - 1
            if idx < 0 or idx >= len(ms): idx = 0
        except ValueError:
            idx = 0
            
        config["ext_model"] = ms[idx]['name']
        host_url = config["host"]
        selected_model = config["ext_model"]
        
    with open(CONFIG_FILE, 'w') as f: 
        json.dump(config, f)
        
    print_rainbow_header()
    print(f"Engine: {selected_model} | Mode: AUTO | Host: {host_url}")
    return config

def main():
    config = get_config()
    try:
        if config["mode"] == "local":
            agent = LSGPTAgent(config['ext_model'], config['host'], config=config)
        else:
            agent = LSGPTAgent(config['ext_model'], config['ext_url'], config=config)
        agent.interactive_loop()
    except Exception as e: 
        print(f"Init Error: {e}")

if __name__ == "__main__": 
    main()
