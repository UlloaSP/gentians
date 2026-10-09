#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#endif

typedef bool (*symbols_fn)(const void *, unsigned, uint64_t *, size_t);
typedef struct { uint64_t handle; size_t offset; int64_t value; } entry;
typedef struct {
    symbols_fn symbols;
    size_t width, table_size, count, batch;
    entry *table;
    uint64_t *shown;
    int64_t *records;
} decoder;

static size_t hash_handle(uint64_t key) {
    key ^= key >> 30; key *= UINT64_C(0xbf58476d1ce4e5b9);
    key ^= key >> 27; key *= UINT64_C(0x94d049bb133111eb);
    return (size_t)(key ^ (key >> 31));
}

static void destroy(PyObject *capsule) {
    decoder *d = PyCapsule_GetPointer(capsule, "gentians.records");
    if (d) { free(d->table); free(d->shown); free(d->records); free(d); }
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
    d->symbols = (symbols_fn)(uintptr_t)address; d->width = (size_t)width; d->batch = (size_t)batch;
    d->table_size = 2;
    while (d->table_size < 2 * (size_t)PySequence_Fast_GET_SIZE(items)) d->table_size *= 2;
    d->table = calloc(d->table_size, sizeof(entry));
    d->shown = calloc(d->width ? d->width : 1, sizeof(uint64_t));
    d->records = malloc((d->width ? d->width : 1) * d->batch * sizeof(int64_t));
    if (!d->table || !d->shown || !d->records) {
        free(d->table); free(d->shown); free(d->records); free(d); Py_DECREF(items); return PyErr_NoMemory();
    }
    for (Py_ssize_t i = 0; i < PySequence_Fast_GET_SIZE(items); ++i) {
        unsigned long long key; Py_ssize_t offset; long long value;
        if (!PyArg_ParseTuple(PySequence_Fast_GET_ITEM(items, i), "KnL", &key, &offset, &value)
                || !key || offset < 0 || (size_t)offset >= d->width || value < 0) {
            if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError, "invalid numeric record lookup");
            free(d->table); free(d->shown); free(d->records); free(d); Py_DECREF(items); return NULL;
        }
        size_t index = hash_handle(key) & (d->table_size - 1);
        while (d->table[index].handle) index = (index + 1) & (d->table_size - 1);
        d->table[index] = (entry){key, (size_t)offset, (int64_t)value};
    }
    Py_DECREF(items);
    PyObject *capsule = PyCapsule_New(d, "gentians.records", destroy);
    if (!capsule) { free(d->table); free(d->shown); free(d->records); free(d); }
    return capsule;
}

static PyObject *take(decoder *d) {
    if (!d->count) Py_RETURN_NONE;
    PyObject *result = PyBytes_FromStringAndSize((const char *)d->records,
        (Py_ssize_t)(d->count * d->width * sizeof(int64_t)));
    if (result) d->count = 0;
    return result;
}

static const char *copy_row(decoder *d, const void *model) {
    memset(d->shown, 0, d->width * sizeof(uint64_t));
    // clingo_show_type_shown = 2. Model pointers live only during this call.
    if (!d->symbols(model, 2, d->shown, d->width)) return "clingo could not copy numeric clause record";
    int64_t *row = d->records + d->count * d->width;
    for (size_t i = 0; i < d->width; ++i) row[i] = -1;
    for (size_t i = 0; i < d->width && d->shown[i]; ++i) {
        size_t index = hash_handle(d->shown[i]) & (d->table_size - 1);
        while (d->table[index].handle && d->table[index].handle != d->shown[i]) index = (index + 1) & (d->table_size - 1);
        if (!d->table[index].handle) return "unknown clause symbol in native record";
        row[d->table[index].offset] = d->table[index].value;
    }
    d->count++;
    return NULL;
}

static PyObject *push(PyObject *self, PyObject *args) {
    PyObject *capsule; unsigned long long model;
    if (!PyArg_ParseTuple(args, "OK", &capsule, &model)) return NULL;
    decoder *d = PyCapsule_GetPointer(capsule, "gentians.records");
    if (!d) return NULL;
    const char *error = copy_row(d, (const void *)(uintptr_t)model);
    if (error) { PyErr_SetString(PyExc_RuntimeError, error); return NULL; }
    if (d->count == d->batch) return take(d);
    Py_RETURN_NONE;
}

/* Model events copy into owned rows without Python or a retained Model. Only
   full blocks acquire the GIL. The lock also protects multi-thread Controls. */
typedef bool (*event_fn)(unsigned, void *, void *, bool *);
typedef bool (*solve_fn)(void *, unsigned, const int32_t *, size_t, event_fn, void *, void **);
typedef bool (*get_fn)(void *, unsigned *);
typedef bool (*close_fn)(void *);
typedef const char *(*error_message_fn)(void);
typedef void (*set_error_fn)(int, const char *);
typedef struct {
    decoder *decoder; PyObject *consume, *error_type, *error_value, *error_traceback;
    PyThread_type_lock lock; set_error_fn set_error;
    size_t models; double seconds; int measure; bool api_error;
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

static bool model_event(unsigned type, void *event, void *data, bool *goon) {
    if (type != 0 || !event) return true;
    solve_context *context = data;
    PyThread_acquire_lock(context->lock, WAIT_LOCK);
    double started = context->measure ? monotonic_seconds() : 0;
    bool ok = context->error_type == NULL;
    const char *error = ok ? copy_row(context->decoder, event) : NULL;
    if (error) context->api_error = true;
    if (ok && !error) context->models++;
    if (error || (ok && context->decoder->count == context->decoder->batch)) {
        PyGILState_STATE gil = PyGILState_Ensure();
        if (error) PyErr_SetString(PyExc_RuntimeError, error);
        else {
            PyObject *block = take(context->decoder);
            PyObject *result = block ? PyObject_CallOneArg(context->consume, block) : NULL;
            Py_XDECREF(block); Py_XDECREF(result);
        }
        if (PyErr_Occurred()) {
            PyErr_Fetch(&context->error_type, &context->error_value, &context->error_traceback);
            ok = false;
        }
        PyGILState_Release(gil);
    }
    if (context->measure) context->seconds += monotonic_seconds() - started;
    if (!ok) {
        *goon = false;
        // A Python delivery exception is restored after normal termination and
        // handle closure. Turning it into a solver error can poison a parallel
        // Control. Real native/API failures still obey Clingo's error contract;
        // its error state is thread-local, so every failing callback sets it.
        if (context->api_error) context->set_error(4, "native clause record capture failed");
    }
    bool success = !context->api_error;
    PyThread_release_lock(context->lock);
    return success;
}

static PyObject *solve_records(PyObject *self, PyObject *args) {
    PyObject *capsule, *addresses, *consume; unsigned long long control;
    int measure;
    if (!PyArg_ParseTuple(args, "OKOOp", &capsule, &control, &addresses, &consume, &measure)) return NULL;
    decoder *d = PyCapsule_GetPointer(capsule, "gentians.records");
    if (!d) return NULL;
    unsigned long long solve_address, get_address, close_address, error_address, set_address;
    if (!PyArg_ParseTuple(addresses, "KKKKK", &solve_address, &get_address, &close_address, &error_address, &set_address)) return NULL;
    if (!control || !solve_address || !get_address || !close_address || !error_address || !set_address
            || !PyCallable_Check(consume) || d->count) {
        PyErr_SetString(PyExc_ValueError, "invalid native clause solve"); return NULL;
    }
    solve_context context = {0}; context.decoder = d; context.consume = consume;
    context.measure = measure; context.set_error = (set_error_fn)(uintptr_t)set_address;
    context.lock = PyThread_allocate_lock();
    if (!context.lock) return PyErr_NoMemory();
    void *handle = NULL; unsigned result = 0; bool ok;
    char message[2048] = "native Clingo solve failed";
    Py_BEGIN_ALLOW_THREADS
    ok = ((solve_fn)(uintptr_t)solve_address)((void *)(uintptr_t)control, 0, NULL, 0, model_event, &context, &handle);
    if (ok) ok = ((get_fn)(uintptr_t)get_address)(handle, &result);
    if (!ok) {
        const char *error = ((error_message_fn)(uintptr_t)error_address)();
        if (error) { strncpy(message, error, sizeof(message)-1); message[sizeof(message)-1] = 0; }
    }
    if (handle && !((close_fn)(uintptr_t)close_address)(handle) && ok) {
        ok = false;
        const char *error = ((error_message_fn)(uintptr_t)error_address)();
        if (error) { strncpy(message, error, sizeof(message)-1); message[sizeof(message)-1] = 0; }
    }
    Py_END_ALLOW_THREADS
    PyThread_free_lock(context.lock);
    if (context.error_type) {
        d->count = 0;
        PyErr_Restore(context.error_type, context.error_value, context.error_traceback);
        return NULL;
    }
    if (!ok) { d->count = 0; PyErr_SetString(PyExc_RuntimeError, message); return NULL; }
    return Py_BuildValue("Kd", (unsigned long long)context.models, context.seconds);
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

/* Clingo 5.x public location ABI. Function pointers come from the loaded
   Clingo instance; no linking to a second runtime, and no text reparsing. */
typedef struct {
    const char *begin_file, *end_file;
    size_t begin_line, end_line, begin_column, end_column;
} location;
typedef bool (*ast_build_fn)(int, void **, ...);
typedef bool (*ast_string_fn)(const void *, char *, size_t);
typedef bool (*ast_size_fn)(const void *, size_t *);
typedef void (*ast_release_fn)(void *);
typedef struct {
    ast_build_fn build; ast_string_fn string; ast_size_fn size; ast_release_fn release;
    int rule_type; location loc; size_t body_capacity, text_capacity;
    void **body; char *text;
} renderer;
static void destroy_renderer(PyObject *capsule) {
    renderer *r = PyCapsule_GetPointer(capsule, "gentians.renderer");
    if (r) { free(r->body); free(r->text); free(r); }
}
static PyObject *prepare_renderer(PyObject *self, PyObject *args) {
    unsigned long long build, string, size, release; int rule_type;
    if (!PyArg_ParseTuple(args, "KKKKi", &build, &string, &size, &release, &rule_type)) return NULL;
    if (!build || !string || !size || !release) { PyErr_SetString(PyExc_ValueError, "missing Clingo function"); return NULL; }
    renderer *r = calloc(1, sizeof(renderer));
    if (!r) return PyErr_NoMemory();
    r->build = (ast_build_fn)(uintptr_t)build; r->string = (ast_string_fn)(uintptr_t)string;
    r->size = (ast_size_fn)(uintptr_t)size; r->release = (ast_release_fn)(uintptr_t)release;
    r->rule_type = rule_type; r->loc = (location){"<gentians>", "<gentians>", 1, 1, 1, 1};
    r->body_capacity = 16; r->text_capacity = 1024;
    r->body = malloc(r->body_capacity * sizeof(void *)); r->text = malloc(r->text_capacity);
    if (!r->body || !r->text) { free(r->body); free(r->text); free(r); return PyErr_NoMemory(); }
    PyObject *capsule = PyCapsule_New(r, "gentians.renderer", destroy_renderer);
    if (!capsule) { free(r->body); free(r->text); free(r); }
    return capsule;
}
static PyObject *render_one(renderer *r, PyObject *parts) {
    unsigned long long head; PyObject *body;
    if (!PyArg_ParseTuple(parts, "KO", &head, &body)) return NULL;
    if (!head || !PyTuple_Check(body)) { PyErr_SetString(PyExc_ValueError, "invalid native rule parts"); return NULL; }
    Py_ssize_t count = PyTuple_GET_SIZE(body);
    if ((size_t)count > r->body_capacity) {
        size_t capacity = (size_t)count > r->body_capacity * 2 ? (size_t)count : r->body_capacity * 2;
        void **replacement = realloc(r->body, capacity * sizeof(void *));
        if (!replacement) return PyErr_NoMemory();
        r->body = replacement; r->body_capacity = capacity;
    }
    for (Py_ssize_t i = 0; i < count; ++i) {
        r->body[i] = (void *)(uintptr_t)PyLong_AsUnsignedLongLong(PyTuple_GET_ITEM(body, i));
        if (PyErr_Occurred()) return NULL;
        if (!r->body[i]) { PyErr_SetString(PyExc_ValueError, "missing native body literal"); return NULL; }
    }
    void *rule = NULL;
    if (!r->build(r->rule_type, &rule, r->loc, (void *)(uintptr_t)head, r->body, (size_t)count)) {
        PyErr_SetString(PyExc_RuntimeError, "Clingo could not build native clause"); return NULL;
    }
    if (!r->string(rule, r->text, r->text_capacity)) {
        size_t needed;
        if (!r->size(rule, &needed) || needed <= r->text_capacity) goto clingo_error;
        size_t capacity = needed > r->text_capacity * 2 ? needed : r->text_capacity * 2;
        char *replacement = realloc(r->text, capacity);
        if (!replacement) { r->release(rule); return PyErr_NoMemory(); }
        r->text = replacement; r->text_capacity = capacity;
        if (!r->string(rule, r->text, capacity)) goto clingo_error;
    }
    PyObject *text = PyUnicode_DecodeUTF8(r->text, (Py_ssize_t)strlen(r->text), "strict");
    r->release(rule); return text;
clingo_error:
    r->release(rule); PyErr_SetString(PyExc_RuntimeError, "Clingo could not format native clause"); return NULL;
}
static PyObject *render_rules(PyObject *self, PyObject *args) {
    PyObject *capsule, *parts;
    if (!PyArg_ParseTuple(args, "OO", &capsule, &parts)) return NULL;
    if (!PyTuple_Check(parts)) { PyErr_SetString(PyExc_ValueError, "native rules must be a tuple"); return NULL; }
    renderer *r = PyCapsule_GetPointer(capsule, "gentians.renderer");
    if (!r) return NULL;
    Py_ssize_t count = PyTuple_GET_SIZE(parts); PyObject *result = PyTuple_New(count);
    if (!result) return NULL;
    for (Py_ssize_t i = 0; i < count; ++i) {
        PyObject *text = render_one(r, PyTuple_GET_ITEM(parts, i));
        if (!text) { Py_DECREF(result); return NULL; }
        PyTuple_SET_ITEM(result, i, text);
    }
    return result;
}

static PyMethodDef methods[] = {
    {"create", create, METH_VARARGS, "Prepare a Control-owned numeric lookup."},
    {"push", push, METH_VARARGS, "Copy one live model; return a block when full."},
    {"flush", flush, METH_O, "Return the final owned block."},
    {"solve", solve_records, METH_VARARGS, "Capture native model events and deliver owned blocks."},
    {"prepare_decode", prepare_decode, METH_VARARGS, "Compile owned block decoding layouts."},
    {"decode_block", decode_block, METH_VARARGS, "Materialize immutable values from an owned block."},
    {"prepare_renderer", prepare_renderer, METH_VARARGS, "Bind the loaded Clingo AST API."},
    {"render_rules", render_rules, METH_VARARGS, "Build, format and release native rules."},
    {NULL, NULL, 0, NULL}
};
static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "_records", NULL, -1, methods};
PyMODINIT_FUNC PyInit__records(void) { return PyModule_Create(&module); }
