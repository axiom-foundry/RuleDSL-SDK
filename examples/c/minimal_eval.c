#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "axiom/ruledsl_c.h"

static int load_file(const char* path, AXBytecode* out)
{
    FILE* f = fopen(path, "rb");
    if (!f) return 0;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return 0; }
    long n = ftell(f);
    if (n <= 0) { fclose(f); return 0; }
    if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); return 0; }
    out->data = (unsigned char*)malloc((size_t)n);
    if (!out->data) { fclose(f); return 0; }
    out->size = (size_t)n;
    if (fread(out->data, 1, out->size, f) != out->size) {
        fclose(f);
        free(out->data);
        out->data = NULL;
        out->size = 0;
        return 0;
    }
    fclose(f);
    return 1;
}

int main(int argc, char** argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: minimal_eval <bytecode.bc>\n");
        return 2;
    }

    AXCompiler* compiler = ax_compiler_create();
    AXBytecode bc = {0};
    AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
    AXDecision decision = AX_DECISION_INIT;
    AXField fields[2];
    char err[256] = {0};

    if (!compiler || !ax_compiler_build(compiler, err, sizeof(err))) {
        fprintf(stderr, "compiler build failed: %s\n", err[0] ? err : "no detail");
        return 1;
    }
    if (!load_file(argv[1], &bc)) {
        fprintf(stderr, "failed to load bytecode: %s\n", argv[1]);
        ax_compiler_destroy(compiler);
        return 1;
    }


    AXCompatibilityInfo compatibility = AX_COMPATIBILITY_INFO_INIT;
    AXStatus compat_status = ax_check_bytecode_compatibility(bytecode.data, bytecode.size, &compatibility);
    if (compat_status != AX_STATUS_OK) {
        fprintf(stderr, "ax_check_bytecode_compatibility failed: status=%d axbc=%u lang=%u.%u abi=%u\n",
                (int)compat_status,
                (unsigned)compatibility.axbc_version,
                (unsigned)compatibility.lang_major,
                (unsigned)compatibility.lang_minor,
                (unsigned)compatibility.minimum_engine_abi);
        free(bytecode.data);
        bytecode.data = NULL;
        bytecode.size = 0;
        ax_compiler_destroy(compiler);
        return 1;
    }
    memset(fields, 0, sizeof(fields));
    fields[0].name = "amount";
    fields[0].value.type = AX_VALUE_NUMBER;
    fields[0].value.number = 100.0;
    fields[0].value.currency = "TRY";
    fields[1].name = AX_FIELD_NOW_UTC_MS;
    fields[1].value.type = AX_VALUE_NUMBER;
    fields[1].value.number = 1700000000000.0;

    printf("%s\n", ax_version_string());
    if (ax_eval_bytecode(compiler, &bc, fields, 2, &opts, &decision, err, sizeof(err)) != AX_ERR_OK) {
        fprintf(stderr, "ax_eval_bytecode failed: %s\n", err[0] ? err : "no detail");
        ax_bytecode_free(&bc);
        ax_compiler_destroy(compiler);
        return 1;
    }

    printf("Decision: matched=%d action_type=%d\n", decision.matched, (int)decision.action_type);
    printf("DETERMINISTIC_OK\n");

    ax_decision_reset(&decision);
    ax_bytecode_free(&bc);
    ax_compiler_destroy(compiler);
    return 0;
}
