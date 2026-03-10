/* output_fields.c — Demonstrates reading output fields from THEN clause assignments.
 *
 * After ax_eval_bytecode, output fields (e.g., risk_score, reason) can be
 * queried via ax_eval_output_field_count / ax_eval_output_field_at.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "axiom/ruledsl_c.h"

static int load_file(const char* path, AXBytecode* out)
{
    FILE* f = fopen(path, "rb");
    long n;
    if (!f) return 0;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return 0; }
    n = ftell(f);
    if (n <= 0) { fclose(f); return 0; }
    if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); return 0; }
    out->data = (unsigned char*)malloc((size_t)n);
    if (!out->data) { fclose(f); return 0; }
    out->size = (size_t)n;
    if (fread(out->data, 1, out->size, f) != out->size) {
        free(out->data); out->data = NULL; out->size = 0;
        fclose(f); return 0;
    }
    fclose(f);
    return 1;
}

int main(int argc, char** argv)
{
    AXCompiler* compiler;
    AXBytecode bc = {0};
    AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
    AXDecision decision = AX_DECISION_INIT;
    AXField fields[2];
    char err[256] = {0};
    uint32_t i, count;

    if (argc < 2) {
        fprintf(stderr, "usage: output_fields <bytecode.axbc>\n");
        return 2;
    }

    compiler = ax_compiler_create();
    if (!compiler || !ax_compiler_build(compiler, err, sizeof(err))) {
        fprintf(stderr, "compiler build failed: %s\n", err[0] ? err : "no detail");
        return 1;
    }

    if (!load_file(argv[1], &bc)) {
        fprintf(stderr, "failed to load bytecode: %s\n", argv[1]);
        ax_compiler_destroy(compiler);
        return 1;
    }

    memset(fields, 0, sizeof(fields));
    fields[0].name = "amount";
    fields[0].value.type = AX_VALUE_NUMBER;
    fields[0].value.number = 5000.0;
    fields[1].name = AX_FIELD_NOW_UTC_MS;
    fields[1].value.type = AX_VALUE_NUMBER;
    fields[1].value.number = 1700000000000.0;

    if (ax_eval_bytecode(compiler, &bc, fields, 2, &opts, &decision, err, sizeof(err)) != AX_ERR_OK) {
        fprintf(stderr, "eval failed: %s\n", err[0] ? err : "no detail");
        ax_bytecode_free(&bc);
        ax_compiler_destroy(compiler);
        return 1;
    }

    printf("matched=%d action=%d rule=%s\n",
           decision.matched, (int)decision.action_type,
           decision.rule_name ? decision.rule_name : "(none)");

    /* Read output fields assigned in THEN clauses (e.g., risk_score, reason) */
    count = ax_eval_output_field_count(compiler);
    printf("output_fields=%u\n", (unsigned)count);
    for (i = 0; i < count; i++) {
        const char* name = NULL;
        AXValue value;
        memset(&value, 0, sizeof(value));
        if (ax_eval_output_field_at(compiler, i, &name, &value) == AX_ERR_OK && name) {
            printf("  %s = ", name);
            switch (value.type) {
                case AX_VALUE_NUMBER: printf("%.6g\n", value.number); break;
                case AX_VALUE_STRING: printf("\"%s\"\n", value.text ? value.text : ""); break;
                case AX_VALUE_BOOL:   printf("%s\n", value.boolean ? "true" : "false"); break;
                default:              printf("(missing)\n"); break;
            }
        }
    }

    ax_decision_reset(&decision);
    ax_bytecode_free(&bc);
    ax_compiler_destroy(compiler);
    return 0;
}
