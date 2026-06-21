/* malformed_bytecode.c — Malformed input yields a DEFINED error, never a crash.
 *
 * A host should never assume the bytecode it hands the engine is well-formed
 * (truncated downloads, wrong files, bit-rot). The engine treats malformed
 * bytecode as a defined error condition: ax_check_bytecode_compatibility returns
 * a non-OK AXStatus and ax_eval_bytecode returns a non-OK AXErrorCode — it does
 * not crash or invoke undefined behavior.
 *
 * This example feeds several malformed buffers and asserts each is rejected with
 * a defined (non-OK) result. The specific code may differ per input; the contract
 * is "defined and non-OK", which is what we assert.
 */
#include <stdio.h>
#include <string.h>

#include "axiom/ruledsl_c.h"

struct sample {
    const char* name;
    const unsigned char* data;
    size_t size;
};

int main(void)
{
    char err[256] = {0};
    AXCompiler* compiler = ax_compiler_create();
    if (!compiler || !ax_compiler_build(compiler, err, sizeof err)) {
        fprintf(stderr, "compiler build failed: %s\n", err[0] ? err : "no detail");
        return 1;
    }

    static const unsigned char junk[32] = {
        0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB,
        0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB,
        0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB,
        0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB, 0xAB
    };
    static const unsigned char truncated[4] = {0x41, 0x58, 0x42, 0x43 }; /* looks like a magic, nothing after */
    static const unsigned char one_byte[1] = {0x00};

    const struct sample samples[] = {
        {"empty (NULL, 0)",      NULL,      0},
        {"single zero byte",     one_byte,  sizeof one_byte},
        {"truncated header",     truncated, sizeof truncated},
        {"wrong-magic garbage",  junk,      sizeof junk},
    };

    int rc = 0;
    for (size_t i = 0; i < sizeof samples / sizeof samples[0]; ++i) {
        const struct sample* s = &samples[i];

        /* 1) Compatibility check must give a defined, non-OK status. */
        AXCompatibilityInfo info = AX_COMPATIBILITY_INFO_INIT;
        AXStatus st = ax_check_bytecode_compatibility(s->data, s->size, &info);

        /* 2) Evaluation must give a defined, non-OK error code (no crash). */
        AXBytecode bc = { (unsigned char*)s->data, s->size };
        AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
        AXDecision decision = AX_DECISION_INIT;
        memset(err, 0, sizeof err);
        AXErrorCode code = ax_eval_bytecode(compiler, &bc, NULL, 0, &opts, &decision, err, sizeof err);

        printf("%-22s -> compat_status=%d eval_code=%d (%s)\n",
               s->name, (int)st, (int)code, ax_error_to_string(code));

        if (st == AX_STATUS_OK) {
            fprintf(stderr, "FAIL: malformed input '%s' reported AX_STATUS_OK\n", s->name);
            rc = 1;
        }
        if (code == AX_ERR_OK) {
            fprintf(stderr, "FAIL: malformed input '%s' evaluated as AX_ERR_OK\n", s->name);
            rc = 1;
        }
        ax_decision_reset(&decision);
        ax_clear_last_error();
    }

    ax_compiler_destroy(compiler);
    if (rc == 0)
        printf("MALFORMED_REJECTED_OK\n");
    return rc;
}
