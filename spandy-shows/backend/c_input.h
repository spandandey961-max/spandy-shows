#ifndef SPANDY_INPUT_H
#define SPANDY_INPUT_H
#include <stdio.h>
#include <stdarg.h>
int spandy_scanf(int line, const char *format, ...) __attribute__((format(scanf, 2, 3)));
int spandy_fscanf(int line, FILE *stream, const char *format, ...) __attribute__((format(scanf, 3, 4)));
int spandy_vscanf(int line, const char *format, va_list arguments);
int spandy_vfscanf(int line, FILE *stream, const char *format, va_list arguments);
int spandy_getchar(int line);
int spandy_fgetc(int line, FILE *stream);
char *spandy_fgets(int line, char *buffer, int size, FILE *stream);
/* Only the user translation unit includes these macros. The helper calls the
   real libc readers, so successful reads have their ordinary C semantics. */
#undef scanf
#undef fscanf
#undef vscanf
#undef vfscanf
#undef getchar
#undef fgetc
#undef getc
#undef fgets
#define scanf(...) spandy_scanf(__LINE__, __VA_ARGS__)
#define fscanf(...) spandy_fscanf(__LINE__, __VA_ARGS__)
#define vscanf(...) spandy_vscanf(__LINE__, __VA_ARGS__)
#define vfscanf(...) spandy_vfscanf(__LINE__, __VA_ARGS__)
#define getchar() spandy_getchar(__LINE__)
#define fgetc(stream) spandy_fgetc(__LINE__, stream)
#define getc(stream) spandy_fgetc(__LINE__, stream)
#define fgets(...) spandy_fgets(__LINE__, __VA_ARGS__)
#endif
