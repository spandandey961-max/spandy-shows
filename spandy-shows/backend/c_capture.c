#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <ctype.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif

static int spandy_interactive = 0;
static unsigned spandy_call = 0;

static void spandy_publish_marker(void) {
#ifdef _WIN32
    for (int attempt=0;attempt<50;++attempt) {
        if (MoveFileExA("input-call.tmp","input-call.txt",MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)) return;
        DWORD error=GetLastError();
        if (error!=ERROR_SHARING_VIOLATION && error!=ERROR_ACCESS_DENIED) break;
        Sleep(5);
    }
#else
    if (!rename("input-call.tmp","input-call.txt")) return;
#endif
    fprintf(stderr,"Spandy Shows could not publish the program input request.\n");
    _Exit(87);
}

static void spandy_begin(int line, const char *kind) {
    if (!spandy_interactive) return;
    FILE *marker = fopen("input-call.tmp", "w");
    if (!marker) { fprintf(stderr,"Spandy Shows could not create the program input request.\n"); _Exit(87); }
    fprintf(marker, "%u %d %s", ++spandy_call, line, kind); fclose(marker); spandy_publish_marker();
}
static void spandy_end(void) {
    if (!spandy_interactive) return;
#ifdef _WIN32
    for (int attempt=0;attempt<50;++attempt) {
        if (DeleteFileA("input-call.txt")) return;
        DWORD error=GetLastError();
        if (error==ERROR_FILE_NOT_FOUND) return;
        if (error!=ERROR_SHARING_VIOLATION && error!=ERROR_ACCESS_DENIED) break;
        Sleep(5);
    }
    fprintf(stderr,"Spandy Shows could not clear the program input request.\n");
    _Exit(87);
#else
    remove("input-call.txt");
#endif
}

static const char *spandy_kind(const char *format) {
    const char *kind = NULL;
    for (const char *p = format; *p; ++p) {
        if (*p != '%') continue;
        ++p; if (*p == '%' || !*p) continue;
        int suppressed = *p == '*'; if (suppressed) ++p;
        while (isdigit((unsigned char)*p)) ++p;
        while (*p && strchr("hljztL", *p)) ++p;
        if (!*p) break;
        if (suppressed || *p == 'n') continue;
        const char *next = strchr("diuoxX", *p) ? "integer" : strchr("aAeEfFgG", *p) ? "number" : *p == 'c' ? "character" : "text";
        if (kind && strcmp(kind, next)) return "text";
        kind = next;
    }
    return kind ? kind : "text";
}

__attribute__((constructor)) static void spandy_capture(void) {
    FILE *path_file = fopen("stdin-path.txt", "r");
    if (path_file) {
        char path[1024];
        if (fgets(path, sizeof(path), path_file)) { spandy_interactive = 1; freopen(path, "rb", stdin); setvbuf(stdin, NULL, _IONBF, 0); }
        fclose(path_file);
    } else freopen("stdin.txt", "r", stdin);
    freopen("stdout.txt", "w", stdout);
    freopen("stderr.txt", "w", stderr);
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
}

static void spandy_read_event(int line) {
    FILE *events = fopen("input-events.txt", "a");
    if (events) { fprintf(events, "%d\n", line); fclose(events); }
}

static void spandy_input_failed(int line) {
    FILE *failure = fopen("input-failure.txt", "w");
    if (failure) {
        fprintf(failure, "%d %s", line, feof(stdin) ? "input_required" : "input_invalid");
        fclose(failure);
    }
    /* Never continue into user code with failed/partially assigned input. */
    _Exit(86);
}

static int spandy_expected(const char *format) {
    int count = 0;
    for (const char *p = format; *p; ++p) {
        if (*p != '%') continue;
        ++p;
        if (!*p) break;
        if (*p == '%') continue;
        int suppressed = *p == '*';
        if (suppressed) ++p;
        while (isdigit((unsigned char)*p)) ++p;
        while (*p && (*p == 'h' || *p == 'l' || *p == 'j' || *p == 'z' || *p == 't' || *p == 'L')) ++p;
        if (!*p) break;
        if (!suppressed && *p != 'n') ++count;
        if (*p == '[') {
            ++p;
            if (*p == '^') ++p;
            if (*p == ']') ++p;
            while (*p && *p != ']') ++p;
            if (!*p) break;
        }
    }
    return count;
}

int spandy_scanf(int line, const char *format, ...) {
    va_list arguments;
    va_start(arguments, format);
    spandy_begin(line, spandy_kind(format));
    int assigned = vscanf(format, arguments);
    spandy_end();
    va_end(arguments);
    if (assigned < 0 || assigned < spandy_expected(format)) spandy_input_failed(line);
    spandy_read_event(line);
    return assigned;
}

int spandy_vscanf(int line, const char *format, va_list arguments) {
    spandy_begin(line, spandy_kind(format));
    int assigned = vscanf(format, arguments);
    spandy_end();
    if (assigned < 0 || assigned < spandy_expected(format)) spandy_input_failed(line);
    spandy_read_event(line);
    return assigned;
}

int spandy_vfscanf(int line, FILE *stream, const char *format, va_list arguments) {
    if (stream == stdin) spandy_begin(line, spandy_kind(format));
    int assigned = vfscanf(stream, format, arguments);
    if (stream == stdin) spandy_end();
    if (stream == stdin) {
        if (assigned < 0 || assigned < spandy_expected(format)) spandy_input_failed(line);
        spandy_read_event(line);
    }
    return assigned;
}

int spandy_fscanf(int line, FILE *stream, const char *format, ...) {
    va_list arguments;
    va_start(arguments, format);
    if (stream == stdin) spandy_begin(line, spandy_kind(format));
    int assigned = vfscanf(stream, format, arguments);
    if (stream == stdin) spandy_end();
    va_end(arguments);
    if (stream == stdin) {
        if (assigned < 0 || assigned < spandy_expected(format)) spandy_input_failed(line);
        spandy_read_event(line);
    }
    return assigned;
}

int spandy_fgetc(int line, FILE *stream) {
    if (stream == stdin) spandy_begin(line, "character");
    int value = fgetc(stream);
    if (stream == stdin) spandy_end();
    if (stream == stdin) {
        if (value == EOF) spandy_input_failed(line);
        spandy_read_event(line);
    }
    return value;
}

int spandy_getchar(int line) { return spandy_fgetc(line, stdin); }

char *spandy_fgets(int line, char *buffer, int size, FILE *stream) {
    if (stream == stdin) spandy_begin(line, "text");
    char *value = fgets(buffer, size, stream);
    if (stream == stdin) spandy_end();
    if (stream == stdin) {
        if (!value) spandy_input_failed(line);
        spandy_read_event(line);
    }
    return value;
}
