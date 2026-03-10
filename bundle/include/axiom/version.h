#pragma once
// Public version identifiers for the RuleDSL SDK.

#include "axiom/export.h"

#define AXIOM_VERSION_MAJOR 1
#define AXIOM_VERSION_MINOR 0
#define AXIOM_VERSION_PATCH 0
#define AXIOM_VERSION_STRING "1.0.0"

#define AXIOM_RULEDSL_LANGUAGE_VERSION_MAJOR 1
#define AXIOM_RULEDSL_LANGUAGE_VERSION_MINOR 0
#define AXIOM_RULEDSL_LANGUAGE_VERSION_PATCH 0
#define AXIOM_RULEDSL_LANGUAGE_VERSION_STRING "1.0.0"

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
