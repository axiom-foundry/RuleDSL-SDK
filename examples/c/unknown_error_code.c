/* unknown_error_code.c — Forward-compatible error handling.
 *
 * The AXErrorCode enum is append-only: a newer engine may return a code your
 * (older) build has never seen. `ax_error_to_string` is defined for EVERY code,
 * including ones outside the range your header knows about — it returns a stable
 * "AX_ERR_UNKNOWN" string rather than NULL or undefined behavior.
 *
 * Best practice: never assume a returned code is one you recognize. Always route
 * unknown codes through ax_error_to_string and treat them as a (non-OK) error.
 */
#include <stdio.h>
#include <string.h>

#include "axiom/ruledsl_c.h"

int main(void)
{
    /* Codes the current header knows about resolve to their own names. */
    const char* ok_name = ax_error_to_string(AX_ERR_OK);
    const char* dup_name = ax_error_to_string(AX_ERR_DUPLICATE_FIELD); /* 12, newest at time of writing */

    /* Codes outside the known range (a future engine could return these) must
     * still produce a defined, non-NULL string — never a crash. */
    const int future_codes[] = {13, 64, 200, 255};
    int rc = 0;

    printf("known: %d -> %s\n", (int)AX_ERR_OK, ok_name ? ok_name : "(NULL!)");
    printf("known: %d -> %s\n", (int)AX_ERR_DUPLICATE_FIELD, dup_name ? dup_name : "(NULL!)");

    for (size_t i = 0; i < sizeof future_codes / sizeof future_codes[0]; ++i) {
        const char* name = ax_error_to_string((AXErrorCode)future_codes[i]);
        if (name == NULL) {
            fprintf(stderr, "FAIL: ax_error_to_string(%d) returned NULL\n", future_codes[i]);
            rc = 1;
            continue;
        }
        printf("unknown: %d -> %s\n", future_codes[i], name);
        /* The engine's defined answer for an unrecognized code is "AX_ERR_UNKNOWN". */
        if (strcmp(name, "AX_ERR_UNKNOWN") != 0) {
            fprintf(stderr, "FAIL: expected AX_ERR_UNKNOWN for %d, got %s\n", future_codes[i], name);
            rc = 1;
        }
    }

    if (rc == 0)
        printf("UNKNOWN_CODE_OK\n");
    return rc;
}
