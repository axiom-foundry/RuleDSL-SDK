#pragma once
// Public C API for embedding the RuleDSL engine.
#include <stddef.h>
#include <stdint.h>
#include <string.h>
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

/*
AXErrorCode numeric registry policy (frozen):
  0       : AX_ERR_OK (success)
  1-99    : Core engine / legacy compatibility codes
  100-199 : Reserved for parser/compile errors (future additions)
  200-299 : Reserved for runtime evaluation errors (future additions)
  300-399 : Reserved for memory/resource errors (future additions)
  900-999 : Reserved for future expansion

Do not renumber existing values. Additions must use explicit numeric assignments
in the designated range.
*/
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

#if defined(__cplusplus)
static_assert(AX_ERR_OK == 0, "AX_ERR_OK must remain 0");
static_assert(AX_ERR_OK < AX_ERR_INVALID_ARGUMENT &&
                  AX_ERR_INVALID_ARGUMENT < AX_ERR_COMPILE &&
                  AX_ERR_COMPILE < AX_ERR_VERIFY &&
                  AX_ERR_VERIFY < AX_ERR_MISSING_NOW_UTC_MS &&
                  AX_ERR_MISSING_NOW_UTC_MS < AX_ERR_NOW_UTC_MS_NOT_NUMBER &&
                  AX_ERR_NOW_UTC_MS_NOT_NUMBER < AX_ERR_NON_FINITE &&
                  AX_ERR_NON_FINITE < AX_ERR_DIV_ZERO &&
                  AX_ERR_DIV_ZERO < AX_ERR_CONCURRENT_COMPILER_USE &&
                  AX_ERR_CONCURRENT_COMPILER_USE < AX_ERR_LIMIT_EXCEEDED &&
                  AX_ERR_LIMIT_EXCEEDED < AX_ERR_BAD_STRUCT_SIZE &&
                  AX_ERR_BAD_STRUCT_SIZE < AX_ERR_RUNTIME,
              "AXErrorCode values must remain unique and strictly increasing");
static_assert(AX_ERR_RUNTIME < 1000, "AXErrorCode values must remain below 1000");
#elif defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L
_Static_assert(AX_ERR_OK == 0, "AX_ERR_OK must remain 0");
_Static_assert(AX_ERR_OK < AX_ERR_INVALID_ARGUMENT &&
                   AX_ERR_INVALID_ARGUMENT < AX_ERR_COMPILE &&
                   AX_ERR_COMPILE < AX_ERR_VERIFY &&
                   AX_ERR_VERIFY < AX_ERR_MISSING_NOW_UTC_MS &&
                   AX_ERR_MISSING_NOW_UTC_MS < AX_ERR_NOW_UTC_MS_NOT_NUMBER &&
                   AX_ERR_NOW_UTC_MS_NOT_NUMBER < AX_ERR_NON_FINITE &&
                   AX_ERR_NON_FINITE < AX_ERR_DIV_ZERO &&
                   AX_ERR_DIV_ZERO < AX_ERR_CONCURRENT_COMPILER_USE &&
                   AX_ERR_CONCURRENT_COMPILER_USE < AX_ERR_LIMIT_EXCEEDED &&
                   AX_ERR_LIMIT_EXCEEDED < AX_ERR_BAD_STRUCT_SIZE &&
                   AX_ERR_BAD_STRUCT_SIZE < AX_ERR_RUNTIME,
               "AXErrorCode values must remain unique and strictly increasing");
_Static_assert(AX_ERR_RUNTIME < 1000, "AXErrorCode values must remain below 1000");
#endif

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

#define AX_EVAL_OPTIONS_V2_VERSION 1u
#define AX_DECISION_V2_VERSION 1u

typedef struct AXEvalOptionsV2 {
    uint32_t struct_size;
    uint32_t version;
    AXTraceCallback trace_cb;
    void* trace_user;
    uint64_t reserved[4];
} AXEvalOptionsV2;

typedef struct AXDecisionV2 {
    uint32_t struct_size;
    uint32_t version;
    int matched;
    AXActionType action_type;
    double amount;
    const char* currency;
    double window_count;
    const char* window_unit;
    const char* rule_name;
    uint64_t reserved[4];
} AXDecisionV2;

#define AX_REPLAY_BUFFER_V1_VERSION 1u

typedef struct AXReplayBufferV1 {
    uint32_t struct_size;
    uint32_t version;
    uint64_t reserved[4];
    const uint8_t* data;
    size_t size;
} AXReplayBufferV1;

#define AX_CAPABILITIES_V1_VERSION 1u

typedef struct AXCapabilitiesV1 {
    uint32_t struct_size;
    uint32_t version;
    uint64_t reserved[4];
    uint32_t abi_level;
    uint32_t has_ex2;
    uint32_t replay_schema;
    uint32_t reserved32;
} AXCapabilitiesV1;

#define AX_EVAL_OPTIONS_V2_INIT \
    { sizeof(AXEvalOptionsV2), AX_EVAL_OPTIONS_V2_VERSION, NULL, NULL, {0, 0, 0, 0} }

#define AX_DECISION_V2_INIT \
    { sizeof(AXDecisionV2), AX_DECISION_V2_VERSION, 0, AX_ACTION_ALLOW, 0.0, NULL, 0.0, NULL, NULL, {0, 0, 0, 0} }

#define AX_REPLAY_BUFFER_V1_INIT \
    { sizeof(AXReplayBufferV1), AX_REPLAY_BUFFER_V1_VERSION, {0, 0, 0, 0}, NULL, 0 }

#define AX_CAPABILITIES_V1_INIT \
    { sizeof(AXCapabilitiesV1), AX_CAPABILITIES_V1_VERSION, {0, 0, 0, 0}, 0, 0, 0, 0 }

#define AX_INIT_AXEvalOptionsV2(ptr)                                                   \
    do {                                                                                \
        if ((ptr) != NULL) {                                                            \
            memset((ptr), 0, sizeof(AXEvalOptionsV2));                                 \
            (ptr)->struct_size = (uint32_t)sizeof(AXEvalOptionsV2);                    \
            (ptr)->version = AX_EVAL_OPTIONS_V2_VERSION;                                \
        }                                                                               \
    } while (0)

#define AX_INIT_AXDecisionV2(ptr)                                                       \
    do {                                                                                \
        if ((ptr) != NULL) {                                                            \
            memset((ptr), 0, sizeof(AXDecisionV2));                                     \
            (ptr)->struct_size = (uint32_t)sizeof(AXDecisionV2);                        \
            (ptr)->version = AX_DECISION_V2_VERSION;                                    \
            (ptr)->action_type = AX_ACTION_ALLOW;                                       \
        }                                                                               \
    } while (0)

#define AX_INIT_AXReplayBufferV1(ptr)                                                   \
    do {                                                                                \
        if ((ptr) != NULL) {                                                            \
            memset((ptr), 0, sizeof(AXReplayBufferV1));                                 \
            (ptr)->struct_size = (uint32_t)sizeof(AXReplayBufferV1);                    \
            (ptr)->version = AX_REPLAY_BUFFER_V1_VERSION;                               \
        }                                                                               \
    } while (0)

#define AX_INIT_AXCapabilitiesV1(ptr)                                                  \
    do {                                                                                \
        if ((ptr) != NULL) {                                                            \
            memset((ptr), 0, sizeof(AXCapabilitiesV1));                                 \
            (ptr)->struct_size = (uint32_t)sizeof(AXCapabilitiesV1);                    \
            (ptr)->version = AX_CAPABILITIES_V1_VERSION;                                \
        }                                                                               \
    } while (0)

// Returned pointer is library-owned static storage; caller must not free it.
AXIOM_API const char* ax_version_string(void);
AXIOM_API AXErrorCode ax_capabilities(AXCapabilitiesV1* out_capabilities);

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

AXIOM_API AXErrorCode ax_eval_bytecode_ex2(AXCompiler* compiler,
                                           const AXBytecode* bytecode,
                                           const AXField* fields,
                                           uint32_t field_count,
                                           const AXEvalOptionsV2* options,
                                           AXDecisionV2* out_decision,
                                           char* err,
                                           size_t err_len);

AXIOM_API AXErrorCode ax_eval_record_ex2(const AXBytecode* bytecode,
                                         const AXEvalOptionsV2* options,
                                         AXDecisionV2* out_decision,
                                         uint8_t* out_buffer,
                                         size_t buffer_capacity,
                                         size_t* out_size);

AXIOM_API AXErrorCode ax_eval_replay_ex2(const AXBytecode* bytecode,
                                         const AXReplayBufferV1* replay,
                                         AXDecisionV2* out_decision);

AXIOM_API void ax_bytecode_free(AXBytecode* bytecode);
// Deep-clear owned members in a caller-owned AXDecision. Does not free the AXDecision struct itself.
AXIOM_API void ax_decision_reset(AXDecision* decision);
// Backward-compatible alias of ax_decision_reset.
AXIOM_API void ax_decision_free(AXDecision* decision);
// Deep-clear owned members in a caller-owned AXDecisionV2. Does not free the struct itself.
AXIOM_API void ax_decision_reset_v2(AXDecisionV2* decision);
AXIOM_API void ax_free(void* ptr);

#ifdef __cplusplus
}
#endif
