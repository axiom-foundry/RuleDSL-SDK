# Integration Snippets (C API)

These snippets are intended as copy-paste starting points for host integrations.
API names match `SDK/Include/axiom/ruledsl_c.h`.

## 1) Minimal Happy Path (Load + Evaluate)

```c
#include <axiom/ruledsl_c.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static int read_file(const char* path, unsigned char** out_data, size_t* out_size) {
    FILE* f = fopen(path, "rb");
    long n = 0;
    unsigned char* buf = NULL;
    if (!f) return 0;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return 0; }
    n = ftell(f);
    if (n <= 0 || fseek(f, 0, SEEK_SET) != 0) { fclose(f); return 0; }
    buf = (unsigned char*)malloc((size_t)n);
    if (!buf) { fclose(f); return 0; }
    if (fread(buf, 1, (size_t)n, f) != (size_t)n) { free(buf); fclose(f); return 0; }
    fclose(f);
    *out_data = buf;
    *out_size = (size_t)n;
    return 1;
}

int main(int argc, char** argv) {
    AXCompiler* compiler = NULL;
    AXBytecode bytecode = {0};
    AXField fields[2] = {0};
    AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
    AXDecision decision = AX_DECISION_INIT;
    AXErrorCode rc = AX_ERR_RUNTIME;
    unsigned char* bc_bytes = NULL;
    size_t bc_size = 0;
    char err[256] = {0};

    if (argc != 2) return 1;
    if (!read_file(argv[1], &bc_bytes, &bc_size)) return 1;

    compiler = ax_compiler_create();
    if (!compiler) goto done;
    if (!ax_compiler_build(compiler, err, sizeof(err))) goto done;

    bytecode.data = bc_bytes;
    bytecode.size = bc_size;

    fields[0].name = "amount";
    fields[0].value.type = AX_VALUE_NUMBER;
    fields[0].value.number = 1250.0;
    fields[1].name = AX_FIELD_NOW_UTC_MS;
    fields[1].value.type = AX_VALUE_NUMBER;
    fields[1].value.number = 1730000000000.0;

    AXCompatibilityInfo compat = AX_COMPATIBILITY_INFO_INIT;
    AXStatus compat_status = ax_check_bytecode_compatibility(bytecode.data, bytecode.size, &compat);
    if (compat_status != AX_STATUS_OK) goto done;

    rc = ax_eval_bytecode(compiler, &bytecode, fields, 2, &opts, &decision, err, sizeof(err));
    if (rc == AX_ERR_OK) {
        printf("matched=%d action=%d rule=%s\n",
               decision.matched,
               (int)decision.action_type,
               decision.rule_name ? decision.rule_name : "<none>");
    }

done:
    ax_decision_reset(&decision);
    free(bc_bytes);
    if (compiler) ax_compiler_destroy(compiler);
    return (rc == AX_ERR_OK) ? 0 : 1;
}
```

## 2) Error Handling Pattern (Robust)

```c
#include <axiom/ruledsl_c.h>
#include <stdio.h>

static void log_ax_error(AXErrorCode rc) {
    AXErrorCode last = ax_last_error_code();
    size_t needed = ax_last_error_detail_utf8(NULL, 0);
    char detail[256] = {0};
    (void)ax_last_error_detail_utf8(detail, sizeof(detail));

    fprintf(stderr,
            "rc=%d(%s) last=%d(%s) detail_len=%zu detail=%s\n",
            (int)rc,
            ax_error_to_string(rc),
            (int)last,
            ax_error_to_string(last),
            needed,
            detail);

    /* Use numeric codes for logic; detail is for diagnostics only. */
    ax_clear_last_error();
}

int eval_checked(AXCompiler* compiler,
                 const AXBytecode* bytecode,
                 const AXField* fields,
                 uint32_t field_count,
                 AXDecision* out_decision) {
    AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
    char err[256] = {0};
    AXErrorCode rc = ax_eval_bytecode(compiler,
                                      bytecode,
                                      fields,
                                      field_count,
                                      &opts,
                                      out_decision,
                                      err,
                                      sizeof(err));
    if (rc != AX_ERR_OK) {
        log_ax_error(rc);
        return -1;
    }
    return 0;
}
```

## 3) Release Artifact Intake (Operational Safety)

```c
#include <axiom/ruledsl_c.h>
#include <stdio.h>
#include <stdlib.h>

static int run_release_gate(const char* release_dir, int require_signature) {
    char cmd[1024];
    int n;

    /* SHA256SUMS must be verified before loading bytecode. */
    if (require_signature) {
        n = snprintf(cmd,
                     sizeof(cmd),
                     "python Tools/release_gate/release_gate.py "
                     "--release-dir \"%s\" "
                     "--out-dir reports/release_gate/intake "
                     "--sig-file \"%s/SHA256SUMS.sig.json\" "
                     "--keyring docs/signing_keys.json --require-signature",
                     release_dir,
                     release_dir);
    } else {
        n = snprintf(cmd,
                     sizeof(cmd),
                     "python Tools/release_gate/release_gate.py "
                     "--release-dir \"%s\" "
                     "--out-dir reports/release_gate/intake",
                     release_dir);
    }
    if (n <= 0 || n >= (int)sizeof(cmd)) return -1;
    return (system(cmd) == 0) ? 0 : -1;
}

int intake_release(const char* release_dir, int require_signature) {
    const char* runtime = ax_version_string();
    if (!runtime || runtime[0] == '\0') {
        fprintf(stderr, "missing runtime version string\n");
        return -1;
    }

    if (run_release_gate(release_dir, require_signature) != 0) {
        fprintf(stderr, "release verification failed\n");
        return -1;
    }

    printf("release_intake_ok runtime=%s release=%s\n", runtime, release_dir);
    return 0;
}
```