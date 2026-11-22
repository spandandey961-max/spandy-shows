#include "spandy_input.h"
#include <stdarg.h>
#include <stdlib.h>
#include <ctype.h>
#include <string.h>
#include <stdint.h>
#include <stdatomic.h>
#include <errno.h>
#include <unistd.h>
#ifdef _WIN32
#include <windows.h>
#endif

static int spandy_interactive = 0;
static unsigned spandy_call = 0;
static atomic_flag input_lock = ATOMIC_FLAG_INIT;

static void spandy_acquire(atomic_flag *lock) {
    while (atomic_flag_test_and_set(lock)) {
#ifdef _WIN32
        Sleep(1);
#else
        usleep(1000);
#endif
    }
}

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
    spandy_acquire(&input_lock);
    FILE *marker = fopen("input-call.tmp", "w");
    if (!marker) { fprintf(stderr,"Spandy Shows could not create the program input request.\n"); _Exit(87); }
    fprintf(marker, "%u %d %s", ++spandy_call, line, kind); fclose(marker); spandy_publish_marker();
}
static void spandy_end(void) {
    if (!spandy_interactive) return;
#ifdef _WIN32
    for (int attempt=0;attempt<50;++attempt) {
        if (DeleteFileA("input-call.txt")) { atomic_flag_clear(&input_lock); return; }
        DWORD error=GetLastError();
        if (error==ERROR_FILE_NOT_FOUND) { atomic_flag_clear(&input_lock); return; }
        if (error!=ERROR_SHARING_VIOLATION && error!=ERROR_ACCESS_DENIED) break;
        Sleep(5);
    }
    fprintf(stderr,"Spandy Shows could not clear the program input request.\n");
    _Exit(87);
#else
    remove("input-call.txt");
    atomic_flag_clear(&input_lock);
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
        const char conversion = *p;
        if (conversion == '[') {
            ++p;
            if (*p == '^') ++p;
            if (*p == ']') ++p;
            while (*p && *p != ']') ++p;
            if (!*p) break;
        }
        if (suppressed || conversion == 'n') continue;
        const char *next = strchr("diuoxX", conversion) ? "integer" : strchr("aAeEfFgG", conversion) ? "number" : conversion == 'c' ? "character" : "text";
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
    if (assigned >= 0 && assigned == spandy_expected(format)) spandy_read_event(line);
    return assigned;
}

int spandy_vscanf(int line, const char *format, va_list arguments) {
    spandy_begin(line, spandy_kind(format));
    int assigned = vscanf(format, arguments);
    spandy_end();
    if (assigned >= 0 && assigned == spandy_expected(format)) spandy_read_event(line);
    return assigned;
}

int spandy_vfscanf(int line, FILE *stream, const char *format, va_list arguments) {
    if (stream == stdin) spandy_begin(line, spandy_kind(format));
    int assigned = vfscanf(stream, format, arguments);
    if (stream == stdin) spandy_end();
    if (stream == stdin && assigned >= 0 && assigned == spandy_expected(format)) spandy_read_event(line);
    return assigned;
}

int spandy_fscanf(int line, FILE *stream, const char *format, ...) {
    va_list arguments;
    va_start(arguments, format);
    if (stream == stdin) spandy_begin(line, spandy_kind(format));
    int assigned = vfscanf(stream, format, arguments);
    if (stream == stdin) spandy_end();
    va_end(arguments);
    if (stream == stdin && assigned >= 0 && assigned == spandy_expected(format)) spandy_read_event(line);
    return assigned;
}

int spandy_fgetc(int line, FILE *stream) {
    if (stream == stdin) spandy_begin(line, "character");
    int value = fgetc(stream);
    if (stream == stdin) spandy_end();
    if (stream == stdin && value != EOF) spandy_read_event(line);
    return value;
}

int spandy_getchar(int line) { return spandy_fgetc(line, stdin); }

char *spandy_fgets(int line, char *buffer, int size, FILE *stream) {
    if (stream == stdin) spandy_begin(line, "text");
    char *value = fgets(buffer, size, stream);
    if (stream == stdin) spandy_end();
    if (stream == stdin && value) spandy_read_event(line);
    return value;
}

size_t spandy_fread(int line, void *buffer, size_t size, size_t count, FILE *stream) {
    if (stream == stdin) spandy_begin(line, "text");
    size_t read = fread(buffer, size, count, stream);
    if (stream == stdin) spandy_end();
    return read;
}

/* A bounded registry read by GDB. Allocation identity changes on address reuse. */
struct SpandyAllocation { uintptr_t address; size_t size; unsigned long long generation; int live; };
struct SpandyAllocation spandy_heap[512];
unsigned spandy_heap_used;
unsigned long long spandy_heap_epoch;
static atomic_flag heap_lock = ATOMIC_FLAG_INIT;

static void spandy_allocated(void *pointer, size_t size) {
    if (!pointer || !size) return;
    spandy_acquire(&heap_lock);
    unsigned slot = spandy_heap_used;
    for (unsigned i = 0; i < spandy_heap_used; ++i) {
        if (!spandy_heap[i].live) slot = i;
        if (spandy_heap[i].address == (uintptr_t)pointer) {
            if (spandy_heap[i].live && spandy_heap[i].size == size) {
                atomic_flag_clear(&heap_lock);
                return;
            }
            slot = i;
            break;
        }
    }
    if (slot >= sizeof spandy_heap / sizeof spandy_heap[0]) { atomic_flag_clear(&heap_lock); return; }
    if (slot == spandy_heap_used) ++spandy_heap_used;
    spandy_heap[slot] = (struct SpandyAllocation){(uintptr_t)pointer, size, ++spandy_heap_epoch, 1};
    atomic_flag_clear(&heap_lock);
}

static void spandy_released(uintptr_t address) {
    spandy_acquire(&heap_lock);
    for (unsigned i = 0; i < spandy_heap_used; ++i) {
        if (spandy_heap[i].address == address && spandy_heap[i].live) {
            spandy_heap[i].live = 0;
            ++spandy_heap_epoch;
            break;
        }
    }
    atomic_flag_clear(&heap_lock);
}

void *spandy_malloc(size_t size) {
    void *pointer = malloc(size);
    spandy_allocated(pointer, size);
    return pointer;
}
void *spandy_calloc(size_t count, size_t size) {
    void *pointer = calloc(count, size);
    if (size && count <= SIZE_MAX / size) spandy_allocated(pointer, count * size);
    return pointer;
}
void *spandy_realloc(void *pointer, size_t size) {
    uintptr_t address = (uintptr_t)pointer;
    void *updated = realloc(pointer, size);
    if (updated || !size) spandy_released(address);
    spandy_allocated(updated, size);
    return updated;
}
void spandy_free(void *pointer) {
    spandy_released((uintptr_t)pointer);
    free(pointer);
}
char *spandy_strndup(const char *text, size_t limit) {
    size_t length = strnlen(text, limit);
    if (length == SIZE_MAX) return NULL;
    char *result = spandy_malloc(length + 1);
    if (result) { memcpy(result, text, length); result[length] = '\0'; }
    return result;
}
char *spandy_strdup(const char *text) { return spandy_strndup(text, SIZE_MAX); }

ssize_t spandy_getline(int line, char **buffer, size_t *size, FILE *stream) {
    if (stream == stdin) spandy_begin(line, "text");
#ifdef _WIN32
    ssize_t read = -1;
    if (!buffer || !size) { errno = EINVAL; goto done; }
    size_t length = 0;
    for (int character; (character = fgetc(stream)) != EOF;) {
        if (!*buffer || length + 1 >= *size) {
            if (*size >= SIZE_MAX / 2) { errno = ENOMEM; goto done; }
            size_t capacity = *buffer && *size >= 64 ? *size * 2 : 64;
            char *updated = spandy_realloc(*buffer, capacity);
            if (!updated) goto done;
            *buffer = updated;
            *size = capacity;
        }
        (*buffer)[length++] = (char)character;
        (*buffer)[length] = '\0';
        if (character == '\n') break;
    }
    if (length) read = (ssize_t)length;
done:
#else
    uintptr_t prior = buffer && size && stream ? (uintptr_t)*buffer : 0;
    ssize_t read = getline(buffer, size, stream);
    int read_errno = errno;
    if (buffer && size && stream) {
        if (*buffer && prior != (uintptr_t)*buffer) spandy_released(prior);
        spandy_allocated(*buffer, *size);
    }
#endif
    if (stream == stdin) spandy_end();
#ifndef _WIN32
    errno = read_errno;
#endif
    return read;
}

#ifdef _WIN32
int spandy_read(int line, int descriptor, void *buffer, unsigned int count) {
    if (descriptor == 0) spandy_begin(line, "text");
    int received = _read(descriptor, buffer, count);
#else
ssize_t spandy_read(int line, int descriptor, void *buffer, size_t count) {
    if (descriptor == 0) spandy_begin(line, "text");
    ssize_t received = read(descriptor, buffer, count);
#endif
    if (descriptor == 0) spandy_end();
    return received;
}
