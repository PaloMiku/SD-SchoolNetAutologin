"""
Campus Network Auto-Login Plugin for Decky
Automatically logs in to campus network (DrCom) when internet connectivity is lost.
"""

import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

import decky


class Plugin:
    """Main plugin class for campus network auto-login."""

    # Configuration constants
    DEFAULT_LOGIN_IP = "221.1.64.43"
    DEFAULT_PING_TARGET = "8.8.8.8"
    DEFAULT_CONFIG_FILE = "config.json"
    HTTP_TIMEOUT = 10
    USER_AGENT = "Mozilla/5.0"

    def __init__(self):
        """Initialize the plugin."""
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._monitor_task: Optional[asyncio.Task[Any]] = None

    # ============= Lifecycle Methods =============

    async def _main(self) -> None:
        """Called when plugin loads. Initialize event loop and log startup."""
        self.loop = asyncio.get_event_loop()
        decky.logger.info("Campus Network Auto-Login plugin loaded")

    async def _unload(self) -> None:
        """Called when plugin unloads. Stop monitoring and cleanup."""
        decky.logger.info("Plugin unloading")
        if self._monitor_task and not self._monitor_task.done():
            try:
                self._monitor_task.cancel()
            except Exception as e:
                decky.logger.error(f"Error stopping monitor: {e}")

    async def _uninstall(self) -> None:
        """Called when plugin is uninstalled."""
        decky.logger.info("Plugin uninstalled")

    async def _migration(self) -> None:
        """Migrate settings from previous plugin versions."""
        decky.logger.info("Running migrations")
        decky.migrate_logs(
            os.path.join(
                decky.DECKY_USER_HOME, ".config", "decky-template", "template.log"
            )
        )
        decky.migrate_settings(
            os.path.join(decky.DECKY_HOME, "settings", "template.json"),
            os.path.join(decky.DECKY_USER_HOME, ".config", "decky-template"),
        )
        decky.migrate_runtime(
            os.path.join(decky.DECKY_HOME, "template"),
            os.path.join(
                decky.DECKY_USER_HOME, ".local", "share", "decky-template"
            ),
        )

    # ============= Configuration Methods =============

    def _config_dir(self) -> str:
        """Get the plugin-specific configuration directory."""
        plugin_dir = os.path.join(decky.DECKY_PLUGIN_SETTINGS_DIR, "schoolnet-autologin")
        os.makedirs(plugin_dir, exist_ok=True)
        return plugin_dir

    def _config_path(self) -> str:
        """Get the path to the configuration file."""
        return os.path.join(self._config_dir(), "config.json")

    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "login_ip": self.DEFAULT_LOGIN_IP,
            "use_https": False,
            "login_path": "/drcom/login",
            "method": "GET",
            "params": {
                "callback": "dr1003",
                "DDDDD": "",
                "upass": "",
                "0MKKey": "123456",
                "R1": "0",
                "R2": "",
                "R3": "1",
                "R6": "0",
                "para": "00",
                "v6ip": "",
                "terminal_type": "1",
                "lang": "zh-cn",
                "jsVersion": "4.2.1",
            },
            "ping_target": self.DEFAULT_PING_TARGET,
            "ping_interval_sec": 60,
            "ping_timeout_sec": 2,
            "consecutive_failures_threshold": 3,
            "backoff_attempt_sec": 60,
            "success_check_string": "",
        }

    async def get_config(self) -> Dict[str, Any]:
        """Read and return configuration, creating defaults if missing."""
        try:
            path = self._config_path()
            if not os.path.exists(path):
                cfg = self._default_config()
                with open(path, "w") as f:
                    json.dump(cfg, f, indent=2)
                decky.logger.info("Created default configuration at: %s", path)
                return cfg

            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            decky.logger.error(f"Failed to load config: {e}")
            return self._default_config()

    async def save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file."""
        try:
            path = self._config_path()
            with open(path, "w") as f:
                json.dump(config, f, indent=2)
            decky.logger.info("Configuration saved successfully")
        except Exception as e:
            decky.logger.error(f"Failed to save config: {e}")

    async def reset_config(self) -> Dict[str, Any]:
        """Reset configuration to defaults and save to file."""
        try:
            path = self._config_path()
            if os.path.exists(path):
                os.remove(path)
                decky.logger.info("Old configuration file deleted")
            
            cfg = self._default_config()
            # Save the default config to file
            with open(path, "w") as f:
                json.dump(cfg, f, indent=2)
            decky.logger.info("Configuration reset to defaults and saved")
            return cfg
        except Exception as e:
            decky.logger.error(f"Failed to reset config: {e}")
            return self._default_config()

    # ============= Network Methods =============

    async def _run_ping(self, host: str, timeout: int) -> Dict[str, Any]:
        """Run a single ping request and return results."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping",
                "-c",
                "1",
                "-W",
                str(timeout),
                host,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            rc = await asyncio.wait_for(proc.wait(), timeout=timeout + 1)
            return {"host": host, "success": rc == 0, "rc": rc}
        except asyncio.TimeoutError:
            decky.logger.warning(f"Ping timeout for {host}")
            return {"host": host, "success": False, "rc": -1, "error": "timeout"}
        except Exception as e:
            decky.logger.error(f"Ping failed for {host}: {e}")
            return {"host": host, "success": False, "rc": -1, "error": str(e)}

    async def test_ping(self) -> Dict[str, Any]:
        """Test ping connectivity."""
        cfg = await self.get_config()
        host = str(cfg.get("ping_target") or self.DEFAULT_PING_TARGET)
        timeout = int(cfg.get("ping_timeout_sec", 2) or 2)

        result = await self._run_ping(host, timeout)
        await decky.emit(
            "ping_status",
            result.get("host"),
            result.get("success"),
            0,
            int(time.time()),
        )
        return result

    # ============= Login Methods =============

    def _build_login_url(self, config: Dict[str, Any]) -> str:
        """Build the complete login URL from configuration."""
        protocol = "https" if config.get("use_https") else "http"
        login_ip = config.get("login_ip", self.DEFAULT_LOGIN_IP)
        login_path = config.get("login_path", "/drcom/login")
        return f"{protocol}://{login_ip}{login_path}"

    def _make_http_request(
        self,
        method: str,
        url: str,
        params: Dict[str, str],
    ) -> Dict[str, Any]:
        """Make HTTP request to login server."""
        try:
            if method == "GET":
                query = urllib.parse.urlencode(params)
                full_url = url + "?" + query
                decky.logger.info(f"GET {full_url[:150]}...")

                req = urllib.request.Request(full_url, method="GET")
                req.add_header("User-Agent", self.USER_AGENT)

                with urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT) as res:
                    body = res.read().decode(errors="ignore")
                    status = res.getcode()
                    decky.logger.info(f"Response: {status}, size: {len(body)} bytes")
                    return {"status": status, "body": body}

            else:  # POST
                decky.logger.info(f"POST {url}")
                data = urllib.parse.urlencode(params).encode()
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
                req.add_header("User-Agent", self.USER_AGENT)

                with urllib.request.urlopen(req, timeout=self.HTTP_TIMEOUT) as res:
                    body = res.read().decode(errors="ignore")
                    status = res.getcode()
                    decky.logger.info(f"Response: {status}, size: {len(body)} bytes")
                    return {"status": status, "body": body}

        except urllib.error.HTTPError as e:
            decky.logger.error(f"HTTP Error {e.code}: {e.reason}")
            return {"status": e.code, "body": "", "error": f"HTTP {e.code}"}
        except urllib.error.URLError as e:
            decky.logger.error(f"URL Error: {e.reason}")
            return {"status": -1, "body": "", "error": str(e.reason)}
        except Exception as e:
            decky.logger.error(f"Request failed: {type(e).__name__}: {e}")
            return {"status": -1, "body": "", "error": str(e)}

    async def do_login(self) -> Dict[str, Any]:
        """Perform campus network login."""
        cfg = await self.get_config()

        # Validate required credentials
        if not cfg.get("params", {}).get("DDDDD"):
            decky.logger.warning("Login skipped: Student ID (DDDDD) not configured")
            return {
                "success": False,
                "status": -1,
                "error": "Student ID not configured",
            }

        if not cfg.get("params", {}).get("upass"):
            decky.logger.warning("Login skipped: Password (upass) not configured")
            return {"success": False, "status": -1, "error": "Password not configured"}

        # Build login request
        url = self._build_login_url(cfg)
        method = cfg.get("method", "GET").upper()
        params = cfg.get("params", {}).copy()
        success_check = cfg.get("success_check_string", "")

        # Add timestamp parameter
        params["v"] = str(int(time.time() * 1000) % 10000)

        decky.logger.info(
            f"Login attempt: {method} {url} with {len(params)} parameters"
        )

        # Run blocking HTTP request in thread pool
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(
            None, self._make_http_request, method, url, params
        )

        status = res.get("status", -1)
        body = res.get("body", "") or ""
        error = res.get("error")

        # Determine success based on response
        success = False
        if status == 200:
            if success_check:
                success = success_check in body
            else:
                success = True

        # Emit login status event
        message = error or (body[:256] if body else "")
        await decky.emit("login_status", success, status, message, int(time.time()))

        decky.logger.info(
            f"Login {'succeeded' if success else 'failed'}: status={status}"
        )

        return {
            "success": success,
            "status": status,
            "body": body[:1024],
            "error": error,
        }

    # ============= Monitor Methods =============

    async def start_ping_monitor(self) -> None:
        """Start the background ping monitor task."""
        if (
            self._monitor_task
            and isinstance(self._monitor_task, asyncio.Task)
            and not self._monitor_task.done()
        ):
            decky.logger.warning("Monitor already running")
            return

        if not self.loop:
            self.loop = asyncio.get_event_loop()

        self._monitor_task = self.loop.create_task(self._ping_monitor())
        decky.logger.info("Ping monitor started")

    async def stop_ping_monitor(self) -> None:
        """Stop the background ping monitor task."""
        if self._monitor_task and isinstance(self._monitor_task, asyncio.Task):
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
            decky.logger.info("Ping monitor stopped")

    async def is_monitor_running(self) -> bool:
        """Check if ping monitor is currently running."""
        return bool(
            self._monitor_task
            and isinstance(self._monitor_task, asyncio.Task)
            and not self._monitor_task.done()
        )

    async def _ping_monitor(self) -> None:
        """Background task that monitors network and triggers login when needed."""
        consecutive_failures = 0
        decky.logger.info("Ping monitor task started")

        try:
            while True:
                cfg = await self.get_config()

                host = cfg.get("ping_target") or self.DEFAULT_PING_TARGET
                interval = int(cfg.get("ping_interval_sec", 60) or 60)
                timeout = int(cfg.get("ping_timeout_sec", 2) or 2)
                threshold = int(cfg.get("consecutive_failures_threshold", 3) or 3)
                backoff = int(cfg.get("backoff_attempt_sec", 60) or 60)

                # Run ping
                result = await self._run_ping(host, timeout)
                success = result.get("success", False)

                if success:
                    if consecutive_failures > 0:
                        consecutive_failures = 0
                        decky.logger.info("Network connectivity restored")
                    await decky.emit(
                        "ping_status",
                        host,
                        True,
                        consecutive_failures,
                        int(time.time()),
                    )
                else:
                    consecutive_failures += 1
                    await decky.emit(
                        "ping_status",
                        host,
                        False,
                        consecutive_failures,
                        int(time.time()),
                    )
                    decky.logger.warning(
                        f"Ping failure {consecutive_failures}/{threshold}"
                    )

                    # Trigger login if threshold reached
                    if consecutive_failures >= threshold:
                        decky.logger.warning("Failure threshold reached, attempting login")
                        await self.do_login()
                        consecutive_failures = 0
                        await asyncio.sleep(backoff)

                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            decky.logger.info("Ping monitor cancelled")
        except Exception as e:
            decky.logger.error(f"Ping monitor error: {e}")
            await asyncio.sleep(5)  # Prevent tight loop on errors
