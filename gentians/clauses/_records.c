#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <pthread.h>
#include <time.h>
#endif

typedef bool (*truth_fn)(const void *, int32_t, bool *);
typedef struct { int32_t literal; size_t offset; int64_t value; } entry;
typedef struct {
    truth_fn is_true;
    size_t width, size, count, batch;
    entry *entries;
    int64_t *records;
} decoder;

static void destroy(PyObject *capsule) {
    decoder *d = PyCapsule_GetPointer(capsule, "gentians.records");
    if (d) { free(d->entries); free(d->records); free(d); }
}

static PyObject *create(PyObject *self, PyObject *args) {
    unsigned long long address;
    Py_ssize_t width, batch;
    PyObject *mapping;
    if (!PyArg_ParseTuple(args, "KnnO", &address, &width, &batch, &mapping)) return NULL;
    if (width < 0 || batch < 1 || batch > 4096 || (size_t)width > SIZE_MAX / (8 * (size_t)batch)) {
        PyErr_SetString(PyExc_ValueError, "invalid numeric record capacity"); return NULL;
    }
    PyObject *items = PySequence_Fast(mapping, "lookup must be a sequence");
    if (!items) return NULL;
    decoder *d = calloc(1, sizeof(decoder));
    if (!d) { Py_DECREF(items); return PyErr_NoMemory(); }
    d->is_true = (truth_fn)(uintptr_t)address; d->width = (size_t)width; d->batch = (size_t)batch;
    d->size = (size_t)PySequence_Fast_GET_SIZE(items);
    d->entries = malloc((d->size ? d->size : 1) * sizeof(entry));
    d->records = malloc((d->width ? d->width : 1) * d->batch * sizeof(int64_t));
    if (!d->entries || !d->records) {
        free(d->entries); free(d->records); free(d); Py_DECREF(items); return PyErr_NoMemory();
    }
    for (size_t i = 0; i < d->size; ++i) {
        int literal; Py_ssize_t offset; long long value;
        if (!PyArg_ParseTuple(PySequence_Fast_GET_ITEM(items, (Py_ssize_t)i), "inL", &literal, &offset, &value)
                || offset < 0 || (size_t)offset >= d->width || value < 0) {
            if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError, "invalid numeric record lookup");
            free(d->entries); free(d->records); free(d); Py_DECREF(items); return NULL;
        }
        d->entries[i] = (entry){(int32_t)literal, (size_t)offset, (int64_t)value};
    }
    Py_DECREF(items);
    PyObject *capsule = PyCapsule_New(d, "gentians.records", destroy);
    if (!capsule) { free(d->entries); free(d->records); free(d); }
    return capsule;
}

static PyObject *take(decoder *d) {
    if (!d->count) Py_RETURN_NONE;
    PyObject *result = PyBytes_FromStringAndSize((const char *)d->records,
        (Py_ssize_t)(d->count * d->width * sizeof(int64_t)));
    if (result) d->count = 0;
    return result;
}

static const char *copy_row(decoder *d, const void *model, int64_t *row) {
    // Truth of each prepared displayed atom; the model lives only during this call.
    for (size_t i = 0; i < d->width; ++i) row[i] = -1;
    for (size_t i = 0; i < d->size; ++i) {
        bool value;
        if (!d->is_true(model, d->entries[i].literal, &value)) return "clingo could not read a clause atom";
        if (value) row[d->entries[i].offset] = d->entries[i].value;
    }
    return NULL;
}

static PyObject *push(PyObject *self, PyObject *args) {
    PyObject *capsule; unsigned long long model;
    if (!PyArg_ParseTuple(args, "OK", &capsule, &model)) return NULL;
    decoder *d = PyCapsule_GetPointer(capsule, "gentians.records");
    if (!d) return NULL;
    const char *error = copy_row(d, (const void *)(uintptr_t)model, d->records + d->count * d->width);
    if (error) { PyErr_SetString(PyExc_RuntimeError, error); return NULL; }
    if (++d->count == d->batch) return take(d);
    Py_RETURN_NONE;
}

/* One lock with two condition variables, from the platform thread library. */
typedef struct {
#ifdef _WIN32
    SRWLOCK lock; CONDITION_VARIABLE ready, space;
#else
    pthread_mutex_t lock; pthread_cond_t ready, space;
#endif
} sync_t;

static void sync_init(sync_t *s) {
#ifdef _WIN32
    InitializeSRWLock(&s->lock); InitializeConditionVariable(&s->ready); InitializeConditionVariable(&s->space);
#else
    pthread_mutex_init(&s->lock, NULL); pthread_cond_init(&s->ready, NULL); pthread_cond_init(&s->space, NULL);
#endif
}

static void sync_destroy(sync_t *s) {
#ifdef _WIN32
    (void)s;
#else
    pthread_mutex_destroy(&s->lock); pthread_cond_destroy(&s->ready); pthread_cond_destroy(&s->space);
#endif
}

#ifdef _WIN32
#define SYNC_LOCK(s) AcquireSRWLockExclusive(&(s)->lock)
#define SYNC_UNLOCK(s) ReleaseSRWLockExclusive(&(s)->lock)
#define SYNC_WAKE(c) WakeAllConditionVariable(&(c))
#define SYNC_WAIT(s, c) SleepConditionVariableSRW(&(c), &(s)->lock, INFINITE, 0)
#define SYNC_WAIT_MS(s, c, ms) SleepConditionVariableSRW(&(c), &(s)->lock, (ms), 0)
#else
#define SYNC_LOCK(s) pthread_mutex_lock(&(s)->lock)
#define SYNC_UNLOCK(s) pthread_mutex_unlock(&(s)->lock)
#define SYNC_WAKE(c) pthread_cond_broadcast(&(c))
#define SYNC_WAIT(s, c) pthread_cond_wait(&(c), &(s)->lock)
static void sync_wait_ms(pthread_mutex_t *lock, pthread_cond_t *cond, long ms) {
    struct timespec until;
    clock_gettime(CLOCK_REALTIME, &until);
    until.tv_sec += ms / 1000; until.tv_nsec += (ms % 1000) * 1000000L;
    if (until.tv_nsec >= 1000000000L) { until.tv_sec++; until.tv_nsec -= 1000000000L; }
    pthread_cond_timedwait(cond, lock, &until);
}
#define SYNC_WAIT_MS(s, c, ms) sync_wait_ms(&(s)->lock, &(c), (ms))
#endif

/* Solver threads copy models into a fixed pool of owned blocks and never take
   the GIL; the calling thread turns full blocks into Python values while the
   search continues. A full pool makes producers wait, bounding memory. */
#define POOL_BLOCKS 16
typedef bool (*event_fn)(unsigned, void *, void *, bool *);
typedef bool (*solve_fn)(void *, unsigned, const int32_t *, size_t, event_fn, void *, void **);
typedef bool (*get_fn)(void *, unsigned *);
typedef bool (*close_fn)(void *);
typedef bool (*cancel_fn)(void *);
typedef const char *(*error_message_fn)(void);
typedef void (*set_error_fn)(int, const char *);
typedef struct {
    decoder *decoder; set_error_fn set_error; sync_t sync;
    int64_t *blocks; size_t counts[POOL_BLOCKS];
    int free_list[POOL_BLOCKS]; size_t free_count;
    int ready[POOL_BLOCKS]; size_t ready_head, ready_count;
    int current; size_t models; double seconds; int measure;
    bool finished, discard;
} solve_context;

static double monotonic_seconds(void) {
#ifdef _WIN32
    LARGE_INTEGER value, frequency;
    QueryPerformanceCounter(&value); QueryPerformanceFrequency(&frequency);
    return (double)value.QuadPart / (double)frequency.QuadPart;
#else
    struct timespec value;
    clock_gettime(CLOCK_MONOTONIC, &value);
    return (double)value.tv_sec + (double)value.tv_nsec / 1e9;
#endif
}

static int64_t *block_rows(solve_context *c, int index) {
    return c->blocks + (size_t)index * c->decoder->batch * c->decoder->width;
}

static bool model_event(unsigned type, void *event, void *data, bool *goon) {
    solve_context *c = data;
    if (type == 3) {  // clingo_solve_event_type_finish
        SYNC_LOCK(&c->sync); c->finished = true; SYNC_WAKE(c->sync.ready); SYNC_UNLOCK(&c->sync);
        return true;
    }
    if (type != 0 || !event) return true;
    SYNC_LOCK(&c->sync);
    while (!c->discard && c->current < 0 && c->free_count == 0) SYNC_WAIT(&c->sync, c->sync.space);
    if (c->discard) { *goon = false; SYNC_UNLOCK(&c->sync); return true; }
    if (c->current < 0) { c->current = c->free_list[--c->free_count]; c->counts[c->current] = 0; }
    double started = c->measure ? monotonic_seconds() : 0;
    const char *error = copy_row(c->decoder, event,
        block_rows(c, c->current) + c->counts[c->current] * c->decoder->width);
    if (c->measure) c->seconds += monotonic_seconds() - started;
    if (error) {
        // Real native/API failures obey Clingo's error contract; its error
        // state is thread-local, so every failing callback sets it.
        *goon = false;
        c->set_error(4, "native clause record capture failed");
        SYNC_UNLOCK(&c->sync);
        return false;
    }
    c->models++;
    if (++c->counts[c->current] == c->decoder->batch) {
        c->ready[(c->ready_head + c->ready_count++) % POOL_BLOCKS] = c->current;
        c->current = -1;
        SYNC_WAKE(c->sync.ready);
    }
    SYNC_UNLOCK(&c->sync);
    return true;
}

static void copy_message(char *message, size_t size, error_message_fn error_message) {
    const char *error = error_message();
    if (error) { strncpy(message, error, size - 1); message[size - 1] = 0; }
}

static PyObject *solve_records(PyObject *self, PyObject *args) {
    PyObject *capsule, *addresses, *consume; unsigned long long control;
    int measure;
    if (!PyArg_ParseTuple(args, "OKOOp", &capsule, &control, &addresses, &consume, &measure)) return NULL;
    decoder *d = PyCapsule_GetPointer(capsule, "gentians.records");
    if (!d) return NULL;
    unsigned long long solve_address, get_address, close_address, error_address, set_address, cancel_address;
    if (!PyArg_ParseTuple(addresses, "KKKKKK", &solve_address, &get_address, &close_address, &error_address,
                          &set_address, &cancel_address)) return NULL;
    if (!control || !solve_address || !get_address || !close_address || !error_address || !set_address
            || !cancel_address || !PyCallable_Check(consume) || d->count) {
        PyErr_SetString(PyExc_ValueError, "invalid native clause solve"); return NULL;
    }
    error_message_fn error_message = (error_message_fn)(uintptr_t)error_address;
    solve_context c = {0}; c.decoder = d; c.measure = measure; c.current = -1;
    c.set_error = (set_error_fn)(uintptr_t)set_address;
    size_t block = (d->width ? d->width : 1) * d->batch;
    c.blocks = malloc(POOL_BLOCKS * block * sizeof(int64_t));
    if (!c.blocks) return PyErr_NoMemory();
    for (int i = POOL_BLOCKS - 1; i >= 0; --i) c.free_list[c.free_count++] = i;
    sync_init(&c.sync);
    PyObject *error_type = NULL, *error_value = NULL, *error_traceback = NULL;
    void *handle = NULL; unsigned result = 0; bool ok;
    char message[2048] = "native Clingo solve failed";
    Py_BEGIN_ALLOW_THREADS
    // clingo_solve_mode_async: the search runs in Clingo's own threads.
    ok = ((solve_fn)(uintptr_t)solve_address)((void *)(uintptr_t)control, 1, NULL, 0, model_event, &c, &handle);
    if (!ok) copy_message(message, sizeof(message), error_message);
    Py_END_ALLOW_THREADS
    while (ok) {
        int index = -1; bool done = false;
        Py_BEGIN_ALLOW_THREADS
        SYNC_LOCK(&c.sync);
        if (!c.ready_count && !c.finished) SYNC_WAIT_MS(&c.sync, c.sync.ready, 100);
        if (c.ready_count) {
            index = c.ready[c.ready_head];
            c.ready_head = (c.ready_head + 1) % POOL_BLOCKS; c.ready_count--;
        } else {
            done = c.finished;
        }
        SYNC_UNLOCK(&c.sync);
        Py_END_ALLOW_THREADS
        if (done) break;
        PyObject *value = NULL;
        if (index >= 0 && !error_type)
            value = PyBytes_FromStringAndSize((const char *)block_rows(&c, index),
                                              (Py_ssize_t)(c.counts[index] * d->width * sizeof(int64_t)));
        if (index >= 0) {
            SYNC_LOCK(&c.sync); c.free_list[c.free_count++] = index; SYNC_WAKE(c.sync.space); SYNC_UNLOCK(&c.sync);
        }
        if (!error_type) {
            // Delivery errors and pending signals stop the search; remaining
            // blocks are then drained without delivery.
            if (value) { PyObject *delivered = PyObject_CallOneArg(consume, value); Py_XDECREF(delivered); }
            else if (index < 0) PyErr_CheckSignals();
            if (PyErr_Occurred()) {
                PyErr_Fetch(&error_type, &error_value, &error_traceback);
                SYNC_LOCK(&c.sync); c.discard = true; SYNC_WAKE(c.sync.space); SYNC_UNLOCK(&c.sync);
                Py_BEGIN_ALLOW_THREADS
                ((cancel_fn)(uintptr_t)cancel_address)(handle);
                Py_END_ALLOW_THREADS
            }
        }
        Py_XDECREF(value);
    }
    Py_BEGIN_ALLOW_THREADS
    if (ok) {
        ok = ((get_fn)(uintptr_t)get_address)(handle, &result);
        if (!ok) copy_message(message, sizeof(message), error_message);
    }
    if (handle && !((close_fn)(uintptr_t)close_address)(handle) && ok) {
        ok = false;
        copy_message(message, sizeof(message), error_message);
    }
    Py_END_ALLOW_THREADS
    // The final partial block stays with the decoder for flush().
    if (ok && !error_type && c.current >= 0 && c.counts[c.current]) {
        memcpy(d->records, block_rows(&c, c.current), c.counts[c.current] * d->width * sizeof(int64_t));
        d->count = c.counts[c.current];
    }
    sync_destroy(&c.sync);
    free(c.blocks);
    if (error_type) {
        d->count = 0;
        PyErr_Restore(error_type, error_value, error_traceback);
        return NULL;
    }
    if (!ok) { d->count = 0; PyErr_SetString(PyExc_RuntimeError, message); return NULL; }
    return Py_BuildValue("Kd", (unsigned long long)c.models, c.seconds);
}

static PyObject *flush(PyObject *self, PyObject *capsule) {
    decoder *d = PyCapsule_GetPointer(capsule, "gentians.records");
    return d ? take(d) : NULL;
}

/* Compile record layouts once. The decoder owns only Python values, never a
   live Model or a pointer into a Control. */
typedef struct { PyObject *prefix; Py_ssize_t count; size_t *offsets; } choice;
typedef struct { int head; Py_ssize_t count; choice *choices; } slot_plan;
typedef struct {
    size_t width; Py_ssize_t count; slot_plan *slots;
    PyObject *literal, *clause, *cache;
} decode_plan;

static void free_plan(decode_plan *p) {
    if (!p) return;
    for (Py_ssize_t s = 0; p->slots && s < p->count; ++s) {
        for (Py_ssize_t m = 0; p->slots[s].choices && m < p->slots[s].count; ++m) {
            Py_XDECREF(p->slots[s].choices[m].prefix);
            free(p->slots[s].choices[m].offsets);
        }
        free(p->slots[s].choices);
    }
    free(p->slots); Py_XDECREF(p->literal); Py_XDECREF(p->clause);
    Py_XDECREF(p->cache); free(p);
}
static void destroy_plan(PyObject *capsule) {
    free_plan(PyCapsule_GetPointer(capsule, "gentians.decode"));
}
static PyObject *prepare_decode(PyObject *self, PyObject *args) {
    Py_ssize_t width; PyObject *slots, *literal, *clause;
    if (!PyArg_ParseTuple(args, "nOOO", &width, &slots, &literal, &clause)) return NULL;
    if (width < 1 || (size_t)width > SIZE_MAX / sizeof(int64_t)
            || !PyTuple_Check(slots) || !PyCallable_Check(literal) || !PyCallable_Check(clause)) {
        PyErr_SetString(PyExc_ValueError, "invalid numeric decode plan"); return NULL;
    }
    decode_plan *p = calloc(1, sizeof(decode_plan));
    if (!p) return PyErr_NoMemory();
    p->width = (size_t)width; p->count = PyTuple_GET_SIZE(slots);
    if (p->count > width) { free(p); PyErr_SetString(PyExc_ValueError, "too many numeric slots"); return NULL; }
    p->slots = calloc(p->count ? (size_t)p->count : 1, sizeof(slot_plan));
    p->literal = Py_NewRef(literal); p->clause = Py_NewRef(clause); p->cache = PyDict_New();
    if (!p->slots || !p->cache) { free_plan(p); return PyErr_NoMemory(); }
    for (Py_ssize_t s = 0; s < p->count; ++s) {
        PyObject *section, *slot, *choices;
        if (!PyArg_ParseTuple(PyTuple_GET_ITEM(slots, s), "OOO", &section, &slot, &choices)
                || !PyUnicode_Check(section) || !PyTuple_Check(choices)) goto error;
        p->slots[s].head = PyUnicode_CompareWithASCIIString(section, "head") == 0;
        if (!p->slots[s].head && PyUnicode_CompareWithASCIIString(section, "body") != 0) goto error;
        p->slots[s].count = PyTuple_GET_SIZE(choices);
        p->slots[s].choices = calloc(p->slots[s].count ? (size_t)p->slots[s].count : 1, sizeof(choice));
        if (!p->slots[s].choices) { PyErr_NoMemory(); goto error; }
        for (Py_ssize_t m = 0; m < p->slots[s].count; ++m) {
            PyObject *offsets = PyTuple_GET_ITEM(choices, m);
            if (offsets == Py_None) continue;
            if (!PyTuple_Check(offsets)) goto error;
            choice *c = p->slots[s].choices + m;
            PyObject *mode = PyLong_FromSsize_t(m);
            if (!mode) goto error;
            c->prefix = PyTuple_Pack(3, section, slot, mode); Py_DECREF(mode);
            c->count = PyTuple_GET_SIZE(offsets);
            c->offsets = calloc(c->count ? (size_t)c->count : 1, sizeof(size_t));
            if (!c->prefix || !c->offsets) { if (!PyErr_Occurred()) PyErr_NoMemory(); goto error; }
            for (Py_ssize_t a = 0; a < c->count; ++a) {
                Py_ssize_t offset = PyLong_AsSsize_t(PyTuple_GET_ITEM(offsets, a));
                if (offset < 0 || offset >= width || PyErr_Occurred()) goto error;
                c->offsets[a] = (size_t)offset;
            }
        }
    }
    PyObject *capsule = PyCapsule_New(p, "gentians.decode", destroy_plan);
    if (!capsule) free_plan(p);
    return capsule;
error:
    if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError, "invalid numeric decode plan");
    free_plan(p); return NULL;
}
static int64_t record_value(const char *row, size_t offset) {
    int64_t value; memcpy(&value, row + offset * sizeof(value), sizeof(value)); return value;
}
static PyObject *decode_block(PyObject *self, PyObject *args) {
    PyObject *capsule; Py_buffer block;
    if (!PyArg_ParseTuple(args, "Oy*", &capsule, &block)) return NULL;
    decode_plan *p = PyCapsule_GetPointer(capsule, "gentians.decode");
    if (!p) { PyBuffer_Release(&block); return NULL; }
    size_t stride = p->width * sizeof(int64_t);
    if ((size_t)block.len % stride) {
        PyBuffer_Release(&block); PyErr_SetString(PyExc_ValueError, "incomplete numeric record"); return NULL;
    }
    PyObject *result = PyList_New(0), *head = NULL, *body = NULL;
    if (!result) goto error;
    for (size_t start = 0; start < (size_t)block.len; start += stride) {
        head = PyList_New(0); body = PyList_New(0);
        if (!head || !body) goto error;
        const char *row = (const char *)block.buf + start;
        for (Py_ssize_t s = 0; s < p->count; ++s) {
            int64_t mode = record_value(row, (size_t)s);
            if (mode < 0) continue;
            if (mode >= p->slots[s].count || !p->slots[s].choices[mode].prefix) {
                PyErr_SetString(PyExc_RuntimeError, "unknown selected numeric mode"); goto error;
            }
            choice *c = p->slots[s].choices + mode;
            PyObject *variables = PyTuple_New(c->count);
            if (!variables) goto error;
            for (Py_ssize_t a = 0; a < c->count; ++a) {
                int64_t value = record_value(row, c->offsets[a]);
                if (value < 0) {
                    Py_DECREF(variables); PyErr_SetString(PyExc_RuntimeError, "selected numeric literal argument has no variable"); goto error;
                }
                PyObject *number = PyLong_FromLongLong(value);
                if (!number) { Py_DECREF(variables); goto error; }
                PyTuple_SET_ITEM(variables, a, number);
            }
            PyObject *key = PyTuple_Pack(4, PyTuple_GET_ITEM(c->prefix, 0),
                PyTuple_GET_ITEM(c->prefix, 1), PyTuple_GET_ITEM(c->prefix, 2), variables);
            Py_DECREF(variables);
            if (!key) goto error;
            PyObject *literal = NULL;
            if (PyDict_GetItemRef(p->cache, key, &literal) < 0) { Py_DECREF(key); goto error; }
            if (!literal) {
                literal = PyObject_CallObject(p->literal, key);
                if (!literal) { Py_DECREF(key); goto error; }
                if (PyDict_Size(p->cache) >= 8192) PyDict_Clear(p->cache);
                if (PyDict_SetItem(p->cache, key, literal) < 0) { Py_DECREF(key); Py_DECREF(literal); goto error; }
            }
            Py_DECREF(key);
            int rc = PyList_Append(p->slots[s].head ? head : body, literal); Py_DECREF(literal);
            if (rc < 0) goto error;
        }
        PyObject *heads = PyList_AsTuple(head), *bodies = PyList_AsTuple(body);
        Py_CLEAR(head); Py_CLEAR(body);
        if (!heads || !bodies) { Py_XDECREF(heads); Py_XDECREF(bodies); goto error; }
        PyObject *clause = PyObject_CallFunctionObjArgs(p->clause, heads, bodies, NULL);
        Py_DECREF(heads); Py_DECREF(bodies);
        if (!clause) goto error;
        int rc = PyList_Append(result, clause); Py_DECREF(clause);
        if (rc < 0) goto error;
    }
    PyBuffer_Release(&block); return result;
error:
    Py_XDECREF(head); Py_XDECREF(body); Py_XDECREF(result); PyBuffer_Release(&block); return NULL;
}

static PyMethodDef methods[] = {
    {"create", create, METH_VARARGS, "Prepare a Control-owned numeric lookup."},
    {"push", push, METH_VARARGS, "Copy one live model; return a block when full."},
    {"flush", flush, METH_O, "Return the final owned block."},
    {"solve", solve_records, METH_VARARGS, "Capture native model events and deliver owned blocks."},
    {"prepare_decode", prepare_decode, METH_VARARGS, "Compile owned block decoding layouts."},
    {"decode_block", decode_block, METH_VARARGS, "Materialize immutable values from an owned block."},
    {NULL, NULL, 0, NULL}
};
static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "_records", NULL, -1, methods};
PyMODINIT_FUNC PyInit__records(void) { return PyModule_Create(&module); }
