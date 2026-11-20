"""Shared bounds: recording a trace has its own budget, separate from Run code."""
MAX_STEPS = 20_000
MAX_SOURCE_LINES = 10_000
MAX_SOURCE_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_TRACE_BYTES = 64 * 1024 * 1024
RUN_SECONDS = 60
VISUALIZE_SECONDS = 300
COMPILE_SECONDS = 60
WORKSPACE_BYTES = 256 * 1024 * 1024

def memory_limit_mib(mode='trusted-local'):
    """Local jobs use a portion of this device's RAM; containers keep their cap."""
    if mode!='trusted-local':return 768
    import os
    try:
        configured=os.getenv('SPANDY_MEMORY_MIB')
        if configured:return min(16384,max(128,int(configured)))
        import psutil
        return min(4096,max(512,int(psutil.virtual_memory().total//(4*1024*1024))))
    except (ValueError,OSError):return 768
