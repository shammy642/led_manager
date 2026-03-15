import subprocess
from pathlib import Path
import pytest
from app.services.dnsmasq_manager import DnsmasqCommandError, DnsmasqManager, DnsmasqStatus
