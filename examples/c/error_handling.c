/* error_handling.c — Demonstrates error handling with ax_last_error_detail_utf8.
 *
 * Shows how to:
 * 1. Check ax_eval_bytecode return code
 * 2. Read the inline error buffer (err parameter)
 * 3. Read the thread-local error detail for richer diagnostics
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "axiom/ruledsl_c.h"

int main(void)
{
    AXCompiler* compiler;
    AXBytecode bc = {0};
    AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
    AXDecision decision = AX_DECISION_INIT;
    char err[256] = {0};

    compiler = ax_compiler_create();
    if (!compiler || !ax_compiler_build(compiler, err, sizeof(err))) {
        fprintf(stderr, "compiler build failed: %s\n", err[0] ? err : "no detail");
        return 1;
    }

    /* Attempt to compile invalid rule source */
    if (!ax_compile_to_bytecode(compiler, "rule bad { when ; then allow; }", &bc, err, sizeof(err))) {
        char detail[512] = {0};
        ax_last_error_detail_utf8(detail, sizeof(detail));
        fprintf(stderr, "Compile error (expected): %s\n", err[0] ? err : "no detail");
        if (detail[0])
            fprintf(stderr, "Detail: %s\n", detail);
        ax_clear_last_error();
        printf("COMPILE_ERROR_CAUGHT=OK\n");
    }

    /* Attempt eval with empty bytecode — triggers error */
    {
        AXErrorCode code;
        memset(err, 0, sizeof(err));
        code = ax_eval_bytecode(compiler, &bc, NULL, 0, &opts, &decision, err, sizeof(err));
        if (code != AX_ERR_OK) {
            char detail[512] = {0};
            ax_last_error_detail_utf8(detail, sizeof(detail));
            fprintf(stderr, "Eval error (expected): code=%d (%s) msg=%s\n",
                    (int)code, ax_error_to_string(code), err[0] ? err : "no detail");
            if (detail[0])
                fprintf(stderr, "Detail: %s\n", detail);
            ax_clear_last_error();
            printf("EVAL_ERROR_CAUGHT=OK\n");
        }
    }

    ax_compiler_destroy(compiler);
    printf("RESULT=OK\n");
    return 0;
}
