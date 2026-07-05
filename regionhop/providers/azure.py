"""Azure provider: create/start/stop a VM via the Azure CLI (``az``).

regionhop shells out to ``az`` so it inherits your existing ``az login`` session
and needs no Python SDK. Requires the Azure CLI to be installed.
"""

from __future__ import annotations

import shutil
import subprocess

from .base import Provider, ProviderError, VMInfo


class AzureProvider(Provider):
    name = "azure"

    def __init__(
        self,
        resource_group: str,
        name: str,
        location: str,
        user: str = "azureuser",
        size: str = "Standard_B1s",
        image: str = "Ubuntu2204",
        ssh_public_key_path: str | None = None,
        key_path: str | None = None,
        password: str | None = None,
    ):
        if not (resource_group and name and location):
            raise ProviderError(
                "The 'azure' provider requires 'resource_group', 'name', and 'location'."
            )
        self.rg = resource_group
        self.vm = name
        self.location = location
        self.user = user
        self.size = size
        self.image = image
        self.pub = ssh_public_key_path
        self.key_path = key_path
        self.password = password

    @classmethod
    def from_options(cls, options: dict) -> AzureProvider:
        return cls(
            resource_group=options.get("resource_group", ""),
            name=options.get("name", ""),
            location=options.get("location", ""),
            user=options.get("user", "azureuser"),
            size=options.get("size", "Standard_B1s"),
            image=options.get("image", "Ubuntu2204"),
            ssh_public_key_path=options.get("ssh_public_key_path"),
            key_path=options.get("key_path"),
            password=options.get("password"),
        )

    def _az(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        if not shutil.which("az"):
            raise ProviderError("Azure CLI 'az' not found. Install it and run 'az login'.")
        result = subprocess.run(["az", *args], capture_output=True, text=True, check=False)
        if check and result.returncode != 0:
            raise ProviderError(f"`az {' '.join(args)}` failed:\n{result.stderr.strip()}")
        return result

    def _exists(self) -> bool:
        return self._az("vm", "show", "-g", self.rg, "-n", self.vm, check=False).returncode == 0

    def _public_ip(self) -> str | None:
        result = self._az(
            "vm", "show", "-d", "-g", self.rg, "-n", self.vm, "--query", "publicIps", "-o", "tsv"
        )
        return result.stdout.strip() or None

    def ensure_running(self) -> VMInfo:
        if not self._exists():
            print(f"[azure] Creating {self.vm} in {self.location} ...")
            self._az("group", "create", "-n", self.rg, "-l", self.location)
            args = [
                "vm", "create", "-g", self.rg, "-n", self.vm, "-l", self.location,
                "--image", self.image, "--size", self.size,
                "--admin-username", self.user, "--public-ip-sku", "Standard",
            ]
            args += ["--ssh-key-values", self.pub] if self.pub else ["--generate-ssh-keys"]
            self._az(*args)
        else:
            # Start it in case it was deallocated (no-op if already running).
            self._az("vm", "start", "-g", self.rg, "-n", self.vm, check=False)

        ip = self._public_ip()
        if not ip:
            raise ProviderError("Could not determine the VM's public IP.")
        return VMInfo(ip, self.user, self.key_path, self.password)

    def deallocate(self) -> None:
        self._az("vm", "deallocate", "-g", self.rg, "-n", self.vm)
        print(f"[azure] Deallocated {self.vm} -- compute billing stopped.")

    def destroy(self) -> None:
        self._az("vm", "delete", "-g", self.rg, "-n", self.vm, "--yes")
        print(f"[azure] Deleted {self.vm}.")

    def status(self) -> str:
        result = self._az(
            "vm", "get-instance-view", "-g", self.rg, "-n", self.vm,
            "--query",
            "instanceView.statuses[?starts_with(code, 'PowerState')].displayStatus",
            "-o", "tsv",
            check=False,
        )
        if result.returncode != 0:
            return "not created"
        return result.stdout.strip() or "unknown"
