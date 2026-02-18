#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "axiom/ruledsl_c.h"

static int load_file(const char* path, AXBytecode* out)
{
    FILE* f = fopen(path, "rb");
    long n;
    if (!f) {
        return 0;
    }
    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return 0;
    }
    n = ftell(f);
    if (n <= 0) {
        fclose(f);
        return 0;
    }
    if (fseek(f, 0, SEEK_SET) != 0) {
        fclose(f);
        return 0;
    }
    out->data = (unsigned char*)malloc((size_t)n);
    if (!out->data) {
        fclose(f);
        return 0;
    }
    out->size = (size_t)n;
    if (fread(out->data, 1, out->size, f) != out->size) {
        free(out->data);
        out->data = NULL;
        out->size = 0;
        fclose(f);
        return 0;
    }
    fclose(f);
    return 1;
}

int main(int argc, char** argv)
{
    AXCompiler* compiler = NULL;
    AXBytecode bytecode = {0};
    AXEvalOptions options = AX_EVAL_OPTIONS_INIT;
    AXDecision decision = AX_DECISION_INIT;
    AXField fields[2];
    char err[256] = {0};

    if (argc != 2) {
        fprintf(stderr, "usage: %s <rules.axbc>\n", argv[0]);
        return 2;
    }

    compiler = ax_compiler_create();
    if (!compiler || !ax_compiler_build(compiler, err, sizeof(err))) {
        fprintf(stderr, "compiler init failed: %s\n", err[0] ? err : "no detail");
        return 1;
    }

    if (!load_file(argv[1], &bytecode)) {
        fprintf(stderr, "failed to read bytecode: %s\n", argv[1]);
        ax_compiler_destroy(compiler);
        return 1;
    }

    memset(fields, 0, sizeof(fields));
    fields[0].name = "amount";
    fields[0].value.type = AX_VALUE_NUMBER;
    fields[0].value.number = 1200.0;

    fields[1].name = AX_FIELD_NOW_UTC_MS;
    fields[1].value.type = AX_VALUE_NUMBER;
    fields[1].value.number = 1700000000000.0;

    if (ax_eval_bytecode(compiler, &bytecode, fields, 2, &options, &decision, err, sizeof(err)) != AX_ERR_OK) {
        fprintf(stderr, "ax_eval_bytecode failed: %s\n", err[0] ? err : "no detail");
        free(bytecode.data);
        bytecode.data = NULL;
        bytecode.size = 0;
        ax_compiler_destroy(compiler);
        return 1;
    }

    if (!decision.matched || decision.action_type != AX_ACTION_DECLINE) {
        fprintf(stderr, "unexpected action_type=%d matched=%d\n", (int)decision.action_type, decision.matched);
        ax_decision_reset(&decision);
        free(bytecode.data);
        bytecode.data = NULL;
        bytecode.size = 0;
        ax_compiler_destroy(compiler);
        return 1;
    }

    printf("ACTION=DECLINE\n");
    printf("RESULT=OK\n");

    ax_decision_reset(&decision);
    free(bytecode.data);
    bytecode.data = NULL;
    bytecode.size = 0;
    ax_compiler_destroy(compiler);
    return 0;
}
