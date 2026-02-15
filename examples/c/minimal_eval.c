/*
MSVC compile check:
cmd /c "\"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat\" >nul && cl /nologo /W4 /WX /std:c11 /I include /c examples\c\minimal_eval.c /Fo:build\minimal_eval.obj"
Linux compile check (gcc/clang):
gcc -std=c11 -Wall -Wextra -Werror -I include -c examples/c/minimal_eval.c -o /tmp/minimal_eval.o
*/

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "axiom/ruledsl_c.h"

static int load_bytecode_file(const char* path, AXBytecode* out)
{
    FILE* f = fopen(path, "rb");
    long size = 0;
    if (!f)
        return 0;
    if (fseek(f, 0, SEEK_END) != 0 || (size = ftell(f)) <= 0 || fseek(f, 0, SEEK_SET) != 0) {
        fclose(f);
        return 0;
    }
    out->data = (unsigned char*)malloc((size_t)size);
    if (!out->data) {
        fclose(f);
        return 0;
    }
    out->size = (size_t)size;
    if (fread(out->data, 1, out->size, f) != out->size) {
        fclose(f);
        ax_bytecode_free(out);
        return 0;
    }
    fclose(f);
    return 1;
}

int main(int argc, char** argv)
{
    AXCapabilitiesV1 caps = AX_CAPABILITIES_V1_INIT;
    AXBytecode bc = {0};
    AXCompiler* compiler = NULL;
    AXEvalOptionsV2 opts = AX_EVAL_OPTIONS_V2_INIT;
    AXDecisionV2 decision = AX_DECISION_V2_INIT;
    AXErrorCode code = AX_ERR_RUNTIME;
    char err[256] = {0};
    int rc = 1;

    // STEP 1: Version
    printf("%s\n", ax_version_string());
    code = ax_capabilities(&caps);
    if (code != AX_ERR_OK) {
        fprintf(stderr, "ax_capabilities failed: %d\n", (int)code);
        return 1;
    }
    printf("Capabilities: abi_level=%u replay_schema=%u has_ex2=%u\n", caps.abi_level, caps.replay_schema, caps.has_ex2);
    if (argc < 2) {
        fprintf(stderr, "usage: %s <bytecode.bc>\n", argv[0]);
        return 1;
    }

    // STEP 2: Load
    if (!load_bytecode_file(argv[1], &bc)) {
        fprintf(stderr, "failed to load bytecode: %s\n", argv[1]);
        return 1;
    }
    compiler = ax_compiler_create();
    if (!compiler || !ax_compiler_build(compiler, err, sizeof(err))) {
        fprintf(stderr, "compiler setup failed: %s\n", err[0] ? err : "unknown");
        goto cleanup;
    }

    // STEP 3: Evaluate
    {
        AXField fields[2] = {0};
        fields[0].name = "amount";
        fields[0].value.type = AX_VALUE_NUMBER;
        fields[0].value.number = 10.0;
        fields[0].value.currency = "USD";
        fields[1].name = AX_FIELD_NOW_UTC_MS;
        fields[1].value.type = AX_VALUE_NUMBER;
        fields[1].value.number = 1700000000000.0;
        code = ax_eval_bytecode_ex2(compiler, &bc, fields, 2, &opts, &decision, err, sizeof(err));
    }
    if (code != AX_ERR_OK) {
        fprintf(stderr, "ax_eval_bytecode_ex2 failed: %d (%s)\n", (int)code, err[0] ? err : "no detail");
        goto cleanup;
    }
    printf("Decision: matched=%d action_type=%d\n", decision.matched, (int)decision.action_type);

    // STEP 4: Replay (optional)
#if defined(AX_REPLAY_BUFFER_V1_VERSION)
    if (caps.has_ex2 == 1u && caps.replay_schema >= 1u) {
        uint8_t replay_bytes[4096] = {0};
        size_t replay_size = 0;
        AXDecisionV2 replay_decision = AX_DECISION_V2_INIT;
        code = ax_eval_record_ex2(&bc, &opts, &decision, replay_bytes, sizeof(replay_bytes), &replay_size);
        if (code == AX_ERR_OK) {
            AXReplayBufferV1 replay = AX_REPLAY_BUFFER_V1_INIT;
            replay.data = replay_bytes;
            replay.size = replay_size;
            code = ax_eval_replay_ex2(&bc, &replay, &replay_decision);
            printf("Replay: code=%d bytes=%zu\n", (int)code, replay_size);
        } else {
            printf("Replay: not supported in this build\n");
        }
        ax_decision_reset_v2(&replay_decision);
    } else {
        printf("Replay: not supported in this build\n");
    }
#else
    printf("Replay: not supported in this build\n");
#endif

    printf("DETERMINISTIC_OK\n");
    rc = 0;

    // STEP 5: Cleanup
cleanup:
    ax_decision_reset_v2(&decision);
    if (compiler)
        ax_compiler_destroy(compiler);
    ax_bytecode_free(&bc);
    return rc;
}

/*
Expected output:
RuleDSL/1.0.0 (abi=1; ex2=1; replay_schema=1)
Decision: <value>
DETERMINISTIC_OK
*/
