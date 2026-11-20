from types import SimpleNamespace
import psutil
from backend import runner,limits


def test_shared_working_sets_do_not_trigger_a_false_private_memory_limit(monkeypatch):
    class Process:
        def __init__(self,pid,private):self.pid=pid;self.private=private
        def children(self,recursive=False):return [child,child]
        def memory_info(self):return SimpleNamespace(rss=600*1024*1024)
        def memory_full_info(self):return SimpleNamespace(rss=600*1024*1024,uss=self.private)
    child=Process(2,30*1024*1024);root=Process(1,20*1024*1024)
    monkeypatch.setattr(runner.psutil,'Process',lambda pid:root)
    assert runner.process_tree_memory_bytes(1)==50*1024*1024


def test_windows_private_commit_is_available_when_unique_resident_query_is_denied(monkeypatch):
    class Process:
        pid=1
        def children(self,recursive=False):return []
        def memory_full_info(self):raise psutil.AccessDenied(1)
        def memory_info(self):return SimpleNamespace(rss=900*1024*1024,private=40*1024*1024)
    monkeypatch.setattr(runner.psutil,'Process',lambda pid:Process())
    assert runner.process_tree_memory_bytes(1)==40*1024*1024


def test_local_budget_uses_device_ram_and_container_limit_stays_explicit(monkeypatch):
    monkeypatch.delenv('SPANDY_MEMORY_MIB',raising=False)
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(total=8*1024**3))
    assert limits.memory_limit_mib('trusted-local')==2048
    assert limits.memory_limit_mib('docker')==768
    monkeypatch.setenv('SPANDY_MEMORY_MIB','1024')
    assert limits.memory_limit_mib('trusted-local')==1024
