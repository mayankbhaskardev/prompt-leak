"""Interactive injection shell — reverse shell for prompt injection."""
import asyncio
import json
import logging
import random
from datetime import datetime

logger = logging.getLogger("promptleak")


class InjectionShell:
    """Interactive shell for sending injected instructions to a target after successful injection."""

    def __init__(self, page, target, injection_payload: str = ""):
        self.page = page
        self.target = target
        self.injection_payload = injection_payload
        self.active = False
        self.history = []
        self.context = "injected"

    async def start(self):
        """Start the interactive shell."""
        self.active = True

        if self.injection_payload:
            print(f"[*] Establishing injection with: {self.injection_payload[:60]}...")
            response = await self._send(self.injection_payload)
            self.history.append({"cmd": self.injection_payload, "response": response, "timestamp": datetime.now().isoformat(), "type": "establish"})
            print(f"[+] Injection sent. Response: {response[:200]}...")

        self._print_banner()
        while self.active:
            try:
                cmd = await asyncio.get_event_loop().run_in_executor(None, input, "inject> ")
                cmd = cmd.strip()
                if not cmd:
                    continue
                if cmd.lower() in ("exit", "quit"):
                    await self._send("EXIT_ADMIN_MODE")
                    self.active = False
                    continue
                if cmd.lower() == "status":
                    self._print_status()
                    continue
                if cmd.lower() == "history":
                    self._print_history()
                    continue
                if cmd.lower().startswith("load "):
                    await self._load_file(cmd[5:])
                    continue
                if cmd.lower().startswith("export "):
                    self._export_history(cmd[7:])
                    continue
                if cmd.lower() == "help":
                    self._print_help()
                    continue

                response = await self._send(cmd)
                self.history.append({"cmd": cmd, "response": response, "timestamp": datetime.now().isoformat(), "type": "command"})
                print(f"\n{response}\n")

            except (KeyboardInterrupt, EOFError):
                print("\n[*] Use 'exit' to quit cleanly")
                break

        self.active = False
        print("\n[*] Shell closed.")

    async def _send(self, message: str) -> str:
        """Send a message to the target."""
        try:
            input_el = await self.page.query_selector(self.target.chat_input_selector)
            if not input_el:
                return "[Error: Cannot find input element]"
            await input_el.click()
            await input_el.fill("")
            for char in message:
                await self.page.keyboard.type(char, delay=random.randint(10, 30))
            if self.target.send_button_selector:
                btn = await self.page.query_selector(self.target.send_button_selector)
                if btn:
                    await btn.click()
            else:
                await self.page.keyboard.press("Enter")
            await asyncio.sleep(2)
            try:
                elements = await self.page.query_selector_all(self.target.response_selector)
                if elements:
                    texts = [await el.inner_text() for el in elements if el]
                    texts = [t for t in texts if t.strip()]
                    if texts:
                        return texts[-1]
            except Exception:
                pass
            return await self.page.evaluate("document.body.innerText") or ""
        except Exception as e:
            logger.debug(f"Shell send error: {e}")
            return f"[Error: {e}]"

    def _print_banner(self):
        print()
        print("Injection Shell v1.0")
        print("-" * 40)
        print(f"  Target: {self.target.name}")
        print(f"  Context: {self.context}")
        print(f"  Commands: {len(self.history)}")
        print("  Type 'help' for available commands")
        print("-" * 40)
        print()

    def _print_status(self):
        print()
        print("Shell Status")
        print("=" * 40)
        print(f"  Active:      {'YES' if self.active else 'NO'}")
        print(f"  Context:     {self.context}")
        print(f"  Target:      {self.target.name}")
        print(f"  Commands:    {len(self.history)}")
        print(f"  Last Cmd:    {self.history[-1]['cmd'][:50] if self.history else 'N/A'}")
        print("=" * 40)
        print()

    def _print_help(self):
        print()
        print("Available commands:")
        print("  <any text>       Send as injected instruction to target")
        print("  status           Show shell status")
        print("  history          Show command history")
        print("  load <file>      Send contents of a file as instruction")
        print("  export <file>    Export session history to JSON")
        print("  help             Show this help")
        print("  exit             Close shell")
        print()

    async def _load_file(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            print(f"[*] Sending {len(content)} chars from {path}...")
            response = await self._send(content)
            self.history.append({"cmd": f"[FILE:{path}]", "response": response, "timestamp": datetime.now().isoformat(), "type": "file"})
            print(f"\n{response}\n")
        except FileNotFoundError:
            print(f"[-] File not found: {path}")
        except Exception as e:
            print(f"[-] Error: {e}")

    def _export_history(self, path: str):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "target": self.target.name,
                    "injection_payload": self.injection_payload,
                    "started_at": self.history[0]["timestamp"] if self.history else None,
                    "commands": self.history,
                }, f, indent=2)
            print(f"[+] Session exported to {path}")
        except Exception as e:
            print(f"[-] Export error: {e}")

    def _print_history(self):
        print()
        print("Command History")
        print("=" * 60)
        for i, entry in enumerate(self.history, 1):
            ts = entry.get("timestamp", "")[11:19]
            cmd = entry["cmd"][:50]
            resp_len = len(entry.get("response", ""))
            print(f"  {i:3d}. [{ts}] {cmd:<50s} ({resp_len} chars)")
        print("=" * 60)
        print()
