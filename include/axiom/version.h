#pragma once
// Public version identifiers for the RuleDSL SDK.

#include "axiom/export.h"

// AXIOM_VERSION_* is the SDK/product version.
#define AXIOM_VERSION_MAJOR 1
#define AXIOM_VERSION_MINOR 0
#define AXIOM_VERSION_PATCH 2
#define AXIOM_VERSION_STRING "1.0.2"

// AXIOM_RULEDSL_LANGUAGE_VERSION_* is the RuleDSL *language* version the compiler accepts (--lang),
// which is 0.9 — distinct from the product version above. It must match the compiler's supported
// language (ruledslc kSupportedLang) and the bytecode/manifest lang axis, all of which are 0.9.
#define AXIOM_RULEDSL_LANGUAGE_VERSION_MAJOR 0
#define AXIOM_RULEDSL_LANGUAGE_VERSION_MINOR 9
#define AXIOM_RULEDSL_LANGUAGE_VERSION_PATCH 0
#define AXIOM_RULEDSL_LANGUAGE_VERSION_STRING "0.9"

#ifdef __cplusplus
extern "C" {
#endif

/// Return the AXIOM SDK version string for diagnostics.
static inline const char* axiom_version_string(void)
{
    return AXIOM_VERSION_STRING;
}

/// Return the supported RuleDSL language version string.
static inline const char* axiom_ruledsl_language_version_string(void)
{
    return AXIOM_RULEDSL_LANGUAGE_VERSION_STRING;
}

#ifdef __cplusplus
}
#endif
