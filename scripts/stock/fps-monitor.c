/* Optional native SDL swap timing. Compile on the handheld; no game changes. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

/* Request one private screenshot by creating $ISAAC_CAPTURE_REQUEST.
 * This records the actual native framebuffer, which headless X11 cannot see. */
static void capture(void *window) {
    const char *request = getenv("ISAAC_CAPTURE_REQUEST");
    if (!request || access(request, F_OK)) return;
    unlink(request);
    void *sdl = dlopen("/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0.2800.5", RTLD_NOW | RTLD_LOCAL);
    void *gl = dlopen("/usr/lib/libmali.so.0", RTLD_NOW | RTLD_LOCAL);
    void (*size)(void *, int *, int *) = sdl ? dlsym(sdl, "SDL_GL_GetDrawableSize") : NULL;
    void (*readpixels)(int,int,int,int,unsigned,unsigned,void *) = gl ? dlsym(gl,"glReadPixels") : NULL;
    const char *path = getenv("ISAAC_CAPTURE_FILE");
    if (size && readpixels && path) {
        int w = 0, h = 0;
        size(window, &w, &h);
        if (w > 0 && h > 0 && w <= 4096 && h <= 4096) {
            unsigned char *rgba = calloc((size_t)w*h, 4);
            FILE *f = rgba ? fopen(path, "wb") : NULL;
            if (f) {
                readpixels(0, 0, w, h, 0x1908, 0x1401, rgba);
                fprintf(f, "P6\n%d %d\n255\n", w, h);
                for (int y=h-1; y>=0; y--)
                    for (int x=0; x<w; x++) fwrite(rgba+((size_t)y*w+x)*4, 1, 3, f);
                fclose(f);
            }
            free(rgba);
        }
    }
    if (sdl) dlclose(sdl);
    if (gl) dlclose(gl);
}

static double now(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}

void SDL_GL_SwapWindow(void *window) {
    static void (*swap)(void *);
    static FILE *out;
    static double start, previous, maximum;
    static unsigned count, over25, over50;
    if (!swap) {
        void *sdl = dlopen("/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0.2800.5", RTLD_NOW | RTLD_LOCAL);
        swap = sdl ? dlsym(sdl, "SDL_GL_SwapWindow") : NULL;
        if (!swap) { fprintf(stderr, "FPS monitor: SDL load failed\n"); abort(); }
        const char *path = getenv("ISAAC_FPS_FILE");
        if (path) out = fopen(path, "w");
        if (out) { fputs("monotonic_seconds,fps,max_frame_ms,frames_over_25ms,frames_over_50ms\n", out); fflush(out); }
    }
    capture(window);
    swap(window);
    double t = now();
    if (!previous) { start = previous = t; return; }
    double dt = t - previous;
    previous = t;
    count++;
    if (dt > maximum) maximum = dt;
    if (dt > .025) over25++;
    if (dt > .050) over50++;
    if (t - start >= 1.0) {
        if (out) {
            if (ftell(out) > 256*1024) {
                rewind(out);
                if (ftruncate(fileno(out), 0)) clearerr(out);
                fputs("monotonic_seconds,fps,max_frame_ms,frames_over_25ms,frames_over_50ms\n", out);
            }
            fprintf(out, "%.3f,%.2f,%.2f,%u,%u\n", t, count / (t-start), maximum*1000, over25, over50);
            fflush(out);
        }
        start = t; count = over25 = over50 = 0; maximum = 0;
    }
}
