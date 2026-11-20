#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wchar.h>
#include <stdio.h>

#ifdef SPANDY_STOP
#define ACTION L"--stop"
#else
#define ACTION L"--start"
#endif

/* Start the included runtime directly; no shell, installer or PATH lookup. */
int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, LPWSTR arguments, int show) {
    wchar_t root[32768], python[32768], script[32768], command[32768];
    DWORD length = GetModuleFileNameW(NULL, root, 32768);
    if (!length || length >= 32768) return 1;
    wchar_t *slash = wcsrchr(root, L'\\');
    if (!slash) return 1;
    *slash = 0;
    if (wcslen(root) + wcslen(arguments) + 160 >= 32768) return 1;
    swprintf(python, 32768, L"%ls\\runtime\\python\\pythonw.exe", root);
    swprintf(script, 32768, L"%ls\\launcher.py", root);
    if (GetFileAttributesW(python) == INVALID_FILE_ATTRIBUTES || GetFileAttributesW(script) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL, L"Extract the entire ZIP first, then open Start Spandy Shows.exe from the extracted folder.", L"Spandy Shows", MB_OK | MB_ICONINFORMATION);
        return 1;
    }
    swprintf(command, 32768, L"\"%ls\" -I \"%ls\" %ls %ls", python, script, ACTION, arguments);
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESHOWWINDOW;
    startup.wShowWindow = SW_HIDE;
    if (!CreateProcessW(python, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, root, &startup, &process)) {
        MessageBoxW(NULL, L"Windows could not start the included runtime. Re-extract the complete package into a writable folder and try again.", L"Spandy Shows", MB_OK | MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
