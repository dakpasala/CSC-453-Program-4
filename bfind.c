/*
 * bfind - Breadth-first find
 *
 * A BFS version of the UNIX find utility using POSIX system calls.
 *
 * Usage: ./bfind [-L] [-xdev] [path...] [filters...]
 *
 * Filters:
 *   -name PATTERN   Glob match on filename (fnmatch)
 *   -type TYPE      f (file), d (directory), l (symlink)
 *   -mtime N        Modified within the last N days
 *   -size SPEC      File size: [+|-]N[c|k|M]
 *   -perm MODE      Exact octal permission match
 *
 * Options:
 *   -L              Follow symbolic links (default: no)
 *   -xdev           Do not cross filesystem boundaries
 */

#define _POSIX_C_SOURCE 200809L

#include <dirent.h>
#include <errno.h>
#include <fnmatch.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#include "queue.h"

/* ------------------------------------------------------------------ */
/*  Filter definitions                                                 */
/* ------------------------------------------------------------------ */

typedef enum {
    FILTER_NAME,
    FILTER_TYPE,
    FILTER_MTIME,
    FILTER_SIZE,
    FILTER_PERM
} filter_kind_t;

typedef enum {
    SIZE_CMP_EXACT,
    SIZE_CMP_GREATER,
    SIZE_CMP_LESS
} size_cmp_t;

typedef struct {
    filter_kind_t kind;
    union {
        char *pattern;       /* -name */
        char type_char;      /* -type: 'f', 'd', or 'l' */
        int mtime_days;      /* -mtime */
        struct {
            off_t size_bytes;
            size_cmp_t size_cmp;
        } size;              /* -size */
        mode_t perm_mode;    /* -perm */
    } filter;
} filter_t;

/* ------------------------------------------------------------------ */
/*  Cycle detection                                                    */
/*                                                                     */
/*  A file's true on-disk identity is its (st_dev, st_ino) pair.       */
/*  You will need this for cycle detection when -L is set.             */
/* ------------------------------------------------------------------ */

typedef struct {
    dev_t dev;
    ino_t ino;
} dev_ino_t;

/* ------------------------------------------------------------------ */
/*  Global configuration                                               */
/* ------------------------------------------------------------------ */

static filter_t *g_filters = NULL;
static int g_nfilters = 0;
static bool g_follow_links = false;
static bool g_xdev = false;
static dev_t g_start_dev = 0;
static time_t g_now;

/* ------------------------------------------------------------------ */
/*  Filter matching                                                    */
/* ------------------------------------------------------------------ */

/*
 * TODO 1: Implement this function.
 *
 * Return true if the single filter 'f' matches the file at 'path' with
 * metadata 'sb'. Handle each filter_kind_t in a switch statement.
 *
 * Refer to the assignment document for the specification of each filter.
 * Relevant man pages: fnmatch(3), stat(2).
 */

// this is so we don't deal with merge conflicts, much easier

static bool match_name(const filter_t *f, const char *path) {
    // reverse search and see if '/' exists
    const char *base = strrchr(path, '/');

    // if it does, we move forward so "/main.c" to "main.c"
    if (base) base++;
    else base = path;

    // check if like a .c would be in main.c. if 0, then it is, and return true
    if (fnmatch(f->filter.pattern, base, 0) == 0) return true;

    return false;
}

static bool match_type(const filter_t *f, const struct stat *sb) {
    // easiest one just see if the filter type matches, that's all
    switch (f->filter.type_char) {
        case 'f':
            return S_ISREG(sb->st_mode);
        case 'd':
            return S_ISDIR(sb->st_mode);
        case 'l':
            return S_ISLNK(sb->st_mode);
    }

    return false;
}

static bool match_mtime(const filter_t *f, const struct stat *sb) {
    int sb_mtime_days = difftime(g_now, sb->st_mtime) / 86400;

    return sb_mtime_days <= f->filter.mtime_days;
}

static bool match_size(const filter_t *f, const struct stat *sb) {
    off_t f_size = f->filter.size.size_bytes;
    off_t sb_size = sb->st_size;

    switch (f->filter.size.size_cmp) {
        case SIZE_CMP_EXACT:
            return sb_size == f_size;
        case SIZE_CMP_GREATER:
            return sb_size > f_size;
        case SIZE_CMP_LESS:
            return sb_size < f_size;
    }

    return false;
}

static bool match_perm(const filter_t *f, const struct stat *sb) {
    // what da hell why is this so short
    return (sb->st_mode & 07777) == f->filter.perm_mode;
}

static bool filter_matches(const filter_t *f, const char *path, const struct stat *sb) {
    switch (f->kind) {
        case FILTER_NAME:
            return match_name(f, path);

        case FILTER_TYPE:
            return match_type(f, sb);

        case FILTER_MTIME:
            return match_mtime(f, sb);

        case FILTER_SIZE:
            return match_size(f, sb);

        case FILTER_PERM:
            return match_perm(f, sb);

        default:
            return false;
    }
}

/* Check if ALL filters match (AND semantics).
 * Returns true if every filter matches, false otherwise. */
static bool matches_all_filters(const char *path, const struct stat *sb) {
    for (int i = 0; i < g_nfilters; i++) {
        if (!filter_matches(&g_filters[i], path, sb)) {
            return false;
        }
    }
    return true;
}

/* ------------------------------------------------------------------ */
/*  Usage / help                                                       */
/* ------------------------------------------------------------------ */

static void print_usage(const char *progname) {
    printf("Usage: %s [-L] [-xdev] [path...] [filters...]\n"
           "\n"
           "Breadth-first search for files in a directory hierarchy.\n"
           "\n"
           "Options:\n"
           "  -L              Follow symbolic links\n"
           "  -xdev           Do not cross filesystem boundaries\n"
           "  --help          Display this help message and exit\n"
           "\n"
           "Filters (all filters are ANDed together):\n"
           "  -name PATTERN   Match filename against a glob pattern\n"
           "  -type TYPE      Match file type: f (file), d (dir), l (symlink)\n"
           "  -mtime N        Match files modified within the last N days\n"
           "  -size [+|-]N[c|k|M]\n"
           "                  Match file size (c=bytes, k=KiB, M=MiB)\n"
           "                  Prefix + means greater than, - means less than\n"
           "  -perm MODE      Match exact octal permission bits\n"
           "\n"
           "If no path is given, defaults to the current directory.\n",
           progname);
}

/* ------------------------------------------------------------------ */
/*  Argument parsing                                                   */
/* ------------------------------------------------------------------ */

/*
 * TODO 2: Implement this function.
 *
 * Parse a size specifier string into a byte count. The input is the
 * numeric portion (after any leading +/- is stripped by the caller)
 * with an optional unit suffix: 'c' (bytes), 'k' (KiB), 'M' (MiB).
 * No suffix means bytes.
 *
 * Examples: "100c" -> 100, "4k" -> 4096, "2M" -> 2097152, "512" -> 512
 */

bool is_digit(char c) {
    return c >= '0' && c <= '9';
}

static off_t parse_size(const char *arg) {
    int i = 0;
    off_t value = 0;

    if (!is_digit(arg[0])) {
        fprintf(stderr, "Must provide number\n");
        exit(EXIT_FAILURE);
    }

    while (arg[i] != '\0' && is_digit(arg[i]))
        // Subtracting '0' converts char digit to int value 
        value = value * 10 + (arg[i++] - '0');

    if (arg[i] == '\0' || arg[i] == 'c') return value;
    else if (arg[i] == 'k') return value * 1024;
    else if (arg[i] == 'M') return value * 1024 * 1024;
    else {
        fprintf(stderr, "Must be either c, k, or M at the end\n");
        exit(EXIT_FAILURE);
    }

    return 0;
}

static void cleanup_paths(char **paths, int count) {
    for (int i = 0; i < count; i++) {
        free(paths[i]);
    }
    free(paths);
}
    
/*
 * TODO 3: Implement this function.
 *
 * Parse command-line arguments into options, paths, and filters.
 * See the usage string and assignment document for the expected format.
 *
 * Set the global variables g_follow_links, g_xdev, g_filters, and
 * g_nfilters as appropriate. Return a malloc'd array of path strings
 * and set *npaths. If no paths are given, default to ".".
 *
 * Handle --help by calling print_usage() and exiting.
 * Exit with an error for unknown options or missing filter arguments.
 */
static char **parse_args(int argc, char *argv[], int *npaths) {
    int i = 1;

    char **paths = NULL;
    int path_count = 0;
    int path_cap = 0;

    g_filters = NULL;
    g_nfilters = 0;
    int filter_cap = 0;

    // these are the options, this should be pretty simple and done

    while (i < argc) {
        if (strcmp(argv[i], "-L") == 0) {
            g_follow_links = true;
            i++;
        }
        else if (strcmp(argv[i], "-xdev") == 0) {
            g_xdev = true;
            i++;
        }
        else if (strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            exit(0);
        }
        else break;
    }

    // paths given

    while (i < argc && argv[i][0] != '-') {
        // make bigger if needed, like dictionary (CSC 357 - assgn 4)
        if (path_count == path_cap) {
            path_cap = path_cap ? path_cap * 2 : 4;
            paths = realloc(paths, path_cap * sizeof(char *));
        }
        paths[path_count++] = strdup(argv[i++]);
    }

    // default path

    if (path_count == 0) {
        paths = malloc(sizeof(char *));
        paths[0] = strdup(".");
        path_count = 1;
    }

    struct stat start_sb;
    if (stat(paths[0], &start_sb) == 0) {
        g_start_dev = start_sb.st_dev;
    } else {
        fprintf(stderr, "bfind: cannot stat '%s': %s\n", 
                paths[0], strerror(errno));
    }

    // parse the filters, this is j a bunch of error handling lwk

    while (i < argc) {
        if (g_nfilters == filter_cap) {
            filter_cap = filter_cap ? filter_cap * 2 : 4;
            g_filters = realloc(g_filters, filter_cap * sizeof(filter_t));
        }

        filter_t *f = &g_filters[g_nfilters];

        if (strcmp(argv[i], "-name") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "bfind: -name requires argument\n");
                cleanup_paths(paths, path_count);
                exit(EXIT_FAILURE);
            }
            f->kind = FILTER_NAME;
            f->filter.pattern = strdup(argv[i + 1]);
            i += 2;
        }
        
        else if (strcmp(argv[i], "-type") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "bfind: -type requires argument\n");
                cleanup_paths(paths, path_count);
                exit(EXIT_FAILURE);
            }
            f->kind = FILTER_TYPE; 
            f->filter.type_char = argv[i + 1][0];
            i += 2;
        }

        else if (strcmp(argv[i], "-mtime") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "bfind: -mtime requires argument\n");
                cleanup_paths(paths, path_count);
                exit(EXIT_FAILURE);
            }
            f->kind = FILTER_MTIME;
            f->filter.mtime_days = atoi(argv[i + 1]);
            i += 2;
        }

        else if (strcmp(argv[i], "-size") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "bfind: -size requires argument\n");
                cleanup_paths(paths, path_count);
                exit(EXIT_FAILURE);
            }

            f->kind = FILTER_SIZE;

            const char *arg = argv[i + 1];

            if (arg[0] == '+') {
                f->filter.size.size_cmp = SIZE_CMP_GREATER;
                f->filter.size.size_bytes = parse_size(arg + 1);
            } else if (arg[0] == '-') {
                f->filter.size.size_cmp = SIZE_CMP_LESS;
                f->filter.size.size_bytes = parse_size(arg + 1);
            } else {
                f->filter.size.size_cmp = SIZE_CMP_EXACT;
                f->filter.size.size_bytes = parse_size(arg);
            }

            i += 2;
        }

        else if (strcmp(argv[i], "-perm") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "bfind: -perm requires argument\n");
                cleanup_paths(paths, path_count);
                exit(EXIT_FAILURE);
            }
            f->kind = FILTER_PERM;
            f->filter.perm_mode = (mode_t)strtol(argv[i + 1], NULL, 8);
            i += 2;
        }

        else {
            fprintf(stderr, "bfind: unknown filter '%s'\n", argv[i]);
            cleanup_paths(paths, path_count);
            exit(EXIT_FAILURE);
        }    

        g_nfilters++;
    }

    *npaths = path_count;
    return paths;
}

/* ------------------------------------------------------------------ */
/*  BFS traversal                                                      */
/* ------------------------------------------------------------------ */

/*
 * TODO 4: Implement this function.
 *
 * Traverse the filesystem breadth-first starting from the given paths.
 * For each entry, check the filters and print matching paths to stdout.
 *
 * You must handle:
 *   - The -L flag: controls whether symlinks are followed. Think about
 *     when to use stat(2) vs lstat(2) and what that means for descending
 *     into directories.
 *   - The -xdev flag: do not descend into directories on a different
 *     filesystem than the starting path (compare st_dev values).
 *   - Cycle detection (only relevant with -L): a symlink can point back
 *     to an ancestor directory. Only symlinks can create cycles (the OS
 *     forbids hard links to directories). Use the dev_ino_t type defined
 *     above to track visited directories — real directories should always
 *     be descended into, but symlinks to already-visited directories
 *     should be skipped.
 *   - Errors: if stat or opendir fails, print a message to stderr
 *     and continue traversing. Do not exit.
 *
 * The provided queue library (queue.h) implements a generic FIFO queue.
 */

static dev_ino_t *visited = NULL;
static int visited_count = 0;
static int visited_cap = 0;

static bool seen_before(dev_t dev, ino_t ino) {
    for (int i = 0; i < visited_count; i++) 
        if (visited[i].dev == dev && visited[i].ino == ino) return true;

    return false;
}

static void record_dir(dev_t dev, ino_t ino) {
    if (visited_count == visited_cap) {
        visited_cap = visited_cap ? visited_cap * 2 : 16;
        visited = realloc(visited, visited_cap * sizeof(dev_ino_t));
    }

    visited[visited_count].dev = dev;
    visited[visited_count].ino = ino;
    visited_count++;
}

static void bfs_traverse(char **start_paths, int npaths) {
    // i kinda wanna change these functions, like eh its whatever
    queue_t queue;
    queue_init(&queue);

    for (int i = 0; i < npaths; i++)
        queue_enqueue(&queue, strdup(start_paths[i]));
    
    while (!queue_is_empty(&queue)) {
        char *path = queue_dequeue(&queue);
        
        // if stat fails
        struct stat sb;

        int ret;
        if (g_follow_links) ret = stat(path, &sb);
        else ret = lstat(path, &sb);
        
        if (ret != 0) {
            fprintf(stderr, "bfind: cannot stat '%s': %s\n", path, strerror(errno));
            free(path);
            continue;
        }       

        if (matches_all_filters(path, &sb)) {
            printf("%s\n", path);
        }

        if (S_ISDIR(sb.st_mode)) {
            struct stat lsb;
            bool is_symlink = (lstat(path, &lsb) == 0 && S_ISLNK(lsb.st_mode));

            if (g_follow_links && is_symlink && seen_before(sb.st_dev, sb.st_ino)) {
                free(path);
                continue;
            }
            
            if (g_xdev && sb.st_dev != g_start_dev) {
                free(path);
                continue;
            }   

            if (g_follow_links && is_symlink) 
                record_dir(sb.st_dev, sb.st_ino);

            // check if directory isn't openable, simple command
            DIR *dir = opendir(path);
            if (!dir) {
                fprintf(stderr, "bfind: cannot open '%s': %s\n", path, strerror(errno));
                free(path);
                continue;
            }

            struct dirent *entry;
            while ((entry = readdir(dir)) != NULL) {
                if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;

                // bind the path together and then push it to the queue
                size_t path_len = strlen(path);
                bool has_slash = (path_len > 0 && path[path_len - 1] == '/');

                size_t len = path_len + strlen(entry->d_name) + (has_slash ? 1 : 2);
                char *child = malloc(len);

                // if the path already ends with a slash, we don't need to add another one
                if (has_slash) {
                    snprintf(child, len, "%s%s", path, entry->d_name);
                } else {
                    snprintf(child, len, "%s/%s", path, entry->d_name);
                }

                // Do we need to remove './' from the beginning of the path? 

                queue_enqueue(&queue, child);
            }

            closedir(dir);
        }

        free(path);
    }

    queue_destroy(&queue);
}

/* ------------------------------------------------------------------ */
/*  Main                                                               */
/* ------------------------------------------------------------------ */

int main(int argc, char *argv[]) {
    g_now = time(NULL);

    int npaths;
    char **paths = parse_args(argc, argv, &npaths);

    bfs_traverse(paths, npaths);

    free(paths);
    free(g_filters);
    free(visited);
    return 0;
}
