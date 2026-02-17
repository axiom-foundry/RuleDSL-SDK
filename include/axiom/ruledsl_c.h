#pragma once
// Public C API for embedding the RuleDSL engine.
#include <stddef.h>
#include <stdint.h>
#include "axiom/export.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct AXCompiler AXCompiler;

typedef enum AXValueType {
    AX_VALUE_MISSING = 0,
    AX_VALUE_NUMBER = 1,
    AX_VALUE_STRING = 2,
    AX_VALUE_IDENT = 3,
    AX_VALUE_BOOL = 4
} AXValueType;

typedef enum AXActionType {
    AX_ACTION_ALLOW = 0,
    AX_ACTION_DECLINE = 1,
    AX_ACTION_REVIEW = 2,
    AX_ACTION_LIMIT = 3
} AXActionType;

// AXErrorCode numeric contract (append-only):
// 0       : success
// 1-63    : user/integration failures
// 64-127  : artifact failures (reserved for growth)
// 128-191 : engine/runtime failures (reserved for growth)
// 192-255 : reserved for future public expansion
// Existing values below are frozen and must never be renumbered.
typedef enum AXErrorCode {
    AX_ERR_OK = 0,
    AX_ERR_INVALID_ARGUMENT = 1,
    AX_ERR_COMPILE = 2,
    AX_ERR_VERIFY = 3,
    AX_ERR_MISSING_NOW_UTC_MS = 4,
    AX_ERR_NOW_UTC_MS_NOT_NUMBER = 5,
    AX_ERR_NON_FINITE = 6,
    AX_ERR_DIV_ZERO = 7,
    AX_ERR_CONCURRENT_COMPILER_USE = 8,
    AX_ERR_LIMIT_EXCEEDED = 9,
    AX_ERR_BAD_STRUCT_SIZE = 10,
    AX_ERR_RUNTIME = 11
} AXErrorCode;

#define AX_FIELD_NOW_UTC_MS "now_utc_ms"

typedef struct AXValue {
    AXValueType type;
    double number;
    const char* text;
    int boolean;
    const char* currency;
} AXValue;

typedef struct AXField {
    const char* name;
    AXValue value;
} AXField;

typedef struct AXBytecode {
    unsigned char* data;
    size_t size;
} AXBytecode;

typedef void (*AXTraceCallback)(void* user, const char* line);

typedef struct AXEvalOptions {
    uint32_t struct_size;
    AXTraceCallback trace_cb;
    void* trace_user;
    uint64_t reserved[4];
} AXEvalOptions;

// Caller-owned decision container.
// The SDK may allocate heap strings for currency/window_unit/rule_name.
// Use ax_decision_reset (or ax_decision_free for compatibility) before reusing or discarding the struct.
typedef struct AXDecision {
    uint32_t struct_size;
    int matched;
    AXActionType action_type;
    double amount;
    const char* currency;
    double window_count;
    const char* window_unit;
    const char* rule_name;
    uint64_t reserved[4];
} AXDecision;

#define AX_EVAL_OPTIONS_INIT { sizeof(AXEvalOptions), NULL, NULL, {0, 0, 0, 0} }
#define AX_DECISION_INIT { sizeof(AXDecision), 0, AX_ACTION_ALLOW, 0.0, NULL, 0.0, NULL, NULL, {0, 0, 0, 0} }

AXIOM_API AXCompiler* ax_compiler_create(void);
AXIOM_API void ax_compiler_destroy(AXCompiler* compiler);
AXIOM_API int ax_compiler_build(AXCompiler* compiler, char* err, size_t err_len);

AXIOM_API int ax_compile_to_bytecode(AXCompiler* compiler,
                                     const char* input,
                                     AXBytecode* out,
                                     char* err,
                                     size_t err_len);

AXIOM_API AXErrorCode ax_eval_bytecode(AXCompiler* compiler,
                                           const AXBytecode* bytecode,
                                           const AXField* fields,
                                           uint32_t field_count,
                                           const AXEvalOptions* options,
                                           AXDecision* out_decision,
                                           char* err,
                                           size_t err_len);

AXIOM_API void ax_bytecode_free(AXBytecode* bytecode);
// Deep-clear owned members in a caller-owned AXDecision. Does not free the AXDecision struct itself.
AXIOM_API void ax_decision_reset(AXDecision* decision);
// Backward-compatible alias of ax_decision_reset.
AXIOM_API void ax_decision_free(AXDecision* decision);
AXIOM_API void ax_free(void* ptr);
AXIOM_API const char* ax_version_string(void);
AXIOM_API const char* ax_error_to_string(AXErrorCode code);
AXIOM_API AXErrorCode ax_last_error_code(void);
AXIOM_API size_t ax_last_error_detail_utf8(char* buf, size_t cap);
AXIOM_API void ax_clear_last_error(void);

#ifdef __cplusplus
}
#endif
