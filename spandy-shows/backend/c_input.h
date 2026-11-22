#ifndef SPANDY_INPUT_H
#define SPANDY_INPUT_H
#include <stdio.h>
#include <stdarg.h>
#include <sys/types.h>
int spandy_scanf(int line, const char *format, ...) __attribute__((format(scanf, 2, 3)));
int spandy_fscanf(int line, FILE *stream, const char *format, ...) __attribute__((format(scanf, 3, 4)));
int spandy_vscanf(int line, const char *format, va_list arguments);
int spandy_vfscanf(int line, FILE *stream, const char *format, va_list arguments);
int spandy_getchar(int line);
int spandy_fgetc(int line, FILE *stream);
char *spandy_fgets(int line, char *buffer, int size, FILE *stream);
size_t spandy_fread(int line, void *buffer, size_t size, size_t count, FILE *stream);
ssize_t spandy_getline(int line, char **buffer, size_t *size, FILE *stream);
#ifdef _WIN32
int spandy_read(int line, int descriptor, void *buffer, unsigned int count);
#else
ssize_t spandy_read(int line, int descriptor, void *buffer, size_t count);
#endif
void *spandy_malloc(size_t size);
void *spandy_calloc(size_t count, size_t size);
void *spandy_realloc(void *pointer, size_t size);
void spandy_free(void *pointer);
char *spandy_strdup(const char *text);
char *spandy_strndup(const char *text, size_t limit);
#endif
