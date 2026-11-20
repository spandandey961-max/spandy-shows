"""Give the bundled native EXE the supplied logo and Spandy Shows file metadata."""
import ctypes,struct
from pathlib import Path

def padded(data):return data+b'\0'*((-len(data))%4)
def block(key,value=b'',children=b'',kind=1,length=None):
    header=padded(struct.pack('<HHH',0,len(value)//2 if kind==1 else len(value) if length is None else length,kind)+(key+'\0').encode('utf-16le'))
    data=header+padded(value)+children
    return struct.pack('<H',len(data))+data[2:]
def version():
    fixed=struct.pack('<13I',0xFEEF04BD,0x10000,0x10002,0,0x10002,0,0x3F,0,0x40004,1,0,0,0)
    strings={'CompanyName':'Spandy Shows','FileDescription':'Spandy Shows','ProductName':'Spandy Shows','FileVersion':'1.2.0','ProductVersion':'1.2.0','OriginalFilename':'Spandy Shows.exe','InternalName':'Spandy Shows'}
    table=block('040904B0',children=b''.join(block(k,(v+'\0').encode('utf-16le')) for k,v in strings.items()))
    var=block('VarFileInfo',children=block('Translation',struct.pack('<HH',0x409,1200),kind=0))
    return block('VS_VERSION_INFO',fixed,block('StringFileInfo',children=table)+var,kind=0)

def brand(executable:Path,icon:Path):
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.BeginUpdateResourceW.argtypes=[ctypes.c_wchar_p,ctypes.c_bool];api.BeginUpdateResourceW.restype=ctypes.c_void_p
    api.UpdateResourceW.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ushort,ctypes.c_void_p,ctypes.c_uint32]
    api.EndUpdateResourceW.argtypes=[ctypes.c_void_p,ctypes.c_bool]
    handle=api.BeginUpdateResourceW(str(executable),False)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    data=icon.read_bytes();_,kind,count=struct.unpack_from('<HHH',data)
    assert kind==1
    group=struct.pack('<HHH',0,1,count)
    def put(kind,name,payload):
        buffer=ctypes.create_string_buffer(payload)
        if not api.UpdateResourceW(handle,kind,name,0x409,buffer,len(payload)):raise ctypes.WinError(ctypes.get_last_error())
    try:
        for index in range(count):
            width,height,colors,reserved,planes,bits,size,offset=struct.unpack_from('<BBBBHHII',data,6+index*16)
            put(3,index+1,data[offset:offset+size])
            group+=struct.pack('<BBBBHHIH',width,height,colors,reserved,planes,bits,size,index+1)
        # Electron's main application icon uses resource group 1.
        put(14,1,group);put(16,1,version())
    except Exception:
        api.EndUpdateResourceW(handle,True);raise
    if not api.EndUpdateResourceW(handle,False):raise ctypes.WinError(ctypes.get_last_error())
