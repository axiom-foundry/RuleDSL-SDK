/* batch_eval.c — Demonstrates compile-once, eval-many pattern.
 *
 * This is the most common production pattern:
 * 1. Create compiler once
 * 2. Compile rules to bytecode once (or load from file)
 * 3. Evaluate many transactions against the same bytecode
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "axiom/ruledsl_c.h"

static const char* action_name(AXActionType t)
{
    switch (t) {
        case AX_ACTION_ALLOW:   return "ALLOW";
        case AX_ACTION_DECLINE: return "DECLINE";
        case AX_ACTION_REVIEW:  return "REVIEW";
        case AX_ACTION_LIMIT:   return "LIMIT";
        default:                return "UNKNOWN";
    }
}

int main(void)
{
    AXCompiler* compiler;
    AXBytecode bc = {0};
    AXEvalOptions opts = AX_EVAL_OPTIONS_INIT;
    char err[512] = {0};

    /* Test amounts — each should produce a different decision */
    double amounts[] = { 100.0, 750.0, 5000.0, 15000.0 };
    int num_txns = (int)(sizeof(amounts) / sizeof(amounts[0]));
    int i;

    const char* rule_source =
        "rule decline_high priority 100 {\n"
        "  when amount > 10000;\n"
        "  then risk_score = 95, reason = \"high_amount\", decline;\n"
        "}\n"
        "rule review_medium priority 50 {\n"
        "  when amount > 500 and amount <= 10000;\n"
        "  then risk_score = 50, reason = \"medium_amount\", review;\n"
        "}\n"
        "rule allow_low {\n"
        "  when true;\n"
        "  then risk_score = 5, reason = \"low_amount\", allow;\n"
        "}\n";

    /* Step 1: Create compiler once */
    compiler = ax_compiler_create();
    if (!compiler || !ax_compiler_build(compiler, err, sizeof(err))) {
        fprintf(stderr, "compiler build failed: %s\n", err[0] ? err : "no detail");
        return 1;
    }

    /* Step 2: Compile rules once */
    if (!ax_compile_to_bytecode(compiler, rule_source, &bc, err, sizeof(err))) {
        fprintf(stderr, "compile failed: %s\n", err[0] ? err : "no detail");
        ax_compiler_destroy(compiler);
        return 1;
    }

    /* Step 3: Evaluate many transactions against the same bytecode */
    for (i = 0; i < num_txns; i++) {
        AXDecision decision = AX_DECISION_INIT;
        AXField fields[2];
        uint32_t j, count;

        memset(fields, 0, sizeof(fields));
        fields[0].name = "amount";
        fields[0].value.type = AX_VALUE_NUMBER;
        fields[0].value.number = amounts[i];
        fields[1].name = AX_FIELD_NOW_UTC_MS;
        fields[1].value.type = AX_VALUE_NUMBER;
        fields[1].value.number = 1700000000000.0;

        if (ax_eval_bytecode(compiler, &bc, fields, 2, &opts, &decision, err, sizeof(err)) != AX_ERR_OK) {
            fprintf(stderr, "eval failed for amount=%.0f: %s\n", amounts[i], err);
            ax_decision_reset(&decision);
            continue;
        }

        printf("amount=%.0f → %s (rule=%s)",
               amounts[i], action_name(decision.action_type),
               decision.rule_name ? decision.rule_name : "?");

        /* Read output fields */
        count = ax_eval_output_field_count(compiler);
        for (j = 0; j < count; j++) {
            const char* name = NULL;
            AXValue value;
            memset(&value, 0, sizeof(value));
            if (ax_eval_output_field_at(compiler, j, &name, &value) == AX_ERR_OK && name) {
                if (value.type == AX_VALUE_NUMBER)
                    printf(" %s=%.6g", name, value.number);
                else if (value.type == AX_VALUE_STRING && value.text)
                    printf(" %s=\"%s\"", name, value.text);
            }
        }
        printf("\n");

        ax_decision_reset(&decision);
    }

    /* Cleanup once */
    ax_bytecode_free(&bc);
    ax_compiler_destroy(compiler);
    printf("RESULT=OK\n");
    return 0;
}
